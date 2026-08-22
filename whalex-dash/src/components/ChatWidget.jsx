import { useEffect, useRef, useState } from "react";
import { MessageCircle, X, Send } from "lucide-react";
import { api } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { useAuth } from "../context/AuthContext.jsx";

/**
 * 💬 محادثة مباشرة — تستخدم نظام الدعم القائم (/api/support).
 *    الردّ الآليّ فوريّ، وما لا يعرفه النظام يصل للإدارة.
 */
export default function ChatWidget() {
  const { lang } = useLang();
  const { user } = useAuth();
  const ar = lang !== "en";
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  // 🧹 الردود مكتوبة بـHTML لتيليجرام — ننظّفها للعرض هنا
  const clean = (t) => String(t || "")
    .replace(/<[^>]+>/g, "")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");

  // 🔑 AuthContext يسمّيه uid لا id — بدونه تُحفظ الرسائل باسم زائر
  const uid = user?.uid || user?.id || localStorage.getItem("wx_uid") || "guest";

  const load = () =>
    api.get(`/api/support/history?user_id=${uid}&limit=40`)
      .then((r) => setMsgs(r?.messages || []))
      .catch(() => {});

  // 🔄 تحديث دوريّ أثناء فتح النافذة — ردّ الإدارة يصل بلا إغلاق وفتح
  useEffect(() => {
    if (!open) return;
    load();
    const iv = setInterval(load, 8000);
    return () => clearInterval(iv);
  }, [open]);
  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, open]);

  const send = async () => {
    const t = text.trim();
    if (!t || busy) return;
    setBusy(true);
    setMsgs((m) => [...m, { message: t, reply: null, created_at: Date.now() / 1000 }]);
    setText("");
    try {
      await api.post("/api/support/ask", { user_id: uid, message: t, lang });
      setTimeout(load, 600);
    } catch { /* الرسالة محفوظة عندنا على أي حال */ }
    finally { setBusy(false); }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label="chat"
        title={ar ? "تواصل معنا" : "Chat with us"}
        style={{
          position: "fixed",
          bottom: "calc(env(safe-area-inset-bottom, 0px) + 82px)",
          insetInlineEnd: 18, width: 48, height: 48, borderRadius: "50%",
          display: open ? "none" : "grid", placeItems: "center",
          background: "var(--brand, #2dd4bf)", color: "#04121a",
          border: "none", cursor: "pointer", zIndex: 880,
          boxShadow: "0 6px 22px rgba(45,212,191,.35)",
        }}
      >
        <MessageCircle size={22} strokeWidth={2.2} />
      </button>

      {open && (
        <div style={{
          position: "fixed",
          bottom: "calc(env(safe-area-inset-bottom, 0px) + 82px)",
          insetInlineEnd: 16, width: "min(360px, calc(100vw - 32px))",
          height: "min(480px, 70vh)", zIndex: 900,
          background: "var(--bg-1)", borderRadius: 16,
          border: "1px solid var(--bg-3)",
          boxShadow: "0 18px 50px rgba(0,0,0,.5)",
          display: "flex", flexDirection: "column", overflow: "hidden",
        }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 9,
            padding: "13px 15px", borderBottom: "1px solid var(--bg-3)",
            background: "rgba(45,212,191,.06)",
          }}>
            <MessageCircle size={17} style={{ color: "var(--brand)" }} />
            <span style={{ flex: 1, fontSize: 13.5, fontWeight: 800 }}>
              {ar ? "تواصل معنا" : "Chat with us"}
            </span>
            <button onClick={() => setOpen(false)} style={{
              background: "transparent", border: "none", cursor: "pointer",
              color: "var(--txt-2)", display: "flex", padding: 2,
            }}><X size={17} /></button>
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: "14px 13px" }}>
            {msgs.length === 0 && (
              <div style={{
                fontSize: 12.5, color: "var(--txt-3)", textAlign: "center",
                padding: "24px 12px", lineHeight: 1.9,
              }}>
                {ar
                  ? "اسألنا عن أي شيء — الاشتراك، ربط المنصّة، التداول الآلي."
                  : "Ask us anything — subscription, linking an exchange, auto-trading."}
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} style={{ marginBottom: 13 }}>
                <div style={{
                  marginInlineStart: "auto", maxWidth: "85%", width: "fit-content",
                  background: "rgba(45,212,191,.13)", borderRadius: "13px 13px 4px 13px",
                  padding: "9px 12px", fontSize: 12.5, color: "var(--txt-1)",
                  lineHeight: 1.7,
                }}>{m.message}</div>
                {m.reply && (
                  <div style={{
                    marginTop: 7, maxWidth: "85%", width: "fit-content",
                    background: "var(--bg-2)", borderRadius: "13px 13px 13px 4px",
                    padding: "9px 12px", fontSize: 12.5, color: "var(--txt-2)",
                    lineHeight: 1.75,
                  }}>🐋 {clean(m.reply)}</div>
                )}
              </div>
            ))}
            <div ref={endRef} />
          </div>

          <div style={{
            display: "flex", gap: 8, padding: "11px 12px",
            borderTop: "1px solid var(--bg-3)",
          }}>
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") send(); }}
              placeholder={ar ? "اكتب رسالتك…" : "Type your message…"}
              style={{
                flex: 1, padding: "10px 13px", borderRadius: 11,
                background: "rgba(255,255,255,.04)", border: "1px solid var(--bg-3)",
                color: "var(--txt-1)", fontSize: 12.5, outline: "none",
              }}
            />
            <button onClick={send} disabled={busy} style={{
              width: 40, borderRadius: 11, border: "none", cursor: "pointer",
              background: "var(--brand)", color: "#04121a",
              display: "grid", placeItems: "center",
            }}><Send size={16} /></button>
          </div>
        </div>
      )}
    </>
  );
}
