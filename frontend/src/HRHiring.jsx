import { useEffect, useState, useCallback } from "react";
import { api } from "./api";

const STEPS = [
  ["jd_review", "JD review"],
  ["monitoring", "Posted and monitoring"],
  ["screening", "Resume screening"],
  ["interviews", "Interviews"],
  ["offer_pending", "Offer sent"],
  ["completed", "Offer accepted"],
];

export default function HRHiring() {
  const [jobs, setJobs] = useState([]);
  const [cur, setCur] = useState(null); // snapshot
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const refreshList = () => api.list().then(setJobs).catch(() => {});
  const load = useCallback((t) => api.get(t).then(setCur).catch((e) => setErr(e.message)), []);

  useEffect(() => { refreshList(); }, []);
  useEffect(() => {
    if (!cur) return;
    const id = setInterval(() => load(cur.thread_id), 5000); // pick up scheduler wake-ups
    return () => clearInterval(id);
  }, [cur?.thread_id, load]);

  const act = async (fn) => {
    setBusy(true); setErr("");
    try { setCur(await fn()); refreshList(); } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  const removeOne = async (t, title) => {
    if (!window.confirm(`Delete "${title}"? Its chat, resumes, shortlist and logs will be removed permanently.`)) return;
    try {
      await api.remove(t);
      if (cur?.thread_id === t) setCur(null);
      refreshList();
    } catch (e) { setErr(e.message); }
  };
  const clearAll = async () => {
    if (!window.confirm("Delete ALL hiring history? This cannot be undone.")) return;
    try { await api.clearAll(); setCur(null); refreshList(); } catch (e) { setErr(e.message); }
  };
  const start = () => text.trim() && act(() => api.start(text)).then(() => setText(""));

  return (
    <div className="app">
      <aside className="side">
        <h1>Hiring requests</h1>
        <button className="primary" onClick={() => setCur(null)}>New hiring request</button>
        <p className="muted">Your hiring requests</p>
        {jobs.length === 0 && <p className="empty">Nothing yet. Describe a role to begin.</p>}
        {jobs.map((j) => (
          <div key={j.thread_id} className={"jobrow" + (cur?.thread_id === j.thread_id ? " on" : "")}>
            <button className="job" onClick={() => load(j.thread_id)}>{j.title}</button>
            <button className="del" aria-label={`Delete ${j.title}`} title="Delete this chat" onClick={() => removeOne(j.thread_id, j.title)}>Delete</button>
          </div>
        ))}
        {jobs.length > 0 && <button className="danger clear" onClick={clearAll}>Clear all history</button>}
      </aside>

      <main className="main">
        {!cur ? (
          <section className="hero">
            <h2>Who do you need to hire?</h2>
            <p>Describe the role and the skills. I will write the job description and ask for your approval before anything is posted.</p>
            <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)}
                      placeholder="I want to hire a Frontend Developer with React and TypeScript skills" />
            <button className="primary" disabled={busy} onClick={start}>{busy ? "Writing job description..." : "Create job description"}</button>
          </section>
        ) : (
          <Workflow cur={cur} act={act} busy={busy} />
        )}
        {err && <p className="error">{err}</p>}
      </main>

      <aside className="rail">
        <h3>Progress</h3>
        {cur ? <Pipeline stage={cur.state.stage} /> : <p className="empty">Progress appears once you start a request.</p>}
        {cur && <p className="muted">{cur.candidate_count} applications received</p>}
      </aside>
    </div>
  );
}

function Pipeline({ stage }) {
  const idx = Math.max(0, STEPS.findIndex(([k]) => k === stage));
  return (
    <ol className="steps">
      {STEPS.map(([k, label], i) => (
        <li key={k} className={i < idx || stage === "completed" ? "done" : i === idx ? "now" : ""}>{label}</li>
      ))}
    </ol>
  );
}

