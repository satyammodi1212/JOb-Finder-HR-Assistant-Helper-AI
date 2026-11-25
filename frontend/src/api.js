let token = localStorage.getItem("token") || "";
export const getToken = () => token;
export const setToken = (t) => {
  token = t || "";
  t ? localStorage.setItem("token", t) : localStorage.removeItem("token");
};

const headers = (json) => ({ ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(json ? { "Content-Type": "application/json" } : {}) });

async function fail(r) {
  const d = await r.json().catch(() => ({}));
  const msg = Array.isArray(d.detail) ? d.detail.map((x) => x.msg).join("; ") : d.detail || r.statusText;
  const e = new Error(msg);
  e.status = r.status;
  throw e;
}
async function req(method, url, body) {
  const isForm = body instanceof FormData;
  const r = await fetch(url, { method, headers: headers(body !== undefined && !isForm), body: body === undefined ? undefined : isForm ? body : JSON.stringify(body) });
  if (!r.ok) await fail(r);
  return r.json();
}
export async function download(url, filename) {
  const r = await fetch(url, { headers: headers(false) });
  if (!r.ok) await fail(r);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(await r.blob());
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 10000);
}

export const api = {
  // accounts
  register: (b) => req("POST", "/api/auth/register", b),
  login: (b) => req("POST", "/api/auth/login", b),
  me: () => req("GET", "/api/auth/me"),
  saveProfile: (b) => req("PUT", "/api/me/profile", b),
  // candidate dashboard
  jobs: (p) => req("GET", "/api/jobs?" + new URLSearchParams(Object.entries(p).filter(([, v]) => v !== "" && v != null))),
  apply: (t, file) => { const f = new FormData(); f.append("file", file); return req("POST", `/api/jobs/${t}/apply`, f); },
  myApps: () => req("GET", "/api/candidate/applications"),
  offerReply: (id, status) => req("POST", `/api/candidate/applications/${id}/offer`, { status }),
  offerLetter: (id) => download(`/api/candidate/applications/${id}/offer-letter`, "offer-letter.pdf"),
  resume: (id, name) => download(`/api/applications/${id}/resume`, name || "resume"),
  // HR tracking
  overview: () => req("GET", "/api/hr/overview"),
  jobApps: (t) => req("GET", `/api/hr/jobs/${t}/applications`),
  jobEmails: (t) => req("GET", `/api/hr/jobs/${t}/emails`),
  activity: () => req("GET", "/api/hr/activity"),
  patchJob: (t, b) => req("PATCH", `/api/hr/jobs/${t}`, b),
  recordChannel: (t, p, url) => req("POST", `/api/hr/jobs/${t}/channels/${encodeURIComponent(p)}`, { url }),
  // HR hiring workflow
  list: () => req("GET", "/api/hiring"),
  get: (t) => req("GET", `/api/hiring/${t}`),
  start: (query) => req("POST", "/api/hiring/start", { query }),
  jdDecision: (t, d) => req("POST", `/api/hiring/${t}/jd-decision`, d),
  lowDecision: (t, action) => req("POST", `/api/hiring/${t}/low-decision`, { action }),
  shortlist: (t, b) => req("POST", `/api/hiring/${t}/shortlist`, b),
  advance: (t) => req("POST", `/api/hiring/${t}/advance`),
  select: (t, selected_id) => req("POST", `/api/hiring/${t}/select`, { selected_id }),
  offer: (t, status) => req("POST", `/api/hiring/${t}/offer`, { status }),
  upload: (t, files, source) => {
    const f = new FormData();
    [...files].forEach((x) => f.append("files", x));
    f.append("source", source);
    return req("POST", `/api/hiring/${t}/resumes`, f);
  },
  remove: (t) => req("DELETE", `/api/hiring/${t}`),
  clearAll: () => req("DELETE", "/api/hiring"),
};
