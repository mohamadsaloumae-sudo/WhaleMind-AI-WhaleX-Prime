// الصفقات — عامّة (المفتوحة تُراقب + المغلقة رابح/خاسر)
import { useEffect, useState } from "react";
import { signals } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { getMarket } from "../hooks/useMarket.js";
import Paywall from "../components/Paywall.jsx";
import { TrendingUp, TrendingDown } from "lucide-react";

export default function Positions() {
  const { t, lang } = useLang();
  const [history, setHistory] = useState([]);
  const [monthly, setMonthly] = useState(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const h = await signals.history(getMarket());
      setHistory(h?.history || []);
      const m = await signals.monthly(getMarket());
      setMonthly(m);
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
    <Paywall>
    <>
      {/* ملخّص الشهر */}
      {monthly && (
        <div className="card" style={{ marginBottom: 20, background: "linear-gradient(135deg, var(--bg-1), var(--bg-2))", border: "1px solid var(--brand-dim)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: "var(--brand)" }}>📅 {t("monthSummary")}</span>
            <span style={{ fontSize: 12, color: "var(--txt-3)" }}>{new Date().toLocaleDateString(lang === "ar" ? "ar-AE" : "en-US", { timeZone: "Asia/Dubai", month: "long", year: "numeric" })}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-around", textAlign: "center" }}>
            <div>
              <div style={{ fontSize: 12, color: "var(--txt-2)" }}>{t("wins")} ({monthly.wins_count})</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: "var(--green)" }}>+{monthly.total_profit_pct}%</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--txt-2)" }}>{t("losses")} ({monthly.losses_count})</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: "var(--red)" }}>-{monthly.total_loss_pct}%</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--txt-2)" }}>{t("net")}</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: monthly.net_pct >= 0 ? "var(--green)" : "var(--red)" }}>{monthly.net_pct >= 0 ? "+" : ""}{monthly.net_pct}%</div>
            </div>
          </div>
        </div>
      )}

      {/* ملخّص اليوم */}
      <div className="card-title" style={{ marginBottom: 10 }}>📆 {t("today")}</div>
      <div className="grid grid-4" style={{ marginBottom: 20 }}>
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
        <div className="card stat">
          <span className="label">{t("net")}</span>
          <span className="value" style={{ color: net >= 0 ? "var(--green)" : "var(--red)" }}>{net >= 0 ? "+" : ""}{net.toFixed(1)}%</span>
        </div>
      </div>

      {/* الصفقات المغلقة */}
      <div className="card">
        <div className="card-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>{t("closedTrades")}</span>
          {history.length > 0 && (
            <span style={{ fontSize: 11.5, fontWeight: 600, color: "var(--txt-3)", background: "rgba(255,255,255,0.05)", padding: "3px 9px", borderRadius: 7 }}>
              {history.length}
            </span>
          )}
        </div>
        {history.length === 0 ? (
          <div className="empty">{t("noClosedTrades")}</div>
        ) : (
          <div style={{ display: "grid", gap: 10, maxHeight: "58vh", overflowY: "auto", paddingInlineEnd: 4 }}>
            {history.map((x, i) => (
              <div key={i} style={{
                padding: "12px 14px", background: "var(--bg-2)", borderRadius: "var(--radius-sm)",
                borderInlineStart: `3px solid ${x.is_win ? "var(--green)" : "var(--red)"}`,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                    <strong style={{ whiteSpace: "nowrap" }}>{x.symbol}</strong>
                    <span className={`badge ${x.direction === "LONG" ? "long" : "short"}`} style={{ flexShrink: 0 }}>{x.direction}</span>
                    <span style={{ fontSize: 11, color: "var(--accent)", whiteSpace: "nowrap" }}>{x.tier === "PH" ? (x.direction === "LONG" ? "📈 WhaleX Long" : "🎯 WhaleX Short") : "⚡ WhaleX Predator"}</span>
                  </div>
                  <div style={{
                    fontSize: 16, fontWeight: 800, whiteSpace: "nowrap", flexShrink: 0,
                    color: x.is_win ? "var(--green)" : "var(--red)",
                    display: "flex", alignItems: "center", gap: 4,
                  }}>
                    {x.is_win ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
                    {x.pnl_pct >= 0 ? "+" : ""}{Number(x.pnl_pct).toFixed(2)}%
                  </div>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 5 }}>
                  <span style={{ fontSize: 12, color: "var(--txt-3)" }}>
                    {x.closed_at ? new Date(x.closed_at * 1000).toLocaleString(lang === "ar" ? "ar-AE" : "en-US", { timeZone: "Asia/Dubai", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : ""}
                  </span>
                  <span style={{ fontSize: 11, fontWeight: 700, color: x.is_win ? "var(--green)" : "var(--red)" }}>
                    {x.is_win ? t("win") : t("loss")}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
    </Paywall>
  );
}
