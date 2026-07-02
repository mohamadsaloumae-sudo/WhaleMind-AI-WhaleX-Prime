// صفقات الرادارات المفتوحة — مشاهدة حيّة فقط (بلا إغلاق)
import { useEffect, useState } from "react";
import { livePositions } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";

export default function LivePositions() {
  const { t } = useLang();
  const [radar, setRadar] = useState([]);
  const [loaded, setLoaded] = useState(false);

  async function loadRadar() {
    try {
      const r = await livePositions.radar();
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
              {isLong ? "LONG" : "SHORT"} {p.leverage}x
            </span>
          </div>
          <span style={{ fontSize: 17, fontWeight: 800, color: isProfit ? "#22c55e" : "#ef4444" }}>
            {isProfit ? "+" : ""}{p.pnl_pct}%
          </span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8, fontSize: 12, color: "var(--txt-3)" }}>
          <span>{t("entry") || "دخول"}: {p.entry}</span>
          <span>{t("current") || "حالياً"}: {p.current}</span>
          <span style={{ fontSize: 16 }}>{isProfit ? "🟢" : "🔴"}</span>
        </div>
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
