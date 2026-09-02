// صفحة الدخول والتسجيل
import { useState } from "react";
import { auth } from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import { useLang } from "../context/LangContext.jsx";
import { Waves, Languages, Eye, EyeOff, Send, RefreshCw } from "lucide-react";

export default function Login() {
  const { login } = useAuth();
  const { t, lang, toggle } = useLang();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [email, setEmail] = useState("");
  // 🎁 كود الإحالة — من الرابط أو يدوياً
  const [refCode, setRefCode] = useState(() => {
    try { return localStorage.getItem("wx_ref") || ""; } catch { return ""; }
  });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  // استرجاع كلمة السر
  const [resetStep, setResetStep] = useState(0);
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [resetMsg, setResetMsg] = useState("");

  // الربط الإجباري بعد التسجيل
  const [linkData, setLinkData] = useState(null); // {link_code, bot}
  const [showManual, setShowManual] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      if (mode === "login") {
        const res = await auth.login(username.trim(), password);
        login(res.access_token);
      } else {
        const res = await auth.register(username.trim(), password, email.trim(),
          refCode.trim().toUpperCase() ||
            (localStorage.getItem("wx_ref") || ""));
        if (res.needs_link) {
          setLinkData({ code: res.link_code, bot: res.bot });
        } else if (res.access_token) {
          login(res.access_token);
        }
      }
    } catch (e) {
      setErr(e.message || "فشل");
    } finally {
      setBusy(false);
    }
  }

  async function checkLink() {
    setErr(""); setBusy(true);
    try {
      const res = await auth.linkStatus(username.trim());
      if (res.linked && res.access_token) {
        login(res.access_token);
      } else {
        setErr(lang === "ar" ? "لم يتم الربط بعد. أرسل الرمز للبوت أولاً." : "Not linked yet. Send the code to the bot first.");
      }
    } catch (e) {
      setErr(e.message || "فشل");
    } finally {
      setBusy(false);
    }
  }

  async function sendResetCode(e) {
    e.preventDefault();
    setErr(""); setResetMsg(""); setBusy(true);
    try {
      const res = await auth.forgot(username.trim());
      if (res.sent) {
        setResetStep(1);
        setResetMsg(lang === "ar" ? "تم إرسال الرمز عبر تيليجرام" : "Code sent via Telegram");
      } else {
        setErr(res.reason || (lang === "ar" ? "تعذّر إرسال الرمز" : "Failed to send code"));
      }
    } catch (e) {
      setErr(e.message || "فشل");
    } finally {
      setBusy(false);
    }
  }

  async function doReset(e) {
    e.preventDefault();
    setErr(""); setResetMsg(""); setBusy(true);
    try {
      await auth.resetPassword(username.trim(), code, newPassword);
      setResetMsg(lang === "ar" ? "تم تغيير كلمة السر! سجّل الدخول الآن" : "Password changed! Login now");
      setResetStep(0);
      setMode("login");
      setPassword(""); setCode(""); setNewPassword("");
    } catch (e) {
      setErr(e.message || "فشل");
    } finally {
      setBusy(false);
    }
  }

  function backToLogin() {
    setMode("login"); setResetStep(0); setErr(""); setResetMsg("");
    setCode(""); setNewPassword(""); setLinkData(null);
  }

  return (
    <div className="wx-auth" style={{
      minHeight: "100vh", display: "flex", alignItems: "center",
      justifyContent: "center", padding: 20,
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

        {linkData ? (
          <>
            <div style={{ textAlign: "center", marginBottom: 16, fontSize: 17, fontWeight: 700 }}>
              {lang === "ar" ? "🔗 تفعيل الحساب" : "🔗 Activate Account"}
            </div>
            <p style={{ fontSize: 13, color: "var(--txt-2)", lineHeight: 1.8, marginBottom: 20, textAlign: "center" }}>
              {lang === "ar"
                ? "لحماية حسابك واسترجاع كلمة السر عند نسيانها، اربط تيليجرام بضغطة واحدة."
                : "To protect your account and recover your password, link Telegram in one tap."}
            </p>
            <a href={`https://t.me/${linkData.bot}?start=${linkData.code}`} target="_blank" rel="noreferrer"
               className="btn btn-primary btn-block" style={{ marginBottom: 12, textDecoration: "none", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, fontSize: 15, padding: "14px" }}>
              <Send size={18} /> {lang === "ar" ? "فتح البوت والربط" : "Open Bot & Link"}
            </a>
            <p style={{ fontSize: 12, color: "var(--txt-3)", textAlign: "center", marginBottom: 20, lineHeight: 1.6 }}>
              {lang === "ar" ? "اضغط «START» داخل البوت، ثم ارجع هنا." : "Tap «START» in the bot, then come back here."}
            </p>
            {err && <div className="alert error">{err}</div>}
            <button onClick={checkLink} disabled={busy} className="btn btn-primary btn-block" style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "14px" }}>
              <RefreshCw size={18} /> {busy ? t("processing") : (lang === "ar" ? "تم! ادخل حسابي ✓" : "Done! Enter my account ✓")}
            </button>
            <button onClick={() => setShowManual(!showManual)} style={{ background: "none", border: "none", color: "var(--txt-3)", cursor: "pointer", fontSize: 12, marginTop: 16, width: "100%" }}>
              {lang === "ar" ? "لم يعمل الربط؟" : "Linking didn't work?"}
            </button>
            {showManual && (
              <div style={{ fontSize: 12, color: "var(--txt-3)", background: "#0a0e1a", borderRadius: 8, padding: "10px 12px", textAlign: "center", marginTop: 8, lineHeight: 1.7 }}>
                {lang === "ar" ? "افتح البوت وأرسل هذا الأمر يدوياً:" : "Open the bot and send this command manually:"}
                <br />
                <span style={{ fontFamily: "monospace", color: "var(--brand)", userSelect: "all", fontSize: 14 }}>/link {linkData.code}</span>
              </div>
            )}
            <button onClick={backToLogin} style={{ background: "none", border: "none", color: "var(--txt-3)", cursor: "pointer", fontSize: 13, marginTop: 14, width: "100%" }}>
              {lang === "ar" ? "← إلغاء" : "← Cancel"}
            </button>
          </>
        ) : mode === "forgot" ? (
          <>
            <div style={{ textAlign: "center", marginBottom: 16, fontSize: 16, fontWeight: 700 }}>
              {lang === "ar" ? "استرجاع كلمة السر" : "Reset Password"}
            </div>
            {resetMsg && <div className="alert" style={{ background: "rgba(34,197,94,0.15)", color: "#22c55e", padding: "10px 14px", borderRadius: 8, marginBottom: 12, fontSize: 13 }}>{resetMsg}</div>}
            {err && <div className="alert error">{err}</div>}
            {resetStep === 0 ? (
              <form onSubmit={sendResetCode}>
                <div className="field">
                  <label>{t("username")}</label>
                  <input value={username} onChange={(e) => setUsername(e.target.value)} required />
                </div>
                <p style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 12 }}>
                  {lang === "ar" ? "سيصلك رمز عبر تيليجرام (يجب ربط حسابك أولاً)" : "You'll receive a code via Telegram"}
                </p>
                <button className="btn btn-primary btn-block" disabled={busy}>
                  {busy ? t("processing") : (lang === "ar" ? "إرسال الرمز" : "Send Code")}
                </button>
              </form>
            ) : (
              <form onSubmit={doReset}>
                <div className="field">
                  <label>{lang === "ar" ? "الرمز (6 أرقام)" : "Code (6 digits)"}</label>
                  <input value={code} onChange={(e) => setCode(e.target.value)} required inputMode="numeric" maxLength={6} />
                </div>
                <div className="field">
                  <label>{lang === "ar" ? "كلمة السر الجديدة" : "New Password"}</label>
                  <div style={{ position: "relative" }}>
                    <input type={showPass ? "text" : "password"} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={6} style={{ paddingInlineEnd: 42 }} />
                    <button type="button" onClick={() => setShowPass(!showPass)} style={{ position: "absolute", insetInlineEnd: 12, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: "var(--txt-3)", cursor: "pointer", padding: 0, display: "flex" }}>
                      {showPass ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>
                <button className="btn btn-primary btn-block" disabled={busy}>
                  {busy ? t("processing") : (lang === "ar" ? "تغيير كلمة السر" : "Change Password")}
                </button>
              </form>
            )}
            <button onClick={backToLogin} style={{ background: "none", border: "none", color: "var(--brand)", cursor: "pointer", fontSize: 13, marginTop: 14, width: "100%" }}>
              {lang === "ar" ? "← رجوع لتسجيل الدخول" : "← Back to Login"}
            </button>
          </>
        ) : (
          <>
            <div className="mode-switch">
              <button className={`mode-btn ${mode === "login" ? "active" : ""}`} onClick={() => setMode("login")}>
                {t("login")}
              </button>
              <button className={`mode-btn ${mode === "register" ? "active" : ""}`} onClick={() => setMode("register")}>
                {t("register")}
              </button>
            </div>
            {err && <div className="alert error">{err}</div>}
            {resetMsg && <div className="alert" style={{ background: "rgba(34,197,94,0.15)", color: "#22c55e", padding: "10px 14px", borderRadius: 8, marginBottom: 12, fontSize: 13 }}>{resetMsg}</div>}
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
              {mode === "register" && (
                <div className="field">
                  <label>{lang === "ar" ? "كود الإحالة (اختياري)"
                                        : "Referral code (optional)"}</label>
                  <input
                    value={refCode}
                    onChange={(e) => setRefCode(e.target.value.toUpperCase())}
                    placeholder="WX000000"
                    autoComplete="off"
                    style={{ direction: "ltr", textTransform: "uppercase" }}
                  />
                </div>
              )}
              <div className="field">
                <label>{t("password")}</label>
                <div style={{ position: "relative" }}>
                  <input type={showPass ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" style={{ paddingInlineEnd: 42 }} />
                  <button type="button" onClick={() => setShowPass(!showPass)} style={{ position: "absolute", insetInlineEnd: 12, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: "var(--txt-3)", cursor: "pointer", padding: 0, display: "flex" }}>
                    {showPass ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>
              {mode === "register" && (
                <p style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 12, lineHeight: 1.6 }}>
                  {lang === "ar"
                    ? "⚠️ بعد التسجيل ستربط حساب تيليجرام (إجباري لاسترجاع كلمة السر)"
                    : "⚠️ After signup you'll link Telegram (required for password recovery)"}
                </p>
              )}
              <button className="btn btn-primary btn-block" disabled={busy}>
                {busy ? t("processing") : mode === "login" ? t("login") : t("createAccount")}
              </button>
              {mode === "login" && (
                <button type="button" onClick={() => { setMode("forgot"); setErr(""); setResetMsg(""); }} style={{ background: "none", border: "none", color: "var(--brand)", cursor: "pointer", fontSize: 13, marginTop: 14, width: "100%" }}>
                  {lang === "ar" ? "نسيت كلمة السر؟" : "Forgot password?"}
                </button>
              )}
            </form>
          </>
        )}
      </div>
    </div>
  );
}
