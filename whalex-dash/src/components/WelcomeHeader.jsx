// 👋 ترحيب + علم الدولة + السوشيال + مشاركة الرقم
import { useEffect, useState } from "react";
import { useLang } from "../context/LangContext.jsx";

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
  tiktok: (
    <svg viewBox="0 0 24 24" width="19" height="19" fill="#ffffff">
      <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/>
    </svg>
  ),
};

const SOCIALS = [
  { id: "telegram", label: "Telegram", url: "https://t.me/whaleXApp",                     bg: "rgba(34,158,217,0.14)" },
  { id: "youtube",  label: "YouTube",  url: "https://youtube.com/@whalemindhybridai",     bg: "rgba(255,0,0,0.12)" },
  { id: "x",        label: "X",        url: "https://x.com/Whale_Mind_AI",                bg: "rgba(255,255,255,0.08)" },
  { id: "tiktok",   label: "TikTok",   url: "https://tiktok.com/@whalemind.ai.bot",       bg: "rgba(255,255,255,0.08)" },
];

function uid() {
  try {
    const t = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
    if (t) return String(t);
  } catch { /* */ }
  let v = localStorage.getItem("wx_uid");
  if (!v) { v = "u" + Math.random().toString(36).slice(2, 10); localStorage.setItem("wx_uid", v); }
  return v;
}

function tgName() {
  try {
    const u = window.Telegram?.WebApp?.initDataUnsafe?.user;
    if (u) return [u.first_name, u.last_name].filter(Boolean).join(" ") || u.username || "";
  } catch { /* */ }
  return localStorage.getItem("wx_name") || "";
}

export default function WelcomeHeader() {
  const { lang } = useLang();
  const ar = lang === "ar";
  const [p, setP] = useState({});
  const [askPhone, setAskPhone] = useState(false);

  useEffect(() => {
    const id = uid(), name = tgName();
    fetch("/api/profile/track", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: id, name }),
    }).catch(() => {});
    fetch(`/api/profile/me?user_id=${encodeURIComponent(id)}`)
      .then((r) => r.json())
      .then((d) => { setP(d || {}); setAskPhone(!d?.phone); })
      .catch(() => {});
  }, []);

  async function sharePhone() {
    try {
      const tg = window.Telegram?.WebApp;
      if (tg?.requestContact) {
        tg.requestContact(async (ok, res) => {
          let phone = "";
          try {
            const raw = res?.responseUnsafe?.contact?.phone_number || res?.contact?.phone_number;
            phone = raw || "";
          } catch { /* */ }
          if (!phone) return;
          await fetch("/api/profile/phone", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: uid(), phone }),
          });
          setAskPhone(false);
          setP((x) => ({ ...x, phone }));
        });
        return;
      }
    } catch { /* */ }
    const manual = prompt(ar ? "أدخل رقم واتساب مع رمز الدولة" : "Enter your WhatsApp number with country code");
    if (manual && manual.trim().length > 6) {
      await fetch("/api/profile/phone", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: uid(), phone: manual.trim() }),
      });
      setAskPhone(false);
      setP((x) => ({ ...x, phone: manual.trim() }));
    }
  }

  const name = p.name || tgName() || (ar ? "صديقنا" : "friend");

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 11, marginBottom: 12 }}>
        <span style={{ fontSize: 30, lineHeight: 1 }}>{p.flag || "🌍"}</span>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 16.5, fontWeight: 800, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {ar ? `أهلاً ${name}` : `Welcome, ${name}`}
          </div>
          <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 2 }}>
            {[p.city, p.country].filter(Boolean).join(" · ") || "WhaleX Prime 🐋"}
          </div>
        </div>
      </div>

      {askPhone && (
        <div onClick={sharePhone} style={{
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10,
          padding: "11px 13px", borderRadius: 12, marginBottom: 12, cursor: "pointer",
          background: "rgba(37,211,102,0.10)", border: "1px solid rgba(37,211,102,0.25)",
        }}>
          <div style={{ fontSize: 12.5, lineHeight: 1.6, minWidth: 0 }}>
            <b style={{ color: "#25D366" }}>📱 {ar ? "انضم لمجموعة واتساب" : "Join our WhatsApp group"}</b>
            <div style={{ color: "var(--txt-3)", fontSize: 11.5 }}>
              {ar ? "شارك رقمك لنضيفك ونرسل لك التنبيهات" : "Share your number to get added and receive alerts"}
            </div>
          </div>
          <span style={{
            flexShrink: 0, background: "#25D366", color: "#04140a", borderRadius: 9,
            padding: "8px 14px", fontSize: 12, fontWeight: 700,
          }}>{ar ? "مشاركة" : "Share"}</span>
        </div>
      )}

      <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
        {SOCIALS.map((s) => (
          <a key={s.id} href={s.url} target="_blank" rel="noreferrer" title={s.label}
            style={{
              width: 42, height: 42, borderRadius: 13, display: "grid", placeItems: "center",
              background: s.bg, border: "1px solid rgba(255,255,255,0.09)",
              textDecoration: "none", transition: "transform .15s",
            }}>{ICONS[s.id]}</a>
        ))}
      </div>
    </div>
  );
}
