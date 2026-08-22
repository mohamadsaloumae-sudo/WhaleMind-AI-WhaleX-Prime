import { useEffect, useRef, useState } from "react";
import { MessageCircle, X, Send, User } from "lucide-react";
import { api } from "../lib/api.js";

/**
 * 💬 محادثات الدعم — قائمة بالاسم، ونافذة لكل مستخدم.
 *    تحلّ محلّ قائمة الأسئلة المبعثرة.
 */
export default function AdminChat() {
  const [threads, setThreads] = useState([]);
  const [open, setOpen] = useState(null);      // user_id
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  const loadThreads = () =>
    api.get("/api/admin/support/threads")
      .then((r) => setThreads(r?.threads || []))
      .catch(() => {});

  const loadThread = (uid) =>
    api.get(`/api/admin/support/thread?user_id=${uid}&limit=60`)
      .then((r) => setMsgs(r?.messages || []))
      .catch(() => {});

  useEffect(() => {
    loadThreads();
    const iv = setInterval(loadThreads, 5000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    if (!open) return;
    loadThread(open);
    const iv = setInterval(() => loadThread(open), 2000);
    return () => clearInterval(iv);
  }, [open]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  const clean = (t) => String(t || "").replace(/<[^>]+>/g, "");

  const send = async () => {
    const t = text.trim();
    if (!t || busy) return;
    const pend = msgs.filter((m) => !m.reply);
    const target = pend.length ? pend[pend.length - 1].id : msgs[msgs.length - 1]?.id;
    if (!target) return;
    setBusy(true);
    try {
      await api.post("/api/admin/support/reply", { msg_id: target, reply: t });
      setText("");
      await loadThread(open); loadThreads();
    } catch (e) {
      alert(e?.message || "تعذّر الإرسال");
    } finally { setBusy(false); }
  };

  const who = threads.find((t) => t.user_id === open);

  return (
    <div className="card" style={{ marginTop: 16, padding: 16 }}>
      <div className="card-title" style={{ marginBottom: 12 }}>
        💬 المحادثات ({threads.reduce((a, t) => a + (t.waiting || 0), 0)} تنتظر)
      </div>

      {threads.length === 0 && (
        <div style={{ fontSize: 12.5, color: "var(--txt-3)", padding: "10px 0" }}>
          لا محادثات بعد
        </div>
      )}

      {threads.map((t) => (
        <div key={t.user_id}
          onClick={() => setOpen(t.user_id)}
          style={{
            display: "flex", alignItems: "center", gap: 10, cursor: "pointer",
            padding: "11px 12px", marginBottom: 7, borderRadius: 12,
            background: t.waiting ? "rgba(245,158,11,.07)" : "rgba(255,255,255,.03)",
            border: `1px solid ${t.waiting ? "rgba(245,158,11,.3)" : "var(--bg-3)"}`,
          }}>
          <User size={16} style={{ color: "var(--txt-3)", flexShrink: 0 }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--txt-1)" }}>
              {t.username}
            </div>
            <div style={{
              fontSize: 11, color: "var(--txt-3)", marginTop: 2,
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }}>{t.last_msg}</div>
          </div>
          {t.waiting > 0 && (
            <span style={{
              minWidth: 20, height: 20, borderRadius: 20, padding: "0 6px",
              background: "#ef4444", color: "#fff", fontSize: 11, fontWeight: 800,
              display: "grid", placeItems: "center", flexShrink: 0,
            }}>{t.waiting}</span>
          )}
        </div>
      ))}

      {open && (
        <div onClick={() => setOpen(null)} style={{
          position: "fixed", inset: 0, zIndex: 9998,
          background: "rgba(0,0,0,.7)", display: "grid", placeItems: "center",
          padding: 16,
        }}>
          <div onClick={(e) => e.stopPropagation()} style={{
            width: "min(460px, 100%)", height: "min(560px, 85vh)",
            background: "var(--bg-1)", borderRadius: 16,
            border: "1px solid var(--bg-3)",
            display: "flex", flexDirection: "column", overflow: "hidden",
          }}>
            <div style={{
              display: "flex", alignItems: "center", gap: 9,
              padding: "13px 15px", borderBottom: "1px solid var(--bg-3)",
            }}>
              <MessageCircle size={17} style={{ color: "var(--brand)" }} />
              <span style={{ flex: 1, fontSize: 14, fontWeight: 800 }}>
                {who?.username || "محادثة"}
              </span>
              <button onClick={() => setOpen(null)} style={{
                background: "transparent", border: "none", cursor: "pointer",
                color: "var(--txt-2)", display: "flex",
              }}><X size={18} /></button>
            </div>

            <div style={{ flex: 1, overflowY: "auto", padding: "14px 13px" }}>
              {msgs.map((m, i) => (
                <div key={i} style={{ marginBottom: 13 }}>
                  <div style={{
                    maxWidth: "85%", width: "fit-content",
                    background: "var(--bg-2)", borderRadius: "13px 13px 13px 4px",
                    padding: "9px 12px", fontSize: 12.5, color: "var(--txt-1)",
                    lineHeight: 1.7,
                  }}>{m.message}</div>
                  {m.reply && (
                    <div style={{
                      marginTop: 7, marginInlineStart: "auto",
                      maxWidth: "85%", width: "fit-content",
                      background: "rgba(45,212,191,.13)",
                      borderRadius: "13px 13px 4px 13px",
                      padding: "9px 12px", fontSize: 12.5, color: "var(--txt-2)",
                      lineHeight: 1.75,
                    }}>{clean(m.reply)}{m.auto ? " 🤖" : ""}</div>
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
                placeholder="اكتب ردّك…"
                style={{
                  flex: 1, padding: "10px 13px", borderRadius: 11,
                  background: "rgba(255,255,255,.04)",
                  border: "1px solid var(--bg-3)",
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
        </div>
      )}
    </div>
  );
}
