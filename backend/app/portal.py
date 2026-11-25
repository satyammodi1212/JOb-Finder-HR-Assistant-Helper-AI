"""Candidate Dashboard logic: job board, applications, resume storage, status timeline.
This is the built-in job portal, so no LinkedIn / Naukri / JobIndia API key is needed."""
import hashlib
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta

from . import db, rag
from .config import APPLY_DEADLINE_DAYS, DATA, MAX_RESUME_MB

PORTAL = "Candidate Portal"
EXTERNAL = ["LinkedIn", "Naukri.com", "JobIndia"]   # optional: HR pastes the post URL by hand
ALLOWED = {".pdf": b"%PDF", ".docx": b"PK"}


class PortalError(Exception):
    def __init__(self, status: int, msg: str):
        self.status, self.msg = status, msg


def now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def parse_meta(q: str) -> dict:
    loc = re.search(r"\bin\s+([A-Z]\w*(?:\s+[A-Z]\w*)*)", q)
    mode = next((m for m in ("remote", "hybrid", "onsite") if m in q.lower().replace("on-site", "onsite")), "")
    lo, hi = 0, 40
    r = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)\s*(?:years|yrs)", q, re.I)
    if r:
        lo, hi = int(r[1]), int(r[2])
    else:
        p = re.search(r"(\d+)\s*\+\s*(?:years|yrs)", q, re.I)
        if p:
            lo = int(p[1])
    return {"location": loc.group(1) if loc else "", "work_mode": mode, "exp_min": lo, "exp_max": hi}


def set_meta(t: str, query: str):
    m = parse_meta(query)
    db.run("UPDATE jobs SET location=?,work_mode=?,exp_min=?,exp_max=? WHERE thread_id=?",
           (m["location"], m["work_mode"], m["exp_min"], m["exp_max"], t))


def job(t: str):
    rows = db.run("SELECT * FROM jobs WHERE thread_id=?", (t,), fetch=True)
    return rows[0] if rows else None


def is_open(j) -> bool:
    return bool(j) and j["status"] == "published" and (j["deadline_at"] or "9999") > now()


def channels(t: str):
    return db.run("SELECT platform,status,url,updated_at FROM job_channels WHERE thread_id=? ORDER BY rowid", (t,), fetch=True)


def publish(t: str, title: str, jd: str, skills: list):
    """Idempotent: calling it again (retry or revised JD) updates the same live job, never duplicates it."""
    j = job(t)
    ts = now()
    published = j["published_at"] or ts
    deadline = j["deadline_at"] or (datetime.utcnow() + timedelta(days=APPLY_DEADLINE_DAYS)).isoformat(timespec="seconds")
    db.run("UPDATE jobs SET title=?,jd=?,skills=?,status='published',published_at=?,deadline_at=? WHERE thread_id=?",
           (title, jd, ", ".join(skills), published, deadline, t))
    db.run("INSERT OR IGNORE INTO job_channels VALUES(?,?,?,?,?)", (t, PORTAL, "published", f"/candidate/jobs/{t}", ts))
    for p in EXTERNAL:
        db.run("INSERT OR IGNORE INTO job_channels VALUES(?,?,?,?,?)", (t, p, "pending_manual", None, ts))
    return channels(t)


def record_channel(t: str, platform: str, url: str):
    db.run("UPDATE job_channels SET status='published',url=?,updated_at=? WHERE thread_id=? AND platform=?", (url, now(), t, platform))


def close_job(t: str):
    db.run("UPDATE jobs SET status='closed' WHERE thread_id=? AND status='published'", (t,))


def set_status(app_id: str, status: str, note: str = ""):
    rows = db.run("SELECT status FROM applications WHERE id=?", (app_id,), fetch=True)
    if not rows or (rows[0]["status"] == status and not note):
        return
    db.run("UPDATE applications SET status=? WHERE id=?", (status, app_id))
    db.run("INSERT INTO app_events(app_id,status,note,ts) VALUES(?,?,?,?)", (app_id, status, note, now()))


def set_score(app_id: str, score: float):
    db.run("UPDATE applications SET score=? WHERE id=?", (score, app_id))


def set_offer_path(app_id: str, path: str):
    db.run("UPDATE applications SET offer_path=? WHERE id=?", (path, app_id))


