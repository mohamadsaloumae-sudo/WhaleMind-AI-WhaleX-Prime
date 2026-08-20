// الصفقات — عامّة (المفتوحة تُراقب + المغلقة رابح/خاسر)
import { useEffect, useState } from "react";
import { signals } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { getMarket } from "../hooks/useMarket.js";
import Paywall from "../components/Paywall.jsx";
import { TrendingUp, TrendingDown } from "lucide-react";

// 🖼️ شعارات المنصّات — للشفافية: أين نُفِّذت الصفقة
const EX_LOGO = {
  binance: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/270.png",
  bybit: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/521.png",
  mexc: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/544.png",
  bingx: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/1064.png",
  bitget: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/513.png",
  gate: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/302.png",
  okx: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/294.png",
};

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
      <div>
        <div className="card-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
          <span>{t("closedTrades")}</span>
          {history.length > 0 && (
            <span style={{ fontSize: 11.5, fontWeight: 600, color: "var(--txt-3)", background: "rgba(255,255,255,0.05)", padding: "3px 9px", borderRadius: 7 }}>
              {history.length}
            </span>
          )}
        </div>
        {history.length === 0 ? (
          <div className="card"><div className="empty">{t("noClosedTrades")}</div></div>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {history.map((x, i) => {
              const win = x.is_win;
              const radar =
                x.tier === "MEME" ? "🐸 WhaleX Meme"
                : x.tier === "SPOT" || x.direction === "SPOT" ? "🪙 WhaleX Spot"
                : x.tier === "PH" ? (x.direction === "LONG" ? "📈 WhaleX Long" : "🎯 WhaleX Short")
                : "⚡ WhaleX Predator";
              return (
                <div key={i} className="card" style={{
                  padding: "14px 16px", marginBottom: 0,
                  borderInlineStart: `3px solid ${win ? "var(--green)" : "var(--red)"}`,
                }}>
                  {/* الصف الأول: العملة والرادار | النتيجة والحالة */}
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 3 }}>
                        {x.exchange ? (
                          <img src={EX_LOGO[String(x.exchange).toLowerCase()]}
                               alt={x.exchange} width="17" height="17"
                               style={{ borderRadius: 4, flexShrink: 0 }}
                               onError={(e) => { e.target.style.display = "none"; }} />
                        ) : null}
                        <strong style={{ fontSize: 14.5, direction: "ltr" }}>{x.symbol}</strong>
                        <span className={`badge ${x.direction === "LONG" ? "long" : "short"}`} style={{ fontSize: 10, flexShrink: 0 }}>
                          {x.direction}{x.leverage ? ` ${Math.round(x.leverage)}x` : ""}
                        </span>
                      </div>
                      <div style={{ fontSize: 11, color: "var(--accent)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {radar}
                      </div>
                      {(x.entry && x.exit_price) ? (
                        <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 3, direction: "ltr", textAlign: "start" }}>
                          {x.entry} → {x.exit_price}
                        </div>
                      ) : null}
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4, flexShrink: 0 }}>
                      <div style={{
                        display: "flex", alignItems: "center", gap: 4, whiteSpace: "nowrap",
                        fontSize: 16.5, fontWeight: 800, color: win ? "var(--green)" : "var(--red)",
                      }}>
                        {win ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
                        {x.pnl_pct >= 0 ? "+" : ""}{Number(x.pnl_pct).toFixed(2)}%
                      </div>
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: "2px 9px", borderRadius: 6, whiteSpace: "nowrap",
                        background: win ? "rgba(34,197,94,0.14)" : "rgba(239,68,68,0.14)",
                        color: win ? "var(--green)" : "var(--red)",
                      }}>
                        {win ? t("win") : t("loss")}
                      </span>
                    </div>
                  </div>

                  {/* الصف الثاني: الوقت */}
                  <div style={{ marginTop: 8, paddingTop: 7, borderTop: "1px solid rgba(255,255,255,0.05)", fontSize: 11.5, color: "var(--txt-3)" }}>
                    {x.closed_at ? new Date(x.closed_at * 1000).toLocaleString(lang === "ar" ? "ar-AE" : "en-US", { timeZone: "Asia/Dubai", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : ""}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
    </Paywall>
  );
}
