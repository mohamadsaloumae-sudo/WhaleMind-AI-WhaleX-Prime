// 💬 الدعم الفني — شاشة كاملة
import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Send, ArrowRight, ArrowLeft } from "lucide-react";
import { useLang } from "../context/LangContext.jsx";

const uid = () => {
  try {
    const tg = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
    if (tg) return String(tg);
  } catch { /* */ }
  let v = localStorage.getItem("wx_uid");
  if (!v) { v = "u" + Math.random().toString(36).slice(2, 10); localStorage.setItem("wx_uid", v); }
  return v;
};



export default function Support() {
  const { lang } = useLang();
  const ar = lang === "ar";
  const nav = useNavigate();
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);
  const [topics, setTopics] = useState([]);
  const [showTopics, setShowTopics] = useState(true);

  useEffect(() => {
    fetch(`/api/support/history?user_id=${uid()}`)
      .then((r) => r.json())
      .then((d) => {
        const list = [];
        (d.messages || []).forEach((m) => {
          list.push({ me: true, text: m.message });
          if (m.reply) list.push({ me: false, text: m.reply });
        });
        setMsgs(list);
      })
      .catch(() => {});
  }, []);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  useEffect(() => {
    fetch(`/api/support/topics?lang=${lang}`)
      .then((r) => r.json())
      .then((d) => setTopics(d.topics || []))
      .catch(() => {});
  }, [lang]);

  async function send(q0) {
    const q = (q0 ?? text).trim();
    if (!q || busy) return;
    if (!q0) setText("");
    setMsgs((m) => [...m, { me: true, text: q }]);
    setBusy(true);
    try {
      const r = await fetch("/api/support/ask", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: q, user_id: uid(), lang }),
      });
      const d = await r.json();
      setMsgs((m) => [...m, {
        me: false,
        text: d.reply || d.menu || (ar ? "📩 وصل سؤالك لفريق الدعم." : "📩 Sent to support."),
        note: !d.reply,
      }]);
    } catch {
      setMsgs((m) => [...m, { me: false, text: ar ? "⚠️ تعذّر الإرسال." : "⚠️ Failed to send." }]);
    }
    setBusy(false);
  }

  const Back = ar ? ArrowRight : ArrowLeft;

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000, display: "flex", flexDirection: "column",
      background: "var(--bg-1, #0b0e16)",
      paddingTop: "env(safe-area-inset-top, 0px)", paddingBottom: "env(safe-area-inset-bottom, 0px)",
    }}>
      <header style={{
        display: "flex", alignItems: "center", gap: 10, padding: "12px 14px",
        borderBottom: "1px solid rgba(255,255,255,0.07)", flexShrink: 0,
      }}>
        <button onClick={() => nav(-1)} aria-label="back" style={{
          background: "rgba(255,255,255,0.06)", border: "none", color: "inherit",
          width: 34, height: 34, borderRadius: 10, display: "grid", placeItems: "center", cursor: "pointer",
        }}><Back size={18} /></button>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>{ar ? "الدعم الفني" : "Support"}</div>
          <div style={{ fontSize: 11, color: "var(--brand)" }}>{ar ? "● متصل" : "● Online"}</div>
        </div>
      </header>

      <div style={{ flex: 1, overflowY: "auto", padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
        {msgs.length === 0 && (
          <div style={{ textAlign: "center", color: "var(--txt-3)", fontSize: 13, marginTop: 30, lineHeight: 2 }}>
            {ar ? "👋 مرحباً بك\nاسأل عن أي شيء يخصّ النظام" : "👋 Welcome\nAsk anything about the system"}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} style={{
            alignSelf: m.me ? "flex-end" : "flex-start",
            maxWidth: "86%", padding: "11px 14px", borderRadius: 14,
            background: m.me ? "rgba(74,222,128,0.15)" : "rgba(255,255,255,0.06)",
            color: m.me ? "var(--brand)" : "var(--txt-1)",
            fontSize: 13.5, lineHeight: 1.85, wordBreak: "break-word",
          }}
            dangerouslySetInnerHTML={{ __html: String(m.text).replace(/\n/g, "<br/>") }}
          />
        ))}
        {busy && <div style={{ alignSelf: "flex-start", fontSize: 12, color: "var(--txt-3)" }}>···</div>}
        <div ref={endRef} />
      </div>

      <div style={{ borderTop: "1px solid rgba(255,255,255,0.07)", flexShrink: 0 }}>
        <button
          onClick={() => setShowTopics((v) => !v)}
          style={{
            width: "100%", background: "transparent", border: "none", color: "var(--txt-3)",
            padding: "9px 14px", fontSize: 12, cursor: "pointer", textAlign: "start",
            display: "flex", justifyContent: "space-between", alignItems: "center",
          }}
        >
          <span>{ar ? "❓ الأسئلة الشائعة" : "❓ Common questions"}</span>
          <span style={{ fontSize: 11 }}>{showTopics ? "▲" : "▼"}</span>
        </button>
        {showTopics && (
          <div style={{
            display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6,
            padding: "0 12px 10px", maxHeight: "30vh", overflowY: "auto",
          }}>
            {topics.map((t) => (
              <button key={t} onClick={() => send(t)} style={{
                background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.09)",
                color: "var(--txt-2)", borderRadius: 10, padding: "10px 9px", fontSize: 11.5,
                cursor: "pointer", textAlign: "start", lineHeight: 1.5,
              }}>{t}</button>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 8, padding: 12, borderTop: "1px solid rgba(255,255,255,0.07)", flexShrink: 0 }}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={ar ? "اكتب سؤالك..." : "Type your question..."}
          style={{
            flex: 1, minWidth: 0, background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.09)", borderRadius: 11,
            padding: "12px 14px", color: "inherit", fontSize: 13.5, outline: "none",
          }}
        />
        <button onClick={() => send()} disabled={busy} style={{
          background: "var(--brand, #4ade80)", border: "none", borderRadius: 11,
          width: 46, display: "grid", placeItems: "center", cursor: "pointer",
          opacity: busy ? 0.5 : 1, color: "#06110a", flexShrink: 0,
        }}><Send size={18} /></button>
      </div>
    </div>
  );
}