function Workflow({ cur, act, busy }) {
  const { state: s, pending: p, thread_id: t } = cur;
  const [feedback, setFeedback] = useState("");
  const [editing, setEditing] = useState(false);
  const [jd, setJd] = useState(s.jd);
  const [source, setSource] = useState("LinkedIn");
  useEffect(() => setJd(s.jd), [s.jd]);

  return (
    <div className="flow">
      <div className="bubble hr">{s.query}</div>

      <div className="card">
        <h3>{s.title} <span className="muted">version {s.jd_version}</span></h3>
        {editing ? <textarea className="jdedit" rows={14} value={jd} onChange={(e) => setJd(e.target.value)} />
                 : <pre className="jd">{s.jd}</pre>}
        {s.skills?.length > 0 && <p className="chips">{s.skills.map((k) => <span key={k}>{k}</span>)}</p>}
      </div>

      {p?.type === "jd_approval" && (
        <div className="card act">
          <p>{s.repost_count > 0 ? "The AI revised this job description because too few people applied. The live job keeps its current text until you approve." : "Waiting for your approval. Nothing is posted until you approve."}</p>
          <textarea rows={2} value={feedback} onChange={(e) => setFeedback(e.target.value)}
                    placeholder="Feedback for a rewrite, for example: add a remote option" />
          <div className="row">
            <button className="primary" disabled={busy} onClick={() => act(() => api.jdDecision(t, { status: "approved", ...(editing ? { jd } : {}) }))}>Approve and post</button>
            <button onClick={() => setEditing(!editing)}>{editing ? "Stop editing" : "Edit text"}</button>
            <button className="danger" disabled={busy} onClick={() => act(() => api.jdDecision(t, { status: "rejected", feedback }))}>Reject and rewrite</button>
          </div>
        </div>
      )}

      {s.job_posts?.length > 0 && (
        <div className="card"><h3>Posted on</h3>
          <p>Live on the Candidate Dashboard. {s.job_posts.filter((j) => j.platform !== "Candidate Portal" && j.status === "published").length} external post(s) recorded.
            Manage external posts under <b>Jobs and applicants</b>.</p>
        </div>
      )}

      {p?.type === "wait" && (
        <div className="card act">
          <p>Monitoring applications: {p.reason}. Next check after {new Date(p.until + "Z").toLocaleString()}.</p>
          <div className="row">
            <select value={source} onChange={(e) => setSource(e.target.value)}>
              <option>LinkedIn</option><option>Naukri.com</option><option>JobIndia</option><option>Manual import</option>
            </select>
            <input type="file" multiple accept=".pdf,.docx" id="up"
                   onChange={(e) => e.target.files.length && api.upload(t, e.target.files, source).then(() => act(() => api.get(t)))} />
            <button disabled={busy} onClick={() => act(() => api.advance(t))}>Skip the wait (demo)</button>
          </div>
          <p className="muted">Candidates apply on the Candidate Dashboard and appear here and under Jobs and applicants automatically. You can also import resumes manually, for example from LinkedIn or Naukri (duplicates are skipped).</p>
        </div>
      )}

      {p?.type === "low_apps" && (
        <div className="card act">
          <p>Only {p.count} valid applications so far (target {p.target}), even after the revised job description. What would you like to do?</p>
          <div className="row">
            <button className="primary" disabled={busy} onClick={() => act(() => api.lowDecision(t, "review"))}>Review the {p.count} available applicants</button>
            <button disabled={busy} onClick={() => act(() => api.lowDecision(t, "extend"))}>Extend recruiting (another 48 hours)</button>
          </div>
        </div>
      )}

      {p?.type === "shortlist_review" && <ShortlistReview p={p} t={t} act={act} busy={busy} />}

      {p?.type === "select" && (
        <div className="card act"><h3>Shortlisted candidates</h3>
          <table><thead><tr><th>Candidate</th><th>Score</th><th>Matched</th><th>Missing</th><th></th></tr></thead>
            <tbody>{p.options.map((c) => (
              <tr key={c.id}><td><b>{c.name}</b><br /><span className="muted">{c.summary}</span></td><td>{c.score}</td>
                <td>{c.matched_skills.join(", ") || "-"}</td><td>{c.missing_skills.join(", ") || "-"}</td>
                <td><button className="primary" disabled={busy} onClick={() => act(() => api.select(t, c.id))}>Send offer</button></td></tr>))}
            </tbody></table>
          <p className="muted">Interview invitations were sent. Choosing a candidate sends the offer letter and regret emails to the others.</p>
        </div>
      )}

      {p?.type === "offer_wait" && (
        <div className="card act">
          <p>Offer sent. Waiting for the candidate to reply (on their dashboard, or record an emailed reply) until {new Date(p.deadline + "Z").toLocaleDateString()}. A reminder goes out one day before.</p>
          <div className="row">
            <button className="primary" disabled={busy} onClick={() => act(() => api.offer(t, "accepted"))}>Record reply: accepted</button>
            <button className="danger" disabled={busy} onClick={() => act(() => api.offer(t, "declined"))}>Record reply: declined</button>
          </div>
        </div>
      )}

      {cur.done && s.stage === "completed" && <div className="card ok">The offer was accepted. Confirmation emails were sent.</div>}
    </div>
  );
}

