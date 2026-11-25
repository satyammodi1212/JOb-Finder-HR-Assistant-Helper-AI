import { NavLink, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import HRHiring from "./HRHiring";
import HRJobs from "./HRJobs";
import HRActivity from "./HRActivity";

export default function HRApp() {
  const { user, signOut } = useAuth();
  return (
    <div className="shell">
      <header className="top">
        <b>S.K A.I Development - HR</b>
        <nav>
          <NavLink to="/hr" end>Hiring chat</NavLink>
          <NavLink to="/hr/jobs">Jobs and applicants</NavLink>
          <NavLink to="/hr/activity">Live activity</NavLink>
        </nav>
        <span className="who">{user.name}<button onClick={signOut}>Log out</button></span>
      </header>
      <Routes>
        <Route index element={<HRHiring />} />
        <Route path="jobs" element={<HRJobs />} />
        <Route path="activity" element={<HRActivity />} />
      </Routes>
    </div>
  );
}
