// 💬 خدمة العملاء
import { useState, useEffect, useRef } from "react";
import { Send } from "lucide-react";
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
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

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

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  async function send() {
    const q = text.trim();
    if (!q || busy) return;
    setText("");
    setMsgs((m) => [...m, { me: true, text: q }]);
    setBusy(true);
    try {
      const r = await fetch("/api/support/ask", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: q, user_id: uid() }),
      });
      const d = await r.json();
      setMsgs((m) => [...m, {
        me: false,
        text: d.reply || (ar
          ? "📩 وصل سؤالك إلى فريق الدعم — سيصلك الرد هنا قريباً."
          : "📩 Your question reached our support team — you will get a reply here shortly."),
      }]);
    } catch {
      setMsgs((m) => [...m, { me: false, text: ar ? "⚠️ تعذّر الإرسال، حاول ثانية." : "⚠️ Failed to send, try again." }]);
    }
    setBusy(false);
  }

  return (
    <>
      <div className="card" style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 205px)", minHeight: 330, padding: 0, overflow: "hidden" }}>
        <div style={{ flex: 1, overflowY: "auto", padding: 14, display: "flex", flexDirection: "column", gap: 9 }}>
          {msgs.length === 0 && (
            <div style={{ textAlign: "center", color: "var(--txt-3)", fontSize: 13, marginTop: 26, lineHeight: 1.9, whiteSpace: "pre-line" }}>
              {ar ? "👋 مرحباً بك في الدعم\nاسأل عن أي شيء: الرادارات، الدرجات، الربط، الاشتراك..."
                  : "👋 Welcome to Support\nAsk anything: radars, grades, linking, subscription..."}
            </div>
          )}
          {msgs.map((m, i) => (
            <div key={i} style={{
              alignSelf: m.me ? "flex-end" : "flex-start",
              maxWidth: "84%", padding: "10px 13px", borderRadius: 13,
              background: m.me ? "rgba(74,222,128,0.14)" : "rgba(255,255,255,0.06)",
              color: m.me ? "var(--brand)" : "var(--txt-1)",
              fontSize: 13.5, lineHeight: 1.75, whiteSpace: "pre-line", wordBreak: "break-word",
            }}>{m.text}</div>
          ))}
          <div ref={endRef} />
        </div>
        <div style={{ display: "flex", gap: 8, padding: 11, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder={ar ? "اكتب سؤالك..." : "Type your question..."}
            style={{
              flex: 1, minWidth: 0, background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.09)", borderRadius: 10,
              padding: "11px 13px", color: "inherit", fontSize: 13.5, outline: "none",
            }}
          />
          <button onClick={send} disabled={busy} style={{
            background: "var(--brand, #4ade80)", border: "none", borderRadius: 10,
            width: 44, display: "grid", placeItems: "center", cursor: "pointer",
            opacity: busy ? 0.5 : 1, color: "#06110a", flexShrink: 0,
          }}><Send size={17} /></button>
        </div>
      </div>
    </>
  );
}
