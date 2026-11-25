import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { badgeClass, day, when } from "./util";

export default function HRJobs() {
  const [jobs, setJobs] = useState([]);
  const [open, setOpen] = useState(null);
  const [apps, setApps] = useState([]);
  const [mails, setMails] = useState([]);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      setJobs(await api.overview());
      if (open) { setApps(await api.jobApps(open)); setMails(await api.jobEmails(open)); }
    } catch (e) { setErr(e.message); }
  }, [open]);
  useEffect(() => { load(); const id = setInterval(load, 5000); return () => clearInterval(id); }, [load]);

  const job = jobs.find((j) => j.thread_id === open);
  return (
    <main className="page">
      <h2>Jobs and applicants <span className="muted">tracked live</span></h2>
      {err && <p className="error">{err}</p>}
      {jobs.length === 0 && <p className="empty">No jobs yet. Start one from the Hiring chat tab.</p>}
      {jobs.length > 0 && (
        <div className="scroll"><table>
          <thead><tr><th>Job</th><th>Location</th><th>Status</th><th>Applicants</th><th>Apply by</th><th>Next step</th><th></th></tr></thead>
          <tbody>{jobs.map((j) => (
            <tr key={j.thread_id} className={open === j.thread_id ? "sel" : ""}>
              <td><b>{j.title}</b></td><td>{j.location || "-"}</td>
              <td><span className={badgeClass(j.status)}>{j.status}</span></td>
              <td><b>{j.applicants}</b></td><td>{day(j.deadline_at)}</td>
              <td>{j.pending === "wait" ? `Check ${when(j.next_check)}` : j.pending ? "Needs your action" : j.stage || "-"}</td>
              <td><button onClick={() => setOpen(open === j.thread_id ? null : j.thread_id)}>{open === j.thread_id ? "Hide" : "Open"}</button></td>
            </tr>))}</tbody>
        </table></div>
      )}
      {job && <JobPanel job={job} apps={apps} mails={mails} reload={load} />}
    </main>
  );
}

function JobPanel({ job, apps, mails, reload }) {
  const [m, setM] = useState({ location: job.location || "", work_mode: job.work_mode || "", exp_min: job.exp_min, exp_max: job.exp_max, deadline: (job.deadline_at || "").slice(0, 10) });
  const [urls, setUrls] = useState({});
  const [msg, setMsg] = useState("");
  const run = async (fn, ok) => { setMsg(""); try { await fn(); setMsg(ok); reload(); } catch (e) { setMsg(e.message); } };
  const copy = () => navigator.clipboard.writeText(`${job.title}\n${job.location}\n\n${job.jd}`).then(() => setMsg("Copied. Paste it into the job site."));

  return (
    <section className="panel">
      <h3>{job.title}</h3>
      {msg && <p className="muted" role="status">{msg}</p>}

      <h4>Where it is posted</h4>
      <table><tbody>{job.channels.map((c) => (
        <tr key={c.platform}>
          <td>{c.platform}</td>
          <td><span className={badgeClass(c.status)}>{c.status === "pending_manual" ? "not posted yet" : c.status}</span></td>
          <td>{c.platform === "Candidate Portal" ? "Live on the Candidate Dashboard"
            : c.url ? <a href={c.url} target="_blank" rel="noreferrer">{c.url}</a>
            : job.status !== "draft" ? (
              <span className="row">
                <button onClick={copy}>Copy posting text</button>
                <input placeholder="Paste the post URL after you publish it" value={urls[c.platform] || ""} onChange={(e) => setUrls({ ...urls, [c.platform]: e.target.value })} />
                <button disabled={!urls[c.platform]} onClick={() => run(() => api.recordChannel(job.thread_id, c.platform, urls[c.platform]), "Recorded")}>Record</button>
              </span>) : "Available after approval"}</td>
        </tr>))}</tbody></table>
      <p className="muted">LinkedIn, Naukri and JobIndia are optional: post by hand with the copied text, then record the link. Only recorded posts are shown as published.</p>

      <h4>Job details shown to candidates</h4>
      <div className="row">
        <label>Location<input value={m.location} onChange={(e) => setM({ ...m, location: e.target.value })} /></label>
        <label>Work mode<select value={m.work_mode} onChange={(e) => setM({ ...m, work_mode: e.target.value })}><option value="">Not set</option><option>onsite</option><option>hybrid</option><option>remote</option></select></label>
        <label>Min years<input type="number" min="0" value={m.exp_min} onChange={(e) => setM({ ...m, exp_min: +e.target.value })} /></label>
        <label>Max years<input type="number" min="0" value={m.exp_max} onChange={(e) => setM({ ...m, exp_max: +e.target.value })} /></label>
        <label>Apply by<input type="date" value={m.deadline} onChange={(e) => setM({ ...m, deadline: e.target.value })} /></label>
        <button className="primary" onClick={() => run(() => api.patchJob(job.thread_id, { location: m.location, work_mode: m.work_mode, exp_min: m.exp_min, exp_max: m.exp_max, ...(m.deadline ? { deadline_at: m.deadline + "T23:59:00" } : {}) }), "Saved")}>Save</button>
      </div>

      <h4>Applicants ({apps.length})</h4>
      {apps.length === 0 ? <p className="empty">No applications yet. New ones appear here as soon as candidates apply.</p> : (
        <div className="scroll"><table>
          <thead><tr><th>Name</th><th>Email</th><th>Source</th><th>Applied</th><th>Status</th><th>AI score</th><th>Resume</th></tr></thead>
          <tbody>{apps.map((a) => (
            <tr key={a.id}><td>{a.name}</td><td>{a.email || "-"}</td><td>{a.source}</td><td>{when(a.submitted_at)}</td>
              <td><span className={badgeClass(a.status)}>{a.status}</span></td><td>{a.score ?? "-"}</td>
              <td><button onClick={() => api.resume(a.id, a.resume_name).catch((e) => setMsg(e.message))}>Download</button></td></tr>))}</tbody>
        </table></div>
      )}

      <h4>Emails</h4>
      {mails.length === 0 ? <p className="empty">No emails sent yet.</p> : (
        <div className="scroll"><table><thead><tr><th>Type</th><th>To</th><th>Subject</th><th>Status</th><th>Time</th></tr></thead>
          <tbody>{mails.map((e, i) => <tr key={i}><td>{e.type}</td><td>{e.to_email}</td><td>{e.subject}</td><td><span className={badgeClass(e.status)}>{e.status}</span></td><td>{when(e.sent_at)}</td></tr>)}</tbody></table></div>
      )}
    </section>
  );
}
