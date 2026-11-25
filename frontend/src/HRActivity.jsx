import { useEffect, useState } from "react";
import { api } from "./api";
import { when } from "./util";

const TEXT = {
  hiring_started: "started a hiring request", jd_generated: "wrote a job description draft", jd_approved: "approved the job description",
  jd_rejected: "rejected the job description", jd_published: "published the job on the Candidate Dashboard",
  applications_counted: "counted applications", application_submitted: "applied for the job", applications_imported: "imported applications",
  jd_modified: "revised the job description (fewer applications than needed)", resumes_screened: "screened resumes",
  shortlist_approved: "approved the shortlist", candidate_selected: "selected a candidate for an offer",
  offer_accepted: "accepted the offer", offer_declined: "declined the offer", offer_no_reply: "offer expired without a reply",
  offer_letter_created: "created an offer letter", external_post_recorded: "recorded an external job post", job_details_edited: "edited job details",
  low_apps_review: "chose to review the available applicants", low_apps_extend: "chose to extend recruiting",
};

export default function HRActivity() {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    const load = () => api.activity().then(setRows).catch(() => {});
    load();
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, []);
  return (
    <main className="page">
      <h2>Live activity <span className="muted">updates every few seconds</span></h2>
      {rows.length === 0 && <p className="empty">No activity yet.</p>}
      <ul className="feed">
        {rows.map((r) => (
          <li key={r.id}>
            <span className="time">{when(r.ts)}</span>
            <span className={"actor " + r.actor}>{r.actor}</span>
            <span>{r.payload.name ? <b>{r.payload.name} </b> : null}{TEXT[r.action] || r.action.replaceAll("_", " ")}
              {r.payload.count != null ? ` (${r.payload.count})` : ""}
              {r.title ? <span className="muted"> - {r.title}</span> : null}
              {r.payload.feedback ? <span className="muted"> - "{r.payload.feedback}"</span> : null}</span>
          </li>
        ))}
      </ul>
    </main>
  );
}
