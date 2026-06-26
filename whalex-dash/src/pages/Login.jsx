// صفحة الدخول والتسجيل
import { useState } from "react";
import { auth } from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import { useLang } from "../context/LangContext.jsx";
import { Waves, Languages } from "lucide-react";

export default function Login() {
  const { login } = useAuth();
  const { t, lang, toggle } = useLang();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      const res = mode === "login"
        ? await auth.login(username, password)
        : await auth.register(username, password, email);
      login(res.access_token);
    } catch (e) {
      setErr(e.message || "فشل");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center",
      justifyContent: "center", padding: 20,
      background: "radial-gradient(circle at 50% 0%, #142033, #0a0e1a)",
    }}>
      <button className="lang-btn" onClick={toggle}
              style={{ position: "fixed", top: 18, insetInlineEnd: 18 }}>
        <Languages size={16} /> {lang === "ar" ? "EN" : "ع"}
      </button>

      <div className="card" style={{ width: 400, maxWidth: "100%" }}>
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 10, color: "var(--brand)", fontSize: 28, fontWeight: 800 }}>
            <Waves size={32} /> WhaleX
          </div>
          <p style={{ color: "var(--txt-2)", fontSize: 14, marginTop: 6 }}>
            {t("tagline")}
          </p>
        </div>

        <div className="mode-switch">
          <button className={`mode-btn ${mode === "login" ? "active" : ""}`} onClick={() => setMode("login")}>
            {t("login")}
          </button>
          <button className={`mode-btn ${mode === "register" ? "active" : ""}`} onClick={() => setMode("register")}>
            {t("register")}
          </button>
        </div>

        {err && <div className="alert error">{err}</div>}

        <form onSubmit={submit}>
          <div className="field">
            <label>{t("username")}</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} required autoComplete="username" />
          </div>
          {mode === "register" && (
            <div className="field">
              <label>{t("emailOptional")}</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </div>
          )}
          <div className="field">
            <label>{t("password")}</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
          </div>
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? t("processing") : mode === "login" ? t("login") : t("createAccount")}
          </button>
        </form>
      </div>
    </div>
  );
}
