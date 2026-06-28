// جرس الإشعارات — يجمع رسائل مدير الصفقات والإشارات عبر WebSocket
import { useEffect, useRef, useState } from "react";
import { Bell, X } from "lucide-react";
import { useLang } from "../context/LangContext.jsx";

export default function NotificationBell() {
  const { t, lang } = useLang();
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const wsRef = useRef(null);

  useEffect(() => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    let ws, alive = true, retry;

    function connect() {
      if (!alive) return;
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      wsRef.current = ws;
      ws.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data);
          if (!d || !d.message) return;
          setItems((prev) => [{
            id: Date.now() + Math.random(),
            event: d.event || "alert",
            message: d.message,
            time: new Date(),
          }, ...prev].slice(0, 50));
          setUnread((u) => u + 1);
        } catch { /* */ }
      };
      ws.onclose = () => { if (alive) retry = setTimeout(connect, 5000); };
      ws.onerror = () => { try { ws.close(); } catch { /* */ } };
    }
    connect();
    return () => { alive = false; clearTimeout(retry); try { ws && ws.close(); } catch { /* */ } };
  }, []);

  function toggleOpen() {
    setOpen((o) => !o);
    if (!open) setUnread(0);
  }

  return (
    <>
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
                  <div key={it.id} className="bell-item">
                    <div className="bell-item-msg">{it.message}</div>
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
