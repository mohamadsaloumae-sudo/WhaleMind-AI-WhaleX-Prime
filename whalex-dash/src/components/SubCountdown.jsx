// ⏳ عدّ تنازلي حيّ للاشتراك
import { useEffect, useState } from "react";
import { subscription } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";

export default function SubCountdown() {
  const { lang } = useLang();
  const ar = lang === "ar";
  const [s, setS] = useState(null);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const r = await subscription.status();
        if (alive) setS(r);
      } catch { /* */ }
    };
    load();
    const a = setInterval(load, 120000);
    const b = setInterval(() => setNow(Date.now()), 1000);
    return () => { alive = false; clearInterval(a); clearInterval(b); };
  }, []);

  if (!s || !s.expires_at || s.tier === "admin") return null;

  const end = new Date(String(s.expires_at).replace(" ", "T") + "Z").getTime();
  const start = s.started_at ? new Date(String(s.started_at).replace(" ", "T") + "Z").getTime() : end - 30 * 86400000;
  const left = Math.max(0, end - now);
  const total = Math.max(1, end - start);
  const pct = Math.max(0, Math.min(100, (left / total) * 100));

  const d = Math.floor(left / 86400000);
  const h = Math.floor((left % 86400000) / 3600000);
  const m = Math.floor((left % 3600000) / 60000);
  const sec = Math.floor((left % 60000) / 1000);

  const fmt = (ts) => new Date(ts).toLocaleString(ar ? "ar-AE" : "en-US", {
    timeZone: "Asia/Dubai", year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });

  const danger = left < 2 * 86400000;
  const color = left <= 0 ? "#ef4444" : danger ? "#f59e0b" : "var(--brand, #4ade80)";

  const Box = ({ v, l }) => (
    <div style={{ flex: 1, textAlign: "center", padding: "9px 4px", background: "rgba(255,255,255,0.05)", borderRadius: 10 }}>
      <div style={{ fontSize: 19, fontWeight: 800, color, lineHeight: 1.2 }}>{String(v).padStart(2, "0")}</div>
      <div style={{ fontSize: 10, color: "var(--txt-3)", marginTop: 2 }}>{l}</div>
    </div>
  );

  return (
    <div className="card" style={{ marginBottom: 16, border: `1px solid ${danger ? "rgba(245,158,11,0.3)" : "rgba(74,222,128,0.22)"}` }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <span style={{ fontSize: 13.5, fontWeight: 700 }}>
          {left <= 0 ? (ar ? "🔒 انتهى الاشتراك" : "🔒 Subscription ended") : (ar ? "⏳ متبقٍ على اشتراكك" : "⏳ Time remaining")}
        </span>
        {s.icon && <span style={{ fontSize: 12, fontWeight: 700, color: "var(--brand)" }}>{s.icon} {ar ? s.level_ar : s.level_en}</span>}
      </div>

      <div style={{ display: "flex", gap: 7, marginBottom: 11 }}>
        <Box v={d} l={ar ? "يوم" : "days"} />
        <Box v={h} l={ar ? "ساعة" : "hrs"} />
        <Box v={m} l={ar ? "دقيقة" : "min"} />
        <Box v={sec} l={ar ? "ثانية" : "sec"} />
      </div>

      <div style={{ height: 6, background: "rgba(255,255,255,0.07)", borderRadius: 4, overflow: "hidden", marginBottom: 10 }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, transition: "width 1s linear" }} />
      </div>

      <div style={{ display: "grid", gap: 4, fontSize: 11.5, color: "var(--txt-3)" }}>
        <div>{ar ? "البداية" : "Started"}: <b style={{ color: "var(--txt-2)" }}>{fmt(start)}</b></div>
        <div>{ar ? "النهاية" : "Ends"}: <b style={{ color: "var(--txt-2)" }}>{fmt(end)}</b></div>
      </div>
    </div>
  );
}