def validate_resume(filename: str, data: bytes) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED or not data.startswith(ALLOWED[ext]):
        raise PortalError(400, "Only PDF or DOCX resumes are accepted")
    if len(data) > MAX_RESUME_MB * 1024 * 1024:
        raise PortalError(413, f"Resume must be smaller than {MAX_RESUME_MB} MB")
    return ext


def _store(t, user, filename, data, source, check_hash):
    ext = validate_resume(filename, data)
    app_id = uuid.uuid4().hex[:10]
    path = os.path.join(DATA, "resumes", f"{app_id}{ext}")   # private folder, never served directly
    with open(path, "wb") as f:
        f.write(data)
    try:
        text = rag.extract_text(path)
    except Exception:
        text = ""
    name, email = (user["name"], user["email"]) if user else rag.guess_contact(text, filename)
    fhash = hashlib.sha256(data).hexdigest()
    conds, args = ["(email<>'' AND lower(email)=lower(?))"], [t, email]
    if user:
        conds.append("user_id=?"); args.append(user["id"])
    if check_hash:
        conds.append("file_hash=?"); args.append(fhash)
    if db.run("SELECT id FROM applications WHERE thread_id=? AND (" + " OR ".join(conds) + ")", args, fetch=True):
        os.remove(path)
        raise PortalError(409, "You have already applied for this job" if user else "Duplicate application skipped")
    try:
        db.run("INSERT INTO applications VALUES(?,?,?,?,?,?,?,?,?,?,NULL,NULL,?)",
               (app_id, t, user["id"] if user else None, name, email, source, "Submitted", path,
                os.path.basename(filename or f"resume{ext}"), fhash, now()))
    except sqlite3.IntegrityError:
        os.remove(path)
        raise PortalError(409, "You have already applied for this job")
    db.run("INSERT INTO candidates(id,thread_id,name,email,source,resume_path,text) VALUES(?,?,?,?,?,?,?)",
           (app_id, t, name, email, source, path, text))
    if text.strip():
        rag.ingest_resume(t, app_id, text)
    db.run("INSERT INTO app_events(app_id,status,note,ts) VALUES(?,?,?,?)", (app_id, "Submitted", "Application received", now()))
    return {"id": app_id, "status": "Submitted", "name": name}


def apply_to_job(t, user, filename, data):
    j = job(t)
    if not j or j["status"] not in ("published", "closed"):
        raise PortalError(404, "Job not found")
    if not is_open(j):
        raise PortalError(400, "Applications are closed for this job")
    return _store(t, user, filename, data, PORTAL, False)


def import_resume(t, filename, data, source):
    if not job(t):
        raise PortalError(404, "Job not found")
    return _store(t, None, filename, data, source, True)


def public_jobs(q="", location="", skill="", experience=None):
    sql = ("SELECT thread_id,title,location,work_mode,exp_min,exp_max,skills,jd,published_at,deadline_at,status "
           "FROM jobs WHERE status='published'")
    args = []
    if q:
        sql += " AND (title LIKE ? OR jd LIKE ? OR skills LIKE ?)"; args += [f"%{q}%"] * 3
    if location:
        sql += " AND location LIKE ?"; args.append(f"%{location}%")
    if skill:
        sql += " AND skills LIKE ?"; args.append(f"%{skill}%")
    if experience is not None:
        sql += " AND exp_min<=? AND exp_max>=?"; args += [experience, experience]
    rows = db.run(sql + " ORDER BY published_at DESC", args, fetch=True)
    for r in rows:
        r["open"] = is_open(r)
        r["skills"] = [s.strip() for s in (r["skills"] or "").split(",") if s.strip()]
    return rows


def my_applications(user_id: str):
    rows = db.run("SELECT a.id,a.thread_id,a.status,a.submitted_at,a.resume_name,(a.offer_path IS NOT NULL) AS has_offer,"
                  "j.title,j.location FROM applications a LEFT JOIN jobs j ON j.thread_id=a.thread_id "
                  "WHERE a.user_id=? ORDER BY a.submitted_at DESC", (user_id,), fetch=True)
    for r in rows:
        r["events"] = db.run("SELECT status,note,ts FROM app_events WHERE app_id=? ORDER BY id", (r["id"],), fetch=True)
    return rows


def list_applications(t: str):
    return db.run("SELECT id,name,email,source,status,submitted_at,score,resume_name FROM applications "
                  "WHERE thread_id=? ORDER BY submitted_at DESC", (t,), fetch=True)
