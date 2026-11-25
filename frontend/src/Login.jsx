import { useState } from "react";
import { api } from "./api";
import { useAuth } from "./auth";

export default function Login() {
  const { signIn } = useAuth();
  const [mode, setMode] = useState("login");
  const [role, setRole] = useState("candidate");
  const [f, setF] = useState({ name: "", email: "", password: "", invite_code: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      signIn(mode === "login" ? await api.login({ email: f.email, password: f.password }) : await api.register({ ...f, role }));
    } catch (x) { setErr(x.message); }
    setBusy(false);
  };

  return (
    <div className="login">
      <form className="card" onSubmit={submit}>
        <h1>S.K A.I Development</h1>
        <p className="muted">H.R Assistant A.I - hiring made simple</p>
        <div className="tabs">
          <button type="button" className={mode === "login" ? "on" : ""} onClick={() => setMode("login")}>Log in</button>
          <button type="button" className={mode === "register" ? "on" : ""} onClick={() => setMode("register")}>Create account</button>
        </div>
        {mode === "register" && (
          <>
            <label>I am a
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="candidate">Candidate / student looking for a job</option>
                <option value="hr">HR manager (invitation needed)</option>
              </select>
            </label>
            <label>Full name<input required value={f.name} onChange={set("name")} /></label>
          </>
        )}
        <label>Email<input required type="email" value={f.email} onChange={set("email")} /></label>
        <label>Password<input required type="password" minLength={mode === "register" ? 8 : 1} value={f.password} onChange={set("password")} /></label>
        {mode === "register" && role === "hr" && (
          <label>Organization invitation code<input required value={f.invite_code} onChange={set("invite_code")} /></label>
        )}
        {err && <p className="error">{err}</p>}
        <button className="primary" disabled={busy}>{busy ? "Please wait..." : mode === "login" ? "Log in" : "Create account"}</button>
        <p className="muted">Demo: hr@demo.com or candidate@demo.com, password Demo@1234 (after running the seed script).</p>
      </form>
    </div>
  );
}
