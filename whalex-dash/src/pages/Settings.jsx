// الإعدادات — أيقونات في صف واحد
import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { useLang } from "../context/LangContext.jsx";
import { LogOut, Bell, BellOff, Languages } from "lucide-react";
import { enablePush, disablePush, isPushEnabled, pushSupported } from "../lib/pushSetup.js";

function Act({ icon, label, on, onClick, danger, busy }) {
  return (
    <button
      onClick={onClick}
      disabled={busy}
      style={{
        background: "none", border: "none", padding: 0,
        cursor: busy ? "wait" : "pointer", opacity: busy ? .5 : 1,
        display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
      }}
    >
      <div style={{
        width: 58, height: 58, borderRadius: 16,
        background: danger ? "rgba(220,72,72,.14)"
          : on ? "rgba(46,160,110,.16)" : "rgba(255,255,255,.06)",
        color: danger ? "#e46767" : on ? "#4bcf92" : "var(--txt-2)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>{icon}</div>
      <span style={{
        fontSize: 11.5, color: "var(--txt-2)", textAlign: "center",
        lineHeight: 1.25, maxWidth: 76,
      }}>{label}</span>
    </button>
  );
}

export default function Settings() {
  const { logout } = useAuth();
  const { t, lang, toggle: swapLang } = useLang();
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
    <div style={{ maxWidth: 560, padding: "4px 2px" }}>
      <div style={{
        display: "flex", gap: 22, flexWrap: "wrap",
        justifyContent: "flex-start", padding: "10px 4px 18px",
      }}>
        {pushSupported() && (
          <Act
            icon={pushOn ? <BellOff size={24} /> : <Bell size={24} />}
            label={pushOn ? t("notifDisable") : t("notifEnable")}
            on={pushOn} onClick={toggle} busy={busy}
          />
        )}
        <Act
          icon={<Languages size={24} />}
          label={lang === "ar" ? "English" : "العربية"}
          onClick={swapLang}
        />
        <Act
          icon={<LogOut size={24} />}
          label={t("logout")}
          danger onClick={logout}
        />
      </div>

      {!pushSupported() && (
        <p style={{ fontSize: 13, color: "var(--txt-3)", padding: "0 4px" }}>
          {t("notifUnsupported")}
        </p>
      )}
      {note && (
        <p style={{ fontSize: 13, color: "var(--txt-2)", padding: "0 4px" }}>
          {note}
        </p>
      )}
    </div>
  );
}
