import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Login from "./Login";
import HRApp from "./HRApp";
import CandidateApp from "./CandidateApp";

export default function App() {
  const { user, ready } = useAuth();
  if (!ready) return <p className="center">Loading...</p>;
  const home = user ? (user.role === "hr" ? "/hr" : "/candidate") : "/login";
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={home} replace /> : <Login />} />
      <Route path="/hr/*" element={user?.role === "hr" ? <HRApp /> : <Navigate to="/login" replace />} />
      <Route path="/candidate/*" element={user?.role === "candidate" ? <CandidateApp /> : <Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to={home} replace />} />
    </Routes>
  );
}
