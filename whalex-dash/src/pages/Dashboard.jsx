// الرئيسية — نظرة عامة
import WelcomeHeader from "../components/WelcomeHeader.jsx";
import { useEffect, useState } from "react";
import { Activity, Radio } from "lucide-react";
import { useLang } from "../context/LangContext.jsx";
import { getMarket, setMarket } from "../hooks/useMarket.js";
import { signals } from "../lib/api.js";
import ChatWidget from "../components/ChatWidget.jsx";

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
    <button onClick={() =>
      mkt !== id && setMarket(id)}
      style={{ flex: 1, padding: "12px 0", borderRadius: 12, border: "1px solid var(--bg-2)",
               fontWeight: 800, fontSize: 15, cursor: "pointer",
               background: mkt === id ? "var(--brand)" : "var(--bg-1)",
               color: mkt === id ? "#04211c" : "var(--txt-1)" }}>
      {lang === "ar" ? ar : en}
    </button>
  );
  const [rdr, setRdr] = useState([]);
  useEffect(() => {
    let alive = true;
    const pull = () => fetch("/api/radars/status")
      .then((r) => r.json())
      .then((d) => { if (alive && d && d.radars) setRdr(d.radars); })
      .catch(() => {});
    pull();
    const id = setInterval(pull, 60000);
    return () => { alive = false; clearInterval(id); };
  }, []);
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60000);
    return () => clearInterval(id);
  }, []);
  const _loc = lang === "ar" ? "ar-EG-u-nu-latn" : "en-US";
  const stamp = now.toLocaleDateString(_loc, { day: "numeric", month: "long" })
    + " · " + now.toLocaleTimeString(_loc, { hour: "numeric", minute: "2-digit" });
  return (
    <>
      <ChatWidget />
      <WelcomeHeader />
      <div style={{ display: "flex", gap: 10, padding: "12px 16px 4px" }}>
        <MB id="futures" ar="⚡ فيوتشر" en="⚡ Futures" />
        <MB id="spot" ar="🪙 سبوت" en="🪙 Spot" />
        <MB id="meme" ar="🐸 ميم" en="🐸 Meme" />
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
          <span style={{ fontSize: 13, color: "#e8eef2", fontWeight: 600, marginTop: 4 }}>{stamp}</span>
        </div>
        <div className="card stat">
          <span className="label">{t("winRate")}</span>
          <span className="value" style={{ color: "var(--brand)" }}>{day.winRate}%</span>
        </div>
      </div>

      <style>{`@keyframes wxPulse {
        0%,100% { opacity: 1; transform: scale(1); }
        50% { opacity: .35; transform: scale(.78); } }`}</style>
      <div className="grid grid-2">
        <div className="card">
          <div className="card-title"><Radio size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("radarsStatus")}</div>
          {(() => {
            const S = { live: ["#22c55e", "يعمل", "live"],
                        slow: ["#fbbf24", "بطيء", "slow"],
                        down: ["#f87171", "متوقّف", "down"],
                        unknown: ["#94a3b8", "غير معروف", "unknown"] };
            const rank = (x) => (x.key.startsWith("ai_") ? 0 : x.market === "all" ? 1 : 2);
            const list = rdr.filter((x) => x.market === mkt || x.market === "all")
                            .sort((a, b) => rank(a) - rank(b));
            if (!list.length) return <div className="empty">…</div>;
            return list.map((x) => {
              const [col, ar, en] = S[x.state] || S.unknown;
              return (
                <div className="toggle-row" key={x.key}>
                  <span>{x.icon} {x.name}</span>
                  <span className="badge" style={{ color: col,
                        display: "inline-flex", alignItems: "center", gap: 6,
                        background: `color-mix(in srgb, ${col} 15%, transparent)` }}>
                    <i style={{ width: 7, height: 7, borderRadius: "50%",
                        background: col, display: "inline-block",
                        animation: x.state === "live" ? "wxPulse 1.8s ease-in-out infinite" : "none" }} />
                    {lang === "en" ? en : ar}
                  </span>
                </div>
              );
            });
          })()}
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
                  {x.radar_type === "meme" ? (
                    <span className="badge" style={{ fontSize: 11, background: "rgba(74,222,128,0.15)", color: "var(--brand)" }}>{x.score}/100</span>
                  ) : (
                    <span className={`badge ${x.direction === "LONG" ? "long" : "short"}`} style={{ fontSize: 11 }}>{x.direction}</span>
                  )}
                  <span style={{ fontSize: 11, color: "var(--txt-3)" }}>{x.radar_type === "meme" ? ("🐸 " + (x.chain || "")) : x.radar_type === "spot" ? "🪙 WhaleX Spot" : x.radar_type === "explosion" ? (x.direction === "LONG" ? "📈 WhaleX Long" : "🎯 WhaleX Short") : "⚡ WhaleX Predator"}{x.radar_type === "meme" ? "" : (" · " + x.grade)}</span>
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
