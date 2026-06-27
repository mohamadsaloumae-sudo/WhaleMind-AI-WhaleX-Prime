// الرئيسية — نظرة عامة
import { useEffect, useState } from "react";
import { Activity, Radio } from "lucide-react";
import { useLang } from "../context/LangContext.jsx";
import { signals } from "../lib/api.js";

export default function Dashboard() {
  const { t } = useLang();
  const [live, setLive] = useState(false);
  const [day, setDay] = useState({ trades: 0, profit: 0, winRate: 0 });
  const [recent, setRecent] = useState([]);

  useEffect(() => {
    async function load() {
      try {
        const h = await signals.history();
        const list = h?.history || [];
        const wins = list.filter((x) => x.is_win).length;
        const profit = list.reduce((a, x) => a + Number(x.pnl_pct || 0), 0);
        const all = await signals.all();
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
    let ws;
    try {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => setLive(true);
      ws.onclose = () => setLive(false);
    } catch { /* تجاهل */ }
    return () => ws && ws.close();
  }, []);

  return (
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
          <div className="toggle-row">
            <span>Peak Hunter — SHORT/LONG</span>
            <span className="badge grade">{t("working")}</span>
          </div>
          <div className="toggle-row">
            <span>Predator</span>
            <span className="badge grade">{t("working")}</span>
          </div>
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
                  <span style={{ fontSize: 11, color: "var(--txt-3)" }}>{x.radar_type === "explosion" ? "🎯" : "⚡"} {x.grade}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
