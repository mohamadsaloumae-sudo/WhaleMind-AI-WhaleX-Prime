import { useState } from "react";
import { Globe, Volume2, VolumeX } from "lucide-react";
import { useLang } from "../context/LangContext.jsx";

// شعارات التواصل — منقولة كما هي من الصفحة الرئيسية بلا مربعات
const WA_CHANNEL = "https://whatsapp.com/channel/0029Vb8KTaF6RGJFztzS0Q3K";

const DIAL = {
  AE: "+971", SA: "+966", EG: "+20", KW: "+965", QA: "+974", BH: "+973", OM: "+968",
  JO: "+962", LB: "+961", IQ: "+964", SY: "+963", YE: "+967", PS: "+970", MA: "+212",
  DZ: "+213", TN: "+216", LY: "+218", SD: "+249", TR: "+90", US: "+1", GB: "+44",
  DE: "+49", FR: "+33", IN: "+91", PK: "+92", ID: "+62", MY: "+60", NG: "+234",
};

const ICONS = {
  telegram: (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="#229ED9">
      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.568 8.16c-.169 1.858-.896 6.728-.896 6.728-.169.896-.896 1.12-1.456.784l-2.688-1.96-1.288 1.232c-.169.169-.336.336-.672.336l.224-3.024 5.32-4.816c.224-.224-.056-.336-.336-.168l-6.552 4.144-2.856-.896c-.616-.224-.616-.616.112-.896l11.2-4.312c.504-.168.952.112.784.848z"/>
    </svg>
  ),
  youtube: (
    <svg viewBox="0 0 24 24" width="21" height="21" fill="#FF0000">
      <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
    </svg>
  ),
  x: (
    <svg viewBox="0 0 24 24" width="17" height="17" fill="#ffffff">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
    </svg>
  ),
  whatsapp: (
    <svg viewBox="0 0 24 24" width="21" height="21" fill="#25D366">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51a12.8 12.8 0 0 0-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.71.306 1.263.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893A11.821 11.821 0 0 0 20.885 3.4"/>
    </svg>
  ),
  tiktok: (
    <svg viewBox="0 0 24 24" width="19" height="19" fill="#ffffff">
      <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/>
    </svg>
  ),
};

const SOCIALS = [
  { id: "telegram", label: "Telegram", url: "https://t.me/whaleXApp" },
  { id: "youtube",  label: "YouTube",  url: "https://youtube.com/@whalemindhybridai" },
  { id: "x",        label: "X",        url: "https://x.com/Whale_Mind_AI" },
  { id: "tiktok",   label: "TikTok",   url: "https://tiktok.com/@whalemind.ai.bot" },
  { id: "whatsapp", label: "WhatsApp", url: WA_CHANNEL },
];

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

      <div style={{
        display: "flex", justifyContent: "center", gap: 22,
        marginTop: 6, paddingTop: 14,
        borderTop: "1px solid rgba(255,255,255,.06)",
      }}>
        {SOCIALS.map((s) => (
          <a key={s.id} href={s.url} target="_blank" rel="noreferrer" title={s.label}
             style={{ width: 22, height: 22, display: "flex", opacity: .62,
                      transition: "opacity .2s, transform .2s" }}
             onMouseEnter={(e) => {
               e.currentTarget.style.opacity = 1;
               e.currentTarget.style.transform = "translateY(-2px)";
             }}
             onMouseLeave={(e) => {
               e.currentTarget.style.opacity = .62;
               e.currentTarget.style.transform = "none";
             }}>
            {DIAL[s.id]}
          </a>
        ))}
      </div>
    </div>
  );
}
