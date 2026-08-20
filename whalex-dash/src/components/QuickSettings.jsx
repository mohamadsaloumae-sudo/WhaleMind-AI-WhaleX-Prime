import { useState } from "react";
import { Globe, Volume2, VolumeX } from "lucide-react";
import { useLang } from "../context/LangContext.jsx";

/**
 * ⚙️ اللغة والصوت — مشترك بين القائمة الجانبية وقائمة المزيد.
 *
 * التصميم: مبدّل منزلق (segmented) للّغة، ومفتاح للصوت.
 * المستطيلات المتجاورة كانت تبدو كأزرار نموذج قديم.
 */
export default function QuickSettings() {
  const { lang, setLang } = useLang();
  const ar = lang !== "en";
  const [muted, setMuted] = useState(
    () => localStorage.getItem("wx_sound") === "off"
  );

  function setSound(on) {
    localStorage.setItem("wx_sound", on ? "on" : "off");
    setMuted(!on);
    window.dispatchEvent(new Event("wx-sound"));
  }

  return (
    <div style={{
      marginTop: 16, paddingTop: 14,
      borderTop: "1px solid rgba(255,255,255,.06)",
      display: "flex", flexDirection: "column", gap: 12,
    }}>
      {/* 🌐 اللغة — مبدّل منزلق */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <Globe size={15} style={{ color: "var(--txt-3, #6b7688)", flexShrink: 0 }} />
        <span style={{ fontSize: 12, color: "var(--txt-3, #6b7688)", flex: 1 }}>
          {ar ? "اللغة" : "Language"}
        </span>
        <div style={{
          position: "relative", display: "flex",
          background: "rgba(255,255,255,.05)", borderRadius: 9, padding: 2,
        }}>
          <span style={{
            position: "absolute", top: 2, bottom: 2, width: "calc(50% - 2px)",
            insetInlineStart: ar ? 2 : "calc(50% - 0px)",
            background: "var(--brand, #4ade80)", borderRadius: 7,
            transition: "inset-inline-start .22s cubic-bezier(.4,0,.2,1)",
          }} />
          {[["ar", "ع"], ["en", "EN"]].map(([k, txt]) => (
            <button key={k} onClick={() => setLang(k)} style={{
              position: "relative", zIndex: 1, minWidth: 38,
              padding: "5px 0", background: "transparent", border: "none",
              cursor: "pointer", fontSize: 11.5, fontWeight: 800,
              color: lang === k ? "#06131c" : "var(--txt-3, #6b7688)",
              transition: "color .2s",
            }}>{txt}</button>
          ))}
        </div>
      </div>

      {/* 🔊 الصوت — مفتاح */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {muted
          ? <VolumeX size={15} style={{ color: "var(--txt-3, #6b7688)", flexShrink: 0 }} />
          : <Volume2 size={15} style={{ color: "var(--brand, #4ade80)", flexShrink: 0 }} />}
        <span style={{ fontSize: 12, color: "var(--txt-3, #6b7688)", flex: 1 }}>
          {ar ? "صوت التنبيهات" : "Alert sound"}
        </span>
        <button
          onClick={() => setSound(muted)}
          aria-label="sound"
          style={{
            position: "relative", width: 40, height: 22, borderRadius: 22,
            border: "none", cursor: "pointer", padding: 0,
            background: muted ? "rgba(255,255,255,.1)" : "var(--brand, #4ade80)",
            transition: "background .22s",
          }}
        >
          <span style={{
            position: "absolute", top: 3, width: 16, height: 16, borderRadius: 16,
            insetInlineStart: muted ? 3 : 21,
            background: muted ? "var(--txt-3, #6b7688)" : "#06131c",
            transition: "inset-inline-start .22s cubic-bezier(.4,0,.2,1)",
          }} />
        </button>
      </div>
    </div>
  );
}
