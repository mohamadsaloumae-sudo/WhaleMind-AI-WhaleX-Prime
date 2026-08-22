import { useEffect, useRef, useState } from "react";
import { MessageCircle, X, Send, Paperclip } from "lucide-react";
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
  const [unread, setUnread] = useState(0);
  // 🔒 المستمع يُسجَّل مرّة واحدة، فيحتجز open القديمة — ref يحمل الحيّة
  const openRef = useRef(false);
  // 📊 عدّ الردود بالاستطلاع — لا يعتمد على WebSocket فيعمل دائماً
  const lastSeenRef = useRef(-1);
  useEffect(() => { openRef.current = open; }, [open]);
  const endRef = useRef(null);

  // 🧹 الردود مكتوبة بـHTML لتيليجرام — ننظّفها للعرض هنا
  const clean = (t) => String(t || "")
    .replace(/<[^>]+>/g, "")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");

  // 🔑 AuthContext يسمّيه uid لا id — بدونه تُحفظ الرسائل باسم زائر
  const uid = user?.uid || user?.id || localStorage.getItem("wx_uid") || "guest";

  const load = () =>
    api.get(`/api/support/history?user_id=${uid}&limit=40`)
      .then((r) => {
        const list = r?.messages || [];
        setMsgs(list);
        // كم ردّاً موجوداً الآن؟ الزيادة = رسائل جديدة لم تُقرأ
        const replies = list.filter((m) => m.reply).length;
        if (lastSeenRef.current < 0) {
          lastSeenRef.current = replies;
        } else if (replies > lastSeenRef.current) {
          if (!openRef.current) setUnread((u) => u + (replies - lastSeenRef.current));
          lastSeenRef.current = replies;
        }
      })
      .catch(() => {});

  // 🔄 تحديث دوريّ أثناء فتح النافذة — ردّ الإدارة يصل بلا إغلاق وفتح
  // ⚡ ردّ فوريّ عبر WebSocket — بلا انتظار الاستطلاع
  useEffect(() => {
    const onReply = () => {
      load();
      if (!openRef.current) setUnread((u) => u + 1);
    };
    window.addEventListener("wx-support-reply", onReply);
    return () => window.removeEventListener("wx-support-reply", onReply);
  }, []);

  // 🔁 استطلاع دائم — حتى والنافذة مغلقة، كي يظهر العدّاد
  useEffect(() => {
    load();
    const iv = setInterval(load, 5000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    if (!open) return;
    load();
    const iv = setInterval(load, 2000);
    return () => clearInterval(iv);
  }, [open]);
  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, open]);

  // 📎 رفع صورة أو فيديو ثم إرساله كرسالة
  // 🗜️ ضغط الصورة قبل الرفع — 700ك تصير 80ك، فالوصول أسرع بكثير
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

  const pickFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || busy) return;
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
      await api.post("/api/support/ask", {
        user_id: uid, message: "", lang, media: d.url,
      });
      await load();
    } catch (err) {
      alert(err?.message || "تعذّر الرفع");
    } finally { setBusy(false); }
  };

  const send = async () => {
    const t = text.trim();
    if (!t || busy) return;
    setBusy(true);
    setMsgs((m) => [...m, { message: t, reply: null, created_at: Date.now() / 1000 }]);
    setText("");
    try {
      await api.post("/api/support/ask", { user_id: uid, message: t, lang });
      await load();
    } catch { /* الرسالة محفوظة عندنا على أي حال */ }
    finally { setBusy(false); }
  };

  return (
    <>
      <button
        onClick={() => { setOpen(true); setUnread(0); openRef.current = true; }}
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
        {unread > 0 && (
          <span style={{
            position: "absolute", top: -3, insetInlineEnd: -3,
            minWidth: 19, height: 19, borderRadius: 19, padding: "0 5px",
            background: "#ef4444", color: "#fff", fontSize: 11, fontWeight: 800,
            display: "grid", placeItems: "center",
          }}>{unread > 9 ? "9+" : unread}</span>
        )}
      </button>

      {open && (
        <div style={{
          position: "fixed",
          bottom: "calc(env(safe-area-inset-bottom, 0px) + 82px)",
          insetInlineEnd: 16, width: "min(460px, calc(100vw - 24px))",
          height: "min(640px, 82vh)", zIndex: 900,
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
                {m.message ? (
                <div style={{
                  marginInlineStart: "auto", maxWidth: "85%", width: "fit-content",
                  background: "rgba(45,212,191,.13)", borderRadius: "13px 13px 4px 13px",
                  padding: "9px 12px", fontSize: 12.5, color: "var(--txt-1)",
                  lineHeight: 1.7,
                }}>{m.message}</div>
                ) : null}
                {m.media ? (
                  <div style={{ marginInlineStart: "auto", width: "fit-content", maxWidth: "85%" }}>
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
            <label style={{
              width: 38, borderRadius: 11, cursor: "pointer",
              background: "rgba(255,255,255,.05)", border: "1px solid var(--bg-3)",
              display: "grid", placeItems: "center", color: "var(--txt-2)",
            }}>
              <Paperclip size={16} />
              <input type="file" accept="image/*,video/*" onChange={pickFile}
                     style={{ display: "none" }} />
            </label>
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
