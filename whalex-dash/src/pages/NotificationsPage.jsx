import { useEffect, useState } from "react";
import { Bell } from "lucide-react";
import { useLang } from "../context/LangContext.jsx";

export default function NotificationsPage() {
  const { t, lang } = useLang();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/notifications?limit=100")
      .then((r) => r.json())
      .then((d) => {
        const arr = (d && Array.isArray(d.notifications)) ? d.notifications : [];
        setItems(arr);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function fmtTime(ts) {
    if (!ts) return "";
    try {
      return new Date(ts * 1000).toLocaleString(lang === "ar" ? "ar-AE" : "en-US", {
        timeZone: "Asia/Dubai", month: "short", day: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
    } catch (e) {
      return "";
    }
  }

  return (
    <div style={{ padding: 16, maxWidth: 720, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <Bell size={20} style={{ color: "var(--accent)" }} />
        <h2 style={{ fontSize: 18, fontWeight: 800, margin: 0 }}>{t("notifications") || "الإشعارات"}</h2>
      </div>
      {loading ? (
        <div style={{ textAlign: "center", color: "var(--txt-3)", padding: 40 }}>...</div>
      ) : items.length === 0 ? (
        <div style={{ textAlign: "center", color: "var(--txt-3)", padding: 40 }}>
          {t("noNotifications") || "لا توجد إشعارات"}
        </div>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {items.map((it) => (
            <div key={it.id} style={{
              padding: "12px 14px", background: "var(--bg-2)",
              borderRadius: "var(--radius-sm)", borderInlineStart: "3px solid var(--accent)",
            }}>
              <div style={{ fontSize: 13.5, whiteSpace: "pre-line", lineHeight: 1.6 }}>
                {lang === "ar" ? it.message : (it.message_en || it.message)}
              </div>
              <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 6 }}>
                {fmtTime(it.created_at)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
