// صفقات الرادارات المفتوحة — مشاهدة حيّة فقط (بلا إغلاق)
import { useEffect, useState } from "react";
import { livePositions } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { getMarket } from "../hooks/useMarket.js";

const fmtPx = (v) =>
  (v === 0 || v) ? String(Number(Number(v).toPrecision(6))) : "";

function fmtAge(openedAt, lang) {
  if (!openedAt) return "";
  const s = Math.max(0, Math.floor(Date.now() / 1000 - openedAt));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  const age = lang === "ar"
    ? (h > 0 ? `${h}س ${m}د` : `${m}د`)
    : (h > 0 ? `${h}h ${m}m` : `${m}m`);
  const tm = new Date(openedAt * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return lang === "ar" ? `⏱ منذ ${age} · فُتحت ${tm}` : `⏱ ${age} ago · opened ${tm}`;
}

export default function LivePositions() {
  const { t, lang } = useLang();
  const [radar, setRadar] = useState([]);
  const [loaded, setLoaded] = useState(false);

  async function loadRadar() {
    try {
      const r = await fetch(`/api/live/radar-positions?market=${getMarket()}`, { headers: { Authorization: `Bearer ${localStorage.getItem("wx_token") || ""}` } }).then((x) => x.json());
      setRadar(r?.positions || []);
    } catch { /* */ }
    finally { setLoaded(true); }
  }

  useEffect(() => {
    loadRadar();
    const id = setInterval(loadRadar, 1000);
    return () => clearInterval(id);
  }, []);

  function Card({ p }) {
    const isLong = p.direction === "LONG";
    const isProfit = p.pnl_pct >= 0;
    return (
      <div className="card" style={{ marginBottom: 10, padding: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontWeight: 700, fontSize: 15 }}>{p.symbol}</span>
            <span style={{
              fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 6,
              background: isLong ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
              color: isLong ? "#22c55e" : "#ef4444",
            }}>
              {isLong ? "LONG" : "SHORT"} {Math.round(p.leverage)}x
            </span>
            <span style={{
              fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 6,
              background: "rgba(99,102,241,0.15)", color: "var(--accent)",
            }}>
              {p.tier === "PH" ? (isLong ? "📈 WhaleX Long" : "🎯 WhaleX Short") : "⚡ WhaleX Predator"}
            </span>
          </div>
          <span style={{ fontSize: 17, fontWeight: 800, color: isProfit ? "#22c55e" : "#ef4444" }}>
            {isProfit ? "+" : ""}{p.pnl_pct}%
          </span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8, fontSize: 12, color: "var(--txt-3)" }}>
          <span>{t("entry") || "دخول"}: {fmtPx(p.entry)}</span>
          <span>{t("current") || "حالياً"}: {fmtPx(p.current)}</span>
          <span style={{ fontSize: 16 }}>{isProfit ? "🟢" : "🔴"}</span>
        </div>
        {p.opened_at ? (
          <div style={{ marginTop: 6, fontSize: 11, color: "var(--txt-3)" }}>
            {fmtAge(p.opened_at, lang)}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>{t("liveRadarTitle") || "صفقات الرادارات"}</h2>
      <p style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 16 }}>{t("liveRadarSub") || "مشاهدة حيّة · الربح والخسارة مباشرة"}</p>

      {!loaded ? (
        <div className="loading">{t("loading")}</div>
      ) : radar.length === 0 ? (
        <div className="card" style={{ padding: 14, fontSize: 13, color: "var(--txt-3)" }}>
          {t("noOpenPositions") || "لا صفقات مفتوحة حالياً."}
        </div>
      ) : (
        radar.map((p, i) => <Card key={`r-${i}`} p={p} />)
      )}
    </>
  );
}
