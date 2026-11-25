import { useEffect, useState } from "react";
import { NavLink, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { api } from "./api";
import { useAuth } from "./auth";
import { badgeClass, day, when } from "./util";

export default function CandidateApp() {
  const { user, signOut } = useAuth();
  return (
    <div className="shell">
      <header className="top">
        <b>S.K A.I Development - Careers</b>
        <nav>
          <NavLink to="/candidate" end>Find jobs</NavLink>
          <NavLink to="/candidate/applications">My applications</NavLink>
          <NavLink to="/candidate/profile">My profile</NavLink>
        </nav>
        <span className="who">{user.name}<button onClick={signOut}>Log out</button></span>
      </header>
      <Routes>
        <Route index element={<Jobs />} />
        <Route path="jobs/:id" element={<Jobs />} />
        <Route path="applications" element={<MyApps />} />
        <Route path="profile" element={<Profile />} />
      </Routes>
    </div>
  );
}

function Jobs() {
  const { id } = useParams();
  const nav = useNavigate();
  const [f, setF] = useState({ q: "", location: "", skill: "", experience: "" });
  const [jobs, setJobs] = useState([]);
  const [applied, setApplied] = useState(new Set());
  const [file, setFile] = useState(null);
  const [msg, setMsg] = useState({ t: "", ok: true });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const load = () => {
    api.jobs(f).then(setJobs).catch((e) => setMsg({ t: e.message, ok: false }));
    api.myApps().then((a) => setApplied(new Set(a.map((x) => x.thread_id)))).catch(() => {});
  };
  useEffect(() => { load(); const i = setInterval(load, 8000); return () => clearInterval(i); }, [f]);
  const job = jobs.find((j) => j.thread_id === id);

  const apply = async () => {
    setBusy(true); setMsg({ t: "", ok: true });
    try { await api.apply(job.thread_id, file); setMsg({ t: "Application submitted. Track it under My applications.", ok: true }); setFile(null); load(); }
    catch (e) { setMsg({ t: e.message, ok: false }); }
    setBusy(false);
  };

  return (
    <main className="page two">
      <section>
        <h2>Open jobs</h2>
        <div className="filters">
          <input placeholder="Search title or keyword" value={f.q} onChange={set("q")} aria-label="Search" />
          <input placeholder="Location" value={f.location} onChange={set("location")} aria-label="Location" />
          <input placeholder="Skill, for example React" value={f.skill} onChange={set("skill")} aria-label="Skill" />
          <select value={f.experience} onChange={set("experience")} aria-label="Experience">
            <option value="">Any experience</option><option value="0">Fresher (0 years)</option>
            {[1, 2, 3, 5, 8].map((y) => <option key={y} value={y}>{y} years</option>)}
          </select>
        </div>
        {jobs.length === 0 && <p className="empty">No jobs match. Try clearing a filter.</p>}
        {jobs.map((j) => (
          <button key={j.thread_id} className={"jobcard" + (j.thread_id === id ? " on" : "")} onClick={() => { nav(`/candidate/jobs/${j.thread_id}`); setMsg({ t: "", ok: true }); }}>
            <b>{j.title}</b>
            <span className="muted">{[j.location, j.work_mode, j.exp_min === 0 ? "Freshers welcome" : `${j.exp_min}+ years`].filter(Boolean).join(" · ")}</span>
            <span>{j.skills.slice(0, 5).map((s) => <i key={s} className="chip">{s}</i>)}</span>
            <span className="muted">{j.open ? `Apply by ${day(j.deadline_at)}` : "Applications closed"}</span>
          </button>
        ))}
      </section>
      <section>
        {!job ? <p className="empty">Select a job to read the details and apply.</p> : (
          <div className="card">
            <h3>{job.title}</h3>
            <p className="muted">{[job.location, job.work_mode, `Experience ${job.exp_min}-${job.exp_max} years`].filter(Boolean).join(" · ")}</p>
            <p><span className={badgeClass(job.open ? "published" : "closed")}>{job.open ? "Applications open" : "Applications closed"}</span> <span className="muted">Deadline {day(job.deadline_at)}</span></p>
            <p><b>Skills:</b> {job.skills.map((s) => <i key={s} className="chip">{s}</i>)}</p>
            <pre className="jd">{job.jd}</pre>
            {applied.has(job.thread_id) ? <p className="b ok">You have applied for this job.</p> : job.open && (
              <div className="act">
                <label>Upload your resume (PDF or DOCX, up to 5 MB)
                  <input type="file" accept=".pdf,.docx" onChange={(e) => setFile(e.target.files[0] || null)} /></label>
                <button className="primary" disabled={!file || busy} onClick={apply}>{busy ? "Submitting..." : "Apply now"}</button>
              </div>
            )}
            {msg.t && <p className={msg.ok ? "okmsg" : "error"} role="status">{msg.t}</p>}
          </div>
        )}
      </section>
    </main>
  );
}

function MyApps() {
  const [apps, setApps] = useState([]);
  const [err, setErr] = useState("");
  const load = () => api.myApps().then(setApps).catch((e) => setErr(e.message));
  useEffect(() => { load(); const i = setInterval(load, 5000); return () => clearInterval(i); }, []);
  const reply = async (id, status) => {
    if (!window.confirm(`Are you sure you want to ${status === "accepted" ? "accept" : "decline"} this offer?`)) return;
    try { await api.offerReply(id, status); load(); } catch (e) { setErr(e.message); }
  };
  return (
    <main className="page">
      <h2>My applications <span className="muted">updates live</span></h2>
      {err && <p className="error">{err}</p>}
      {apps.length === 0 && <p className="empty">You have not applied yet. Find a job to get started.</p>}
      {apps.map((a) => (
        <div className="card app" key={a.id}>
          <div className="row between"><h3>{a.title || "Job"}</h3><span className={badgeClass(a.status)}>{a.status}</span></div>
          <p className="muted">{a.location} · Applied {when(a.submitted_at)}</p>
          <ol className="timeline">{a.events.map((e, i) => <li key={i}><b>{e.status}</b> <span className="muted">{when(e.ts)}{e.note ? ` - ${e.note}` : ""}</span></li>)}</ol>
          {a.status === "Offer Received" && (
            <div className="act row">
              {a.has_offer && <button onClick={() => api.offerLetter(a.id).catch((e) => setErr(e.message))}>View offer letter</button>}
              <button className="primary" onClick={() => reply(a.id, "accepted")}>Accept offer</button>
              <button className="danger" onClick={() => reply(a.id, "declined")}>Decline offer</button>
            </div>)}
        </div>
      ))}
    </main>
  );
}

function Profile() {
  const { user, setUser } = useAuth();
  const [f, setF] = useState({ name: user.name, phone: user.phone || "", location: user.location || "", skills: user.skills || "", experience_years: user.experience_years || 0 });
  const [msg, setMsg] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async (e) => {
    e.preventDefault();
    try { setUser(await api.saveProfile({ ...f, experience_years: +f.experience_years })); setMsg("Saved. Applications you already submitted keep the resume you sent."); }
    catch (x) { setMsg(x.message); }
  };
  return (
    <main className="page narrow">
      <h2>My profile</h2>
      <form className="card" onSubmit={save}>
        <label>Full name<input required value={f.name} onChange={set("name")} /></label>
        <label>Email<input value={user.email} disabled /></label>
        <label>Phone<input value={f.phone} onChange={set("phone")} /></label>
        <label>Location<input value={f.location} onChange={set("location")} /></label>
        <label>Skills (comma separated)<input value={f.skills} onChange={set("skills")} /></label>
        <label>Years of experience (0 = fresher)<input type="number" min="0" max="50" value={f.experience_years} onChange={set("experience_years")} /></label>
        <button className="primary">Save profile</button>
        {msg && <p className="muted" role="status">{msg}</p>}
      </form>
    </main>
  );
}
