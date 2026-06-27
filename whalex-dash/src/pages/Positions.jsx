// الصفقات — عامّة (المفتوحة تُراقب + المغلقة رابح/خاسر)
import { useEffect, useState } from "react";
import { signals } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { TrendingUp, TrendingDown } from "lucide-react";

export default function Positions() {
  const { t, lang } = useLang();
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const h = await signals.history();
      setHistory(h?.history || []);
    } catch { /* */ }
    finally { setLoading(false); }
  }
  useEffect(() => {
    load();
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, []);

  // إحصائيات سريعة
  const wins = history.filter((x) => x.is_win).length;
  const losses = history.length - wins;
  const winRate = history.length ? ((wins / history.length) * 100).toFixed(0) : 0;
  const totalProfit = history.filter((x) => x.is_win).reduce((a, x) => a + Number(x.pnl_pct || 0), 0);
  const totalLoss = history.filter((x) => !x.is_win).reduce((a, x) => a + Math.abs(Number(x.pnl_pct || 0)), 0);
  const net = totalProfit - totalLoss;

  if (loading) return <div className="loading">{t("loading")}</div>;

  return (
    <>
      {/* ملخّص الأداء */}
      <div className="grid grid-3" style={{ marginBottom: 20 }}>
        <div className="card stat">
          <span className="label">{t("winRate")}</span>
          <span className="value" style={{ color: "var(--brand)" }}>{winRate}%</span>
        </div>
        <div className="card stat">
          <span className="label">{t("wins")} ({wins})</span>
          <span className="value green">+{totalProfit.toFixed(1)}%</span>
        </div>
        <div className="card stat">
          <span className="label">{t("losses")} ({losses})</span>
          <span className="value red">-{totalLoss.toFixed(1)}%</span>
        </div>
      </div>

      {/* الصفقات المغلقة */}
      <div className="card">
        <div className="card-title">{t("closedTrades")}</div>
        {history.length === 0 ? (
          <div className="empty">{t("noClosedTrades")}</div>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {history.map((x, i) => (
              <div key={i} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "12px 14px", background: "var(--bg-2)", borderRadius: "var(--radius-sm)",
                borderInlineStart: `3px solid ${x.is_win ? "var(--green)" : "var(--red)"}`,
              }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <strong>{x.symbol}</strong>
                    <span className={`badge ${x.direction === "LONG" ? "long" : "short"}`}>{x.direction}</span>
                    {x.tier === "PH" && <span style={{ fontSize: 11, color: "var(--accent)" }}>🎯 Peak Hunter</span>}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 3 }}>
                    {x.closed_at ? new Date(x.closed_at * 1000).toLocaleString(lang === "ar" ? "ar-AE" : "en-US", { timeZone: "Asia/Dubai", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : ""}
                  </div>
                </div>
                <div style={{ textAlign: "center" }}>
                  <div style={{
                    fontSize: 18, fontWeight: 800,
                    color: x.is_win ? "var(--green)" : "var(--red)",
                    display: "flex", alignItems: "center", gap: 4,
                  }}>
                    {x.is_win ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                    {x.pnl_pct >= 0 ? "+" : ""}{Number(x.pnl_pct).toFixed(2)}%
                  </div>
                  <div style={{ fontSize: 11, color: x.is_win ? "var(--green)" : "var(--red)" }}>
                    {x.is_win ? t("win") : t("loss")}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
