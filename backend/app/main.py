import hmac
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime
from typing import Literal

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from langgraph.types import Command
from pydantic import BaseModel, Field

from . import auth, db, emails, portal, rag, tools
from .auth import candidate_user, current_user, hr_user
from .config import CHECKPOINT_DB, HR_INVITE_CODE
from .graph import build_graph

app = FastAPI(title="H.R Assistant A.I")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
db.init()
graph = build_graph()
lock = threading.Lock()  # one graph step at a time
hr = APIRouter(dependencies=[Depends(hr_user)])  # every route on this router needs an HR login


@app.exception_handler(portal.PortalError)
def portal_error(_, e: portal.PortalError):
    return JSONResponse({"detail": e.msg}, status_code=e.status)


def cfg(t): return {"configurable": {"thread_id": t}}


def run_graph(t, inp):
    with lock:
        graph.invoke(inp, cfg(t))


def snapshot(t):
    st = graph.get_state(cfg(t))
    if not st.values:
        raise HTTPException(404, "Unknown workflow")
    pending = next((i.value for task in st.tasks for i in task.interrupts), None)
    return {"thread_id": t, "state": st.values, "pending": pending, "done": not st.next}


# =============== accounts ===============
class RegisterReq(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=120)
    password: str = Field(min_length=8, max_length=100)
    role: Literal["candidate", "hr"]
    invite_code: str = ""


class LoginReq(BaseModel):
    email: str
    password: str


