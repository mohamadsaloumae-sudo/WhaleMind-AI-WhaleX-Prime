// ════════════════════════════════════════════════════════════
//  سياق المصادقة (Auth Context)
//  يحفظ حالة المستخدم (التوكن، الباقة) عبر التطبيق.
// ════════════════════════════════════════════════════════════
import { createContext, useContext, useState, useEffect } from "react";
import { getToken, setToken } from "../lib/api.js";

const AuthCtx = createContext(null);

function decodeTier(token) {
  // قراءة tier من JWT (الجزء الأوسط) دون مكتبة
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return { tier: payload.tier || "free", uid: payload.sub, exp: payload.exp };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const t = getToken();
    if (t) {
      const info = decodeTier(t);
      if (info && info.exp * 1000 > Date.now()) setUser(info);
      else setToken("");
    }
    setReady(true);
  }, []);

  function login(token) {
    setToken(token);
    setUser(decodeTier(token));
  }
  function logout() {
    setToken("");
    setUser(null);
  }

  return (
    <AuthCtx.Provider value={{ user, ready, login, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth() {
  return useContext(AuthCtx);
}