function ShortlistReview({ p, t, act, busy }) {
  const [picked, setPicked] = useState(new Set(p.options.map((c) => c.id)));
  const [iv, setIv] = useState({ date: "", time: "", timezone: "IST", link: "" });
  const [reason, setReason] = useState("");
  const toggle = (id) => { const n = new Set(picked); n.has(id) ? n.delete(id) : n.add(id); setPicked(n); };
  const row = (c) => (
    <tr key={c.id}>
      <td><input type="checkbox" aria-label={`Include ${c.name}`} checked={picked.has(c.id)} onChange={() => toggle(c.id)} /></td>
      <td><b>{c.name}</b><br /><span className="muted">{c.summary}</span></td><td>{c.score}</td>
      <td>{c.matched_skills.join(", ") || "-"}{c.partial_skills.length ? <span className="muted"> (partly: {c.partial_skills.join(", ")})</span> : null}</td>
      <td>{c.missing_skills.length ? <>Not found in resume: {c.missing_skills.join(", ")}</> : "-"}</td>
    </tr>);
  const ready = picked.size > 0 && iv.date && iv.time && iv.timezone && iv.link;
  return (
    <div className="card act">
      <h3>Review the AI shortlist</h3>
      <p className="muted">Scoring rubric: {p.rubric.skills?.join(", ")}. Weights: skills {p.rubric.weights?.skill * 100}%, experience {p.rubric.weights?.experience * 100}%, education {p.rubric.weights?.education * 100}%, similarity to the job {p.rubric.weights?.semantic * 100}%. {p.rubric.rule}</p>
      {p.flagged?.length > 0 && <p className="error">Needs manual review (unreadable resume): {p.flagged.map((f) => f.name).join(", ")}</p>}
      <div className="scroll"><table>
        <thead><tr><th>Include</th><th>Candidate</th><th>Score</th><th>Skills found</th><th>Missing</th></tr></thead>
        <tbody>{p.options.map(row)}</tbody>
      </table></div>
      {p.others.length > 0 && (<details><summary>Other applicants not proposed ({p.others.length}) - tick to add</summary>
        <div className="scroll"><table><tbody>{p.others.map(row)}</tbody></table></div></details>)}
      <label>Reason if you changed the AI shortlist (saved in the audit log)<input value={reason} onChange={(e) => setReason(e.target.value)} /></label>
      <h4>Interview details (sent in the invitation emails)</h4>
      <div className="row">
        <label>Date<input type="date" value={iv.date} onChange={(e) => setIv({ ...iv, date: e.target.value })} /></label>
        <label>Time<input type="time" value={iv.time} onChange={(e) => setIv({ ...iv, time: e.target.value })} /></label>
        <label>Time zone<input value={iv.timezone} onChange={(e) => setIv({ ...iv, timezone: e.target.value })} /></label>
        <label>Meeting link or location<input value={iv.link} onChange={(e) => setIv({ ...iv, link: e.target.value })} /></label>
      </div>
      <button className="primary" disabled={busy || !ready} onClick={() => act(() => api.shortlist(t, { approved_ids: [...picked], interview: iv, override_reason: reason }))}>
        {busy ? "Sending invitations..." : `Approve ${picked.size} candidate(s) and send interview invitations`}</button>
    </div>
  );
}