class ProfileReq(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field("", max_length=30)
    location: str = Field("", max_length=80)
    skills: str = Field("", max_length=300)
    experience_years: int = Field(0, ge=0, le=50)


def _session(uid):
    u = db.run("SELECT id,email,name,role,phone,skills,experience_years,location FROM users WHERE id=?", (uid,), fetch=True)[0]
    return {"token": auth.make_token(uid, u["role"]), "user": u}


@app.post("/api/auth/register")
def register(r: RegisterReq):
    if r.role == "hr" and not hmac.compare_digest(r.invite_code, HR_INVITE_CODE):
        raise HTTPException(403, "A valid organization invitation code is required for HR accounts")
    email = r.email.lower()
    if db.run("SELECT 1 FROM users WHERE email=?", (email,), fetch=True):
        raise HTTPException(409, "This email is already registered")
    uid = uuid.uuid4().hex[:10]
    db.run("INSERT INTO users(id,email,name,role,password_hash) VALUES(?,?,?,?,?)",
           (uid, email, r.name.strip(), r.role, auth.hash_password(r.password)))
    return _session(uid)


@app.post("/api/auth/login")
def login(r: LoginReq):
    rows = db.run("SELECT id,password_hash FROM users WHERE email=?", (r.email.lower(),), fetch=True)
    if not rows or not auth.verify_password(r.password, rows[0]["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")
    return _session(rows[0]["id"])


@app.get("/api/auth/me")
def me(u=Depends(current_user)):
    return u


@app.put("/api/me/profile")
def save_profile(p: ProfileReq, u=Depends(current_user)):
    db.run("UPDATE users SET name=?,phone=?,location=?,skills=?,experience_years=? WHERE id=?",
           (p.name.strip(), p.phone, p.location, p.skills, p.experience_years, u["id"]))
    return _session(u["id"])["user"]


# =============== Candidate Dashboard ===============
@app.get("/api/jobs")
def jobs(q: str = "", location: str = "", skill: str = "", experience: int | None = None, _=Depends(current_user)):
    return portal.public_jobs(q, location, skill, experience)


@app.get("/api/jobs/{t}")
def job_detail(t: str, _=Depends(current_user)):
    j = portal.job(t)
    if not j or j["status"] not in ("published", "closed"):
        raise HTTPException(404, "Job not found")
    return {k: j[k] for k in ("thread_id", "title", "location", "work_mode", "exp_min", "exp_max", "jd", "published_at", "deadline_at")} | {
        "skills": [s.strip() for s in (j["skills"] or "").split(",") if s.strip()], "open": portal.is_open(j)}


@app.post("/api/jobs/{t}/apply")
async def apply(t: str, file: UploadFile = File(...), u=Depends(candidate_user)):
    data = await file.read()
    a = portal.apply_to_job(t, u, file.filename, data)
    db.audit(t, "Candidate", "application_submitted", {"name": u["name"]})
    return a


@app.get("/api/candidate/applications")
def my_applications(u=Depends(candidate_user)):
    return portal.my_applications(u["id"])


def _own_app(aid, u):
    rows = db.run("SELECT * FROM applications WHERE id=? AND user_id=?", (aid, u["id"]), fetch=True)
    if not rows:
        raise HTTPException(404, "Application not found")
    return rows[0]


class OfferReply(BaseModel):
    status: Literal["accepted", "declined"]


@app.post("/api/candidate/applications/{aid}/offer")
def candidate_offer(aid: str, body: OfferReply, u=Depends(candidate_user)):
    a = _own_app(aid, u)
    p = snapshot(a["thread_id"])["pending"] or {}
    if a["status"] != "Offer Received" or p.get("type") != "offer_wait" or p.get("candidate_id") != aid:
        raise HTTPException(400, "There is no open offer to answer")
    run_graph(a["thread_id"], Command(resume={"status": body.status}))
    return {"ok": True}


@app.get("/api/candidate/applications/{aid}/offer-letter")
def offer_letter(aid: str, u=Depends(candidate_user)):
    a = _own_app(aid, u)
    if not a["offer_path"] or not os.path.isfile(a["offer_path"]):
        raise HTTPException(404, "No offer letter")
    return FileResponse(a["offer_path"], media_type="application/pdf", filename="offer-letter.pdf")


@app.get("/api/applications/{aid}/resume")
def get_resume(aid: str, u=Depends(current_user)):
    rows = db.run("SELECT * FROM applications WHERE id=?", (aid,), fetch=True)
    # a candidate can only open their own resume; others get "not found"
    if not rows or (u["role"] != "hr" and rows[0]["user_id"] != u["id"]) or not os.path.isfile(rows[0]["resume_path"]):
        raise HTTPException(404, "Resume not found")
    return FileResponse(rows[0]["resume_path"], filename=rows[0]["resume_name"])


# =============== HR: hiring workflow ===============
class StartReq(BaseModel):
    query: str = Field(min_length=5, max_length=1000)


class JDDecision(BaseModel):
    status: Literal["approved", "rejected"]
    feedback: str = ""
    jd: str | None = None


class SelectReq(BaseModel):
    selected_id: str


class OfferHook(BaseModel):
    status: Literal["accepted", "declined"]


class LowReq(BaseModel):
    action: Literal["review", "extend"]


class InterviewInfo(BaseModel):
    date: str = Field(min_length=1)
    time: str = Field(min_length=1)
    timezone: str = Field(min_length=1)
    link: str = Field(min_length=1)


class ShortlistReq(BaseModel):
    approved_ids: list[str] = Field(min_length=1)
    interview: InterviewInfo
    override_reason: str = ""


@hr.post("/api/hiring/start")
def start(req: StartReq):
    t = uuid.uuid4().hex[:10]
    db.run("INSERT INTO jobs(thread_id,title,query,status) VALUES(?,?,?,'draft')", (t, "New role", req.query))
    portal.set_meta(t, req.query)
    db.audit(t, "HR", "hiring_started", {"query": req.query})
    run_graph(t, {"query": req.query, "declined_ids": [], "repost_count": 0})
    return snapshot(t)


@hr.get("/api/hiring")
def list_jobs():
    return db.run("SELECT thread_id,title,status,created_at FROM jobs ORDER BY created_at DESC", fetch=True)


@hr.get("/api/hiring/{t}")
def get_state(t: str):
    s = snapshot(t)
    s["candidate_count"] = tools.count_applications(t)
    return s


@hr.post("/api/hiring/{t}/jd-decision")
def jd_decision(t: str, d: JDDecision):
    run_graph(t, Command(resume=d.model_dump(exclude_none=True)))
    return snapshot(t)


@hr.post("/api/hiring/{t}/low-decision")
def low_decision(t: str, d: LowReq):
    if (snapshot(t)["pending"] or {}).get("type") != "low_apps":
        raise HTTPException(400, "No decision is pending")
    run_graph(t, Command(resume=d.model_dump()))
    return snapshot(t)


@hr.post("/api/hiring/{t}/shortlist")
def shortlist_review(t: str, d: ShortlistReq):
    p = snapshot(t)["pending"] or {}
    if p.get("type") != "shortlist_review":
        raise HTTPException(400, "No shortlist is waiting for review")
    allowed = {c["id"] for c in p["options"] + p["others"]}
    if not set(d.approved_ids) <= allowed:
        raise HTTPException(400, "Unknown candidate in the shortlist")

    interview = d.interview.model_dump()
    for key in ("date", "time", "timezone", "link"):
        value = str(interview.get(key, "")).strip()
        if not value:
            raise HTTPException(400, f"Interview {key} is required")
        interview[key] = value

    try:
        datetime.strptime(interview["date"], "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Interview date must be in YYYY-MM-DD format")
    try:
        datetime.strptime(interview["time"], "%H:%M")
    except ValueError:
        raise HTTPException(400, "Interview time must be in HH:MM format")

    body = d.model_dump()
    body["interview"] = interview
    run_graph(t, Command(resume=body))
    return snapshot(t)


@hr.post("/api/hiring/{t}/resumes")
async def import_resumes(t: str, files: list[UploadFile] = File(...), source: str = Form("Manual import")):
    """Manual import (for example applications from LinkedIn/Naukri). Duplicates of existing applicants are skipped."""
    ok, dup, rejected = 0, 0, []
    for f in files:
        try:
            portal.import_resume(t, f.filename, await f.read(), source[:40])
            ok += 1
        except portal.PortalError as e:
            if e.status == 409:
                dup += 1
            else:
                rejected.append(f"{f.filename}: {e.msg}")
    if ok:
        db.audit(t, "HR", "applications_imported", {"count": ok})
    return {"imported": ok, "duplicates": dup, "rejected": rejected, "total": tools.count_applications(t)}


@hr.post("/api/hiring/{t}/advance")
def advance(t: str):
    """Demo helper: skip the current 7-day / 48-hour wait right now."""
    if (snapshot(t)["pending"] or {}).get("type") != "wait":
        raise HTTPException(400, "Workflow is not waiting on a timer")
    run_graph(t, Command(resume={"ok": True}))
    return snapshot(t)


@hr.post("/api/hiring/{t}/select")
def select(t: str, req: SelectReq):
    run_graph(t, Command(resume=req.model_dump()))
    return snapshot(t)


@hr.post("/api/hiring/{t}/offer")
def record_offer_reply(t: str, hook: OfferHook):
    """HR records a reply that arrived outside the portal (for example by email)."""
    run_graph(t, Command(resume=hook.model_dump()))
    return snapshot(t)


@hr.get("/api/hiring/{t}/audit")
def audit_log(t: str):
    return db.run("SELECT * FROM audit_log WHERE thread_id=? ORDER BY id", (t,), fetch=True)


# =============== HR: job posting + tracking dashboard ===============
@hr.get("/api/hr/overview")
def overview():
    out = []
    for j in db.run("SELECT * FROM jobs ORDER BY created_at DESC", fetch=True):
        t = j["thread_id"]
        try:
            st = graph.get_state(cfg(t))
            vals = st.values or {}
            pending = next((i.value for task in st.tasks for i in task.interrupts), None) or {}
        except Exception:
            vals, pending = {}, {}
        out.append({"thread_id": t, "title": j["title"], "location": j["location"], "work_mode": j["work_mode"],
                    "exp_min": j["exp_min"], "exp_max": j["exp_max"], "status": j["status"], "stage": vals.get("stage", ""),
                    "pending": pending.get("type"), "next_check": pending.get("until") if pending.get("type") == "wait" else None,
                    "applicants": tools.count_applications(t), "published_at": j["published_at"],
                    "deadline_at": j["deadline_at"], "jd": j["jd"], "skills": j["skills"], "channels": portal.channels(t)})
    return out


@hr.get("/api/hr/jobs/{t}/applications")
def job_applications(t: str):
    return portal.list_applications(t)


@hr.get("/api/hr/jobs/{t}/emails")
def job_emails(t: str):
    return db.run("SELECT type,to_email,subject,status,sent_at FROM email_logs WHERE thread_id=? ORDER BY id DESC", (t,), fetch=True)


class JobMeta(BaseModel):
    location: str | None = Field(None, max_length=80)
    work_mode: str | None = Field(None, max_length=20)
    exp_min: int | None = Field(None, ge=0, le=50)
    exp_max: int | None = Field(None, ge=0, le=50)
    deadline_at: str | None = None


@hr.patch("/api/hr/jobs/{t}")
def edit_job(t: str, m: JobMeta):
    if not portal.job(t):
        raise HTTPException(404, "Job not found")
    fields = {k: v for k, v in m.model_dump().items() if v is not None}
    if "deadline_at" in fields:
        try:
            fields["deadline_at"] = datetime.fromisoformat(fields["deadline_at"]).isoformat(timespec="seconds")
        except ValueError:
            raise HTTPException(422, "Invalid deadline")
    if fields:
        db.run("UPDATE jobs SET " + ",".join(f"{k}=?" for k in fields) + " WHERE thread_id=?", (*fields.values(), t))
        db.audit(t, "HR", "job_details_edited", {"count": len(fields)})
    return {"ok": True}


class ChannelReq(BaseModel):
    url: str = Field(pattern=r"^https?://\S+$", max_length=500)


@hr.post("/api/hr/jobs/{t}/channels/{platform}")
def record_channel(t: str, platform: str, b: ChannelReq):
    """An external post counts as published only when HR records its URL here."""
    if platform not in portal.EXTERNAL or not portal.job(t):
        raise HTTPException(404, "Unknown channel")
    portal.record_channel(t, platform, b.url)
    db.audit(t, "HR", "external_post_recorded", {"name": platform})
    return {"ok": True}


SAFE_KEYS = {"name", "count", "feedback", "version", "status", "query", "reason"}


@hr.get("/api/hr/activity")
def activity(limit: int = 40):
    rows = db.run("SELECT a.id,a.ts,a.actor,a.action,a.payload,a.thread_id,j.title FROM audit_log a "
                  "LEFT JOIN jobs j ON j.thread_id=a.thread_id ORDER BY a.id DESC LIMIT ?", (min(limit, 200),), fetch=True)
    for r in rows:
        p = json.loads(r["payload"] or "{}")
        r["payload"] = {k: v for k, v in p.items() if k in SAFE_KEYS}
    return rows


# =============== delete history ===============
def _rm(path):
    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def purge(t: str):
    """Remove one hiring workflow completely: state, applications, resumes, vectors, letters, logs."""
    with lock:
        for r in db.run("SELECT resume_path,offer_path FROM applications WHERE thread_id=?", (t,), fetch=True):
            _rm(r["resume_path"]); _rm(r["offer_path"])
        try:
            rag._col("resumes").delete(where={"thread_id": t})
        except Exception:
            pass
        try:
            graph.checkpointer.delete_thread(t)
        except Exception:
            c = sqlite3.connect(CHECKPOINT_DB)
            for tbl in ("checkpoints", "writes"):
                try:
                    c.execute(f"DELETE FROM {tbl} WHERE thread_id=?", (t,))
                except sqlite3.Error:
                    pass
            c.commit(); c.close()
        db.run("DELETE FROM app_events WHERE app_id IN (SELECT id FROM applications WHERE thread_id=?)", (t,))
        for tbl in ("applications", "candidates", "email_logs", "audit_log", "job_channels", "jobs"):
            db.run(f"DELETE FROM {tbl} WHERE thread_id=?", (t,))


@hr.delete("/api/hiring/{t}")
def delete_one(t: str):
    purge(t)
    return {"deleted": t}


@hr.delete("/api/hiring")
def delete_all():
    ids = [j["thread_id"] for j in db.run("SELECT thread_id FROM jobs", fetch=True)]
    for t in ids:
        purge(t)
    return {"deleted": len(ids)}


app.include_router(hr)


# =============== Scheduler: wakes sleeping workflows ===============
def tick():
    """Every minute: resume timers that are due, remind about offers close to the deadline."""
    for job in db.run("SELECT thread_id FROM jobs", fetch=True):
        t = job["thread_id"]
        try:
            p = snapshot(t)["pending"] or {}
            now = datetime.utcnow().isoformat()
            if p.get("type") == "wait" and p["until"] <= now:
                run_graph(t, Command(resume={"ok": True}))
            elif p.get("type") == "offer_wait":
                if p["deadline"] <= now:
                    run_graph(t, Command(resume={"status": "no_reply"}))
                elif (datetime.fromisoformat(p["deadline"]) - datetime.utcnow()).total_seconds() < 86400:
                    s = snapshot(t)["state"]
                    c = next(c for c in s["shortlist"] if c["id"] == s["selected_id"])
                    tools.send_email(t, c["email"], "Reminder: your offer expires soon",
                                     emails.reminder(c["name"], s["title"], p["deadline"][:10]), "reminder")  # de-duplicated in send_email
        except Exception as e:
            print("scheduler error", t, e)


scheduler = BackgroundScheduler()


@app.on_event("startup")
def _start():
    scheduler.add_job(tick, "interval", minutes=1, max_instances=1)
    scheduler.start()


@app.on_event("shutdown")
def _stop():
    scheduler.shutdown(wait=False)
