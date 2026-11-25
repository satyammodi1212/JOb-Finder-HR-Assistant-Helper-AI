import { createContext, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";

const Ctx = createContext(null);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!getToken()) return setReady(true);
    api.me().then(setUser).catch(() => setToken("")).finally(() => setReady(true));
  }, []);
  const signIn = (res) => { setToken(res.token); setUser(res.user); };
  const signOut = () => { setToken(""); setUser(null); };
  return <Ctx.Provider value={{ user, setUser, ready, signIn, signOut }}>{children}</Ctx.Provider>;
}
