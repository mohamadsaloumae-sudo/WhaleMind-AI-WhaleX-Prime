// الإعدادات
import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { useLang } from "../context/LangContext.jsx";
import { User, Shield, LogOut, Bell, BellOff } from "lucide-react";
import { enablePush, disablePush, isPushEnabled, pushSupported } from "../lib/pushSetup.js";

export default function Settings() {
  const { user, logout } = useAuth();
  const { t } = useLang();
  const [pushOn, setPushOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  useEffect(() => { isPushEnabled().then(setPushOn); }, []);

  async function toggle() {
    setBusy(true); setNote("");
    if (pushOn) {
      const r = await disablePush();
      if (r.ok) { setPushOn(false); setNote(t("notifOffMsg")); }
      else setNote("⚠️ " + (r.error || ""));
    } else {
      const r = await enablePush();
      if (r.ok) { setPushOn(true); setNote(t("notifOnMsg")); }
      else setNote("⚠️ " + (r.error || ""));
    }
    setBusy(false);
  }

  return (
    <div style={{ maxWidth: 560 }}>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title"><User size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("account")}</div>
        <div style={{ display: "grid", gap: 12, fontSize: 14 }}>
          <div className="toggle-row" style={{ margin: 0 }}>
            <span style={{ color: "var(--txt-2)" }}>{t("userId")}</span>
            <span style={{ fontFamily: "monospace" }}>{user?.uid}</span>
          </div>
          <div className="toggle-row" style={{ margin: 0 }}>
            <span style={{ color: "var(--txt-2)" }}>{t("plan")}</span>
            <span className="badge grade">{user?.tier}</span>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title"><Bell size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("notifTitle")}</div>
        <p style={{ fontSize: 13.5, color: "var(--txt-2)", marginBottom: 16 }}>{t("notifDesc")}</p>
        {!pushSupported() ? (
          <p style={{ fontSize: 13, color: "var(--txt-3)" }}>{t("notifUnsupported")}</p>
        ) : (
          <button className="btn" onClick={toggle} disabled={busy}
            style={{ background: pushOn ? "transparent" : "var(--brand)",
                     color: pushOn ? "var(--txt-2)" : "#071520",
                     border: pushOn ? "1px solid var(--brand-dim)" : "none", fontWeight: 700 }}>
            {pushOn ? <BellOff size={16} /> : <Bell size={16} />}
            {busy ? "..." : (pushOn ? t("notifDisable") : t("notifEnable"))}
          </button>
        )}
        {note && <p style={{ fontSize: 13, marginTop: 12 }}>{note}</p>}
      </div>

      <div className="card">
        <div className="card-title"><Shield size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("security")}</div>
        <p style={{ fontSize: 13.5, color: "var(--txt-2)", marginBottom: 16 }}>{t("securityDesc")}</p>
        <button className="btn btn-danger" onClick={logout}><LogOut size={16} /> {t("logout")}</button>
      </div>
    </div>
  );
}
