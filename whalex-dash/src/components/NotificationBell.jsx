// جرس الإشعارات — يجمع رسائل مدير الصفقات والإشارات عبر WebSocket
import { useEffect, useRef, useState } from "react";
import { Bell, X, Volume2, VolumeX } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useLang } from "../context/LangContext.jsx";

// 🔔 نغمة تنبيه عبر WebAudio — بلا ملف صوت، تعمل على الجوال بعد أول لمسة
let _actx = null;
function playChime() {
  try {
    if (localStorage.getItem("wx_sound") === "off") return;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    if (!_actx) _actx = new AC();
    if (_actx.state === "suspended") _actx.resume();
    const now = _actx.currentTime;
    [880, 1174.7].forEach((f, i) => {
      const osc = _actx.createOscillator(), g = _actx.createGain();
      osc.type = "sine";
      osc.frequency.value = f;
      g.gain.setValueAtTime(0.0001, now + i * 0.14);
      g.gain.exponentialRampToValueAtTime(0.28, now + i * 0.14 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.14 + 0.42);
      osc.connect(g); g.connect(_actx.destination);
      osc.start(now + i * 0.14); osc.stop(now + i * 0.14 + 0.45);
    });
  } catch { /* */ }
}

export default function NotificationBell() {
  const { t, lang } = useLang();
  const [muted, setMuted] = useState(() => localStorage.getItem("wx_sound") === "off");
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const wsRef = useRef(null);

  useEffect(() => {
    fetch("/api/notifications?limit=50")
      .then((r) => r.json())
      .then((d) => {
        if (d && Array.isArray(d.notifications)) {
          setItems(
            d.notifications.map((n) => ({
              id: n.id,
              event: n.event,
              message: n.message,
              message_en: n.message_en,
              time: new Date(n.created_at * 1000),
            }))
          );
        }
      })
      .catch(() => { /* تجاهل فشل التحميل الأولي */ });
  }, []);

  useEffect(() => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    let ws, alive = true, retry;

    function connect() {
      if (!alive) return;
      ws = new WebSocket(`${proto}://${location.host}/ws/live`);
      wsRef.current = ws;
      ws.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data);
          if (!d || !d.message) return;
          setItems((prev) => [{
            id: Date.now() + Math.random(),
            event: d.event || "alert",
            message: d.message,
            message_en: d.message_en,
            time: new Date(),
          }, ...prev].slice(0, 50));
          setUnread((u) => u + 1);
          playChime();
        } catch { /* */ }
      };
      ws.onclose = () => { if (alive) retry = setTimeout(connect, 5000); };
      ws.onerror = () => { try { ws.close(); } catch { /* */ } };
    }
    connect();
    return () => { alive = false; clearTimeout(retry); try { ws && ws.close(); } catch { /* */ } };
  }, []);

  useEffect(() => {
    const unlock = () => {
      try {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (AC && !_actx) _actx = new AC();
        if (_actx && _actx.state === "suspended") _actx.resume();
      } catch { /* */ }
    };
    document.addEventListener("touchstart", unlock, { once: true });
    document.addEventListener("click", unlock, { once: true });
    return () => {
      document.removeEventListener("touchstart", unlock);
      document.removeEventListener("click", unlock);
    };
  }, []);

  function toggleMute() {
    const next = !muted;
    setMuted(next);
    localStorage.setItem("wx_sound", next ? "off" : "on");
    if (!next) playChime();
  }

  function toggleOpen() {
    setOpen((o) => !o);
    if (!open) setUnread(0);
  }

  return (
    <>
      <button className="bell-btn" onClick={toggleMute} title={muted ? "تشغيل الصوت" : "كتم الصوت"} style={{ opacity: muted ? 0.45 : 1 }}>
        {muted ? <VolumeX size={17} /> : <Volume2 size={17} />}
      </button>
      <button className="bell-btn" onClick={toggleOpen} title={t("notifications")}>
        <Bell size={18} />
        {unread > 0 && <span className="bell-badge">{unread > 9 ? "9+" : unread}</span>}
      </button>

      {open && (
        <>
          <div className="bell-overlay" onClick={() => setOpen(false)} />
          <div className="bell-panel">
            <div className="bell-panel-head">
              <span>{t("notifications")}</span>
              <button onClick={() => setOpen(false)}><X size={18} /></button>
            </div>
            <div className="bell-list">
              {items.length === 0 ? (
                <div className="bell-empty">{t("noNotifications")}</div>
              ) : (
                items.map((it) => (
                  <div
                    key={it.id}
                    className="bell-item"
                    onClick={() => {
                      setOpen(false);
                      const _pmEvents = ["tp1_hit", "tp2_hit", "position_closed", "pyramiding", "sl_warning", "trailing_active", "ai_alert"];
                      navigate(_pmEvents.includes(it.event) ? "/live" : "/signals");
                    }}
                    style={{ cursor: "pointer" }}
                  >
                    <div className="bell-item-msg">{lang === "ar" ? it.message : (it.message_en || it.message)}</div>
                    <div className="bell-item-time">
                      {it.time.toLocaleTimeString(lang === "ar" ? "ar-AE" : "en-US", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Dubai" })}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </>
  );
}
