// 👋 ترحيب + علم الدولة + السوشيال + مشاركة الرقم
import { useEffect, useState } from "react";
import { useLang } from "../context/LangContext.jsx";

const SOCIALS = [
  { id: "telegram", label: "Telegram", url: "https://t.me/whaleXApp", emoji: "✈️" },
  { id: "youtube",  label: "YouTube",  url: "https://youtube.com/@whalemindhybridai", emoji: "▶️" },
  { id: "x",        label: "X",        url: "https://x.com/Whale_Mind_AI", emoji: "𝕏" },
  { id: "tiktok",   label: "TikTok",   url: "https://tiktok.com/@whalemind.ai.bot", emoji: "🎵" },
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
              width: 40, height: 40, borderRadius: 12, display: "grid", placeItems: "center",
              background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)",
              fontSize: 17, textDecoration: "none",
            }}>{s.emoji}</a>
        ))}
      </div>
    </div>
  );
}
