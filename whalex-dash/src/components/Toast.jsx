// 🔔 إشعار عائم داخل التطبيق
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, TrendingUp, CheckCircle2, XCircle } from "lucide-react";

const ICONS = {
  signal: TrendingUp,
  opened: TrendingUp,
  closed: CheckCircle2,
  sl_hit: XCircle,
  trailing_active: CheckCircle2,
};

export default function Toast() {
  const [items, setItems] = useState([]);
  const nav = useNavigate();

  useEffect(() => {
    function onToast(e) {
      const id = Date.now() + Math.random();
      const msg = String(e.detail?.message || "").slice(0, 180);
      setItems((prev) => [{ id, message: msg, event: e.detail?.event || "alert" }, ...prev].slice(0, 3));
      setTimeout(() => setItems((prev) => prev.filter((x) => x.id !== id)), 6000);
    }
    window.addEventListener("wx-toast", onToast);
    return () => window.removeEventListener("wx-toast", onToast);
  }, []);

  if (!items.length) return null;

  return (
    <div style={{
      position: "fixed", top: "calc(env(safe-area-inset-top, 0px) + 10px)",
      left: "50%", transform: "translateX(-50%)",
      width: "min(94vw, 420px)", zIndex: 1200,
      display: "flex", flexDirection: "column", gap: 8, pointerEvents: "none",
    }}>
      {items.map((it) => {
        const Icon = ICONS[it.event] || Bell;
        return (
          <div
            key={it.id}
            onClick={() => nav("/")}
            style={{
              pointerEvents: "auto", cursor: "pointer",
              display: "flex", alignItems: "flex-start", gap: 10,
              padding: "12px 14px", borderRadius: 14,
              background: "rgba(18,22,32,0.86)",
              backdropFilter: "blur(14px)", WebkitBackdropFilter: "blur(14px)",
              border: "1px solid rgba(74,222,128,0.28)",
              boxShadow: "0 10px 34px rgba(0,0,0,0.45)",
              animation: "wxToastIn .34s cubic-bezier(.22,.9,.3,1)",
            }}
          >
            <span style={{
              width: 30, height: 30, borderRadius: 9, flexShrink: 0,
              background: "rgba(74,222,128,0.16)", color: "var(--brand, #4ade80)",
              display: "grid", placeItems: "center",
            }}><Icon size={16} /></span>
            <div style={{
              fontSize: 13, lineHeight: 1.65, color: "#e8ecf3",
              whiteSpace: "pre-line", wordBreak: "break-word", flex: 1, minWidth: 0,
            }}>{it.message}</div>
          </div>
        );
      })}
    </div>
  );
}
