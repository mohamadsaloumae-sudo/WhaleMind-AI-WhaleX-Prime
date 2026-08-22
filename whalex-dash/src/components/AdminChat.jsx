import { useEffect, useRef, useState } from "react";
import { MessageCircle, X, Send, User, Paperclip } from "lucide-react";
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

  // 🗜️ ضغط الصورة قبل الرفع
  const shrink = (file) => new Promise((done) => {
    if (!file.type.startsWith("image/")) return done(file);
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const max = 1400;
      let { width: w, height: h } = img;
      if (w > max || h > max) {
        const r = Math.min(max / w, max / h);
        w = Math.round(w * r); h = Math.round(h * r);
      }
      const cv = document.createElement("canvas");
      cv.width = w; cv.height = h;
      cv.getContext("2d").drawImage(img, 0, 0, w, h);
      cv.toBlob((b) => {
        URL.revokeObjectURL(url);
        done(b ? new File([b], "img.jpg", { type: "image/jpeg" }) : file);
      }, "image/jpeg", 0.82);
    };
    img.onerror = () => { URL.revokeObjectURL(url); done(file); };
    img.src = url;
  });

  // 📎 إرسال صورة أو فيديو للعميل
  const pickFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || busy || !open) return;
    setBusy(true);
    try {
      const small = await shrink(file);
      const fd = new FormData();
      fd.append("file", small);
      const r = await fetch("/api/support/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("whalex_token") || ""}` },
        body: fd,
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail || "فشل الرفع");
      await api.post("/api/admin/support/send",
                     { user_id: open, reply: "", media: d.url });
      await loadThread(open);
    } catch (err) {
      alert(err?.message || "تعذّر الرفع");
    } finally { setBusy(false); }
  };

  const send = async () => {
    const t = text.trim();
    if (!t || busy) return;
    setBusy(true);
    try {
      // 💬 إن كان هناك سؤال معلّق نردّ عليه، وإلا نرسل رسالة مباشرة
      const pend = msgs.filter((m) => !m.reply);
      if (pend.length) {
        await api.post("/api/admin/support/reply",
                       { msg_id: pend[pend.length - 1].id, reply: t });
      } else {
        await api.post("/api/admin/support/send", { user_id: open, reply: t });
      }
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
                  {m.message ? (
                  <div style={{
                    maxWidth: "85%", width: "fit-content",
                    background: "var(--bg-2)", borderRadius: "13px 13px 13px 4px",
                    padding: "9px 12px", fontSize: 12.5, color: "var(--txt-1)",
                    lineHeight: 1.7,
                  }}>{m.message}</div>
                  ) : null}
                  {m.media ? (
                    <div style={{ width: "fit-content", maxWidth: "85%", marginBottom: 6 }}>
                      {/\.(mp4|webm|mov)$/i.test(m.media) ? (
                        <video src={m.media} controls
                               style={{ maxWidth: "100%", borderRadius: 12, display: "block" }} />
                      ) : (
                        <img src={m.media} alt=""
                             onClick={() => window.open(m.media, "_blank")}
                             style={{ maxWidth: "100%", borderRadius: 12, display: "block", cursor: "pointer" }} />
                      )}
                    </div>
                  ) : null}
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
              <label style={{
                width: 38, borderRadius: 11, cursor: "pointer",
                background: "rgba(255,255,255,.05)", border: "1px solid var(--bg-3)",
                display: "grid", placeItems: "center", color: "var(--txt-2)",
              }}>
                <Paperclip size={16} />
                <input type="file" accept="image/*,video/mp4,video/quicktime" onChange={pickFile}
                       style={{ display: "none" }} />
              </label>
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
