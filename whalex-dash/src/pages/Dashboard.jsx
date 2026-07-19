// الرئيسية — نظرة عامة
import { useEffect, useState } from "react";
import { Activity, Radio } from "lucide-react";
import { useLang } from "../context/LangContext.jsx";
import { getMarket, setMarket } from "../hooks/useMarket.js";
import { signals } from "../lib/api.js";

export default function Dashboard() {
  const { t, lang } = useLang();
  const [live, setLive] = useState(false);
  const [day, setDay] = useState({ trades: 0, profit: 0, winRate: 0 });
  const [recent, setRecent] = useState([]);

  useEffect(() => {
    async function load() {
      try {
        const h = await signals.history(getMarket());
        const list = h?.history || [];
        const wins = list.filter((x) => x.is_win).length;
        const profit = list.reduce((a, x) => a + Number(x.pnl_pct || 0), 0);
        const all = await signals.all(getMarket());
        setRecent((all?.signals || []).slice(0, 4));
        setDay({
          trades: list.length,
          profit: profit,
          winRate: list.length ? Math.round((wins / list.length) * 100) : 0,
        });
      } catch { /* */ }
    }
    load();
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    let ws, alive = true, retry;
    function connect() {
      if (!alive) return;
      try {
        ws = new WebSocket(`${proto}://${location.host}/ws/live`);
        ws.onopen = () => { if (alive) setLive(true); };
        ws.onclose = () => { if (alive) { setLive(false); retry = setTimeout(connect, 5000); } };
        ws.onerror = () => { try { ws.close(); } catch { /* */ } };
      } catch { /* */ }
    }
    connect();
    return () => { alive = false; clearTimeout(retry); try { ws && ws.close(); } catch { /* */ } };
  }, []);

  const mkt = getMarket();
  const MB = ({ id, ar, en }) => (
    <button onClick={() => mkt !== id && setMarket(id)}
      style={{ flex: 1, padding: "12px 0", borderRadius: 12, border: "1px solid var(--bg-2)",
               fontWeight: 800, fontSize: 15, cursor: "pointer",
               background: mkt === id ? "var(--brand)" : "var(--bg-1)",
               color: mkt === id ? "#04211c" : "var(--txt-1)" }}>
      {lang === "ar" ? ar : en}
    </button>
  );
  return (
    <>
      <div style={{ display: "flex", gap: 10, padding: "12px 16px 4px" }}>
        <MB id="futures" ar="⚡ فيوتشر" en="⚡ Futures" />
        <MB id="spot" ar="🪙 سبوت" en="🪙 Spot" />
      </div>
      <>
      <div className="grid grid-4" style={{ marginBottom: 24 }}>
        <div className="card stat">
          <span className="label">{t("status")}</span>
          <span className="value green" style={{ fontSize: 20 }}>
            {live ? t("connectedLive") : t("notConnected")}
          </span>
        </div>
        <div className="card stat">
          <span className="label">{t("todayTrades")}</span>
          <span className="value">{day.trades}</span>
        </div>
        <div className="card stat">
          <span className="label">{t("todayProfit")}</span>
          <span className="value" style={{ color: day.profit >= 0 ? "var(--green)" : "var(--red)" }}>{day.profit >= 0 ? "+" : ""}{day.profit.toFixed(1)}%</span>
        </div>
        <div className="card stat">
          <span className="label">{t("winRate")}</span>
          <span className="value" style={{ color: "var(--brand)" }}>{day.winRate}%</span>
        </div>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="card-title"><Radio size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("radarsStatus")}</div>
          {mkt === "spot" ? (
            <div className="toggle-row">
              <span>🪙 WhaleX Spot</span>
              <span className="badge grade">{t("working")}</span>
            </div>
          ) : (
            <>
              <div className="toggle-row">
                <span>📈 WhaleX Long</span>
                <span className="badge grade">{t("working")}</span>
              </div>
              <div className="toggle-row">
                <span>🎯 WhaleX Short</span>
                <span className="badge grade">{t("working")}</span>
              </div>
              <div className="toggle-row">
                <span>⚡ WhaleX Predator</span>
                <span className="badge grade">{t("working")}</span>
              </div>
            </>
          )}
        </div>
        <div className="card">
          <div className="card-title"><Activity size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("recentActivity")}</div>
          {recent.length === 0 ? (
            <div className="empty">{t("liveActivityHint")}</div>
          ) : (
            <div style={{ display: "grid", gap: 8 }}>
              {recent.map((x, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 10px", background: "var(--bg-2)", borderRadius: "var(--radius-sm)", fontSize: 13 }}>
                  <span style={{ fontWeight: 700 }}>{x.symbol}</span>
                  <span className={`badge ${x.direction === "LONG" ? "long" : "short"}`} style={{ fontSize: 11 }}>{x.direction}</span>
                  <span style={{ fontSize: 11, color: "var(--txt-3)" }}>{x.radar_type === "spot" ? "🪙 WhaleX Spot" : x.radar_type === "explosion" ? (x.direction === "LONG" ? "📈 WhaleX Long" : "🎯 WhaleX Short") : "⚡ WhaleX Predator"} · {x.grade}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      </>
    </>
  );
}
