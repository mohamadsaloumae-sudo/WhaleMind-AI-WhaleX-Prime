// صفقاتي — صفقات Binance الحقيقية (حيّة + زرّ إغلاق)
import { useEffect, useState } from "react";
import { livePositions, api } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";

export default function Trades() {
  const { t } = useLang();
  const [positions, setPositions] = useState([]);
  const [connected, setConnected] = useState(true);
  const [loading, setLoading] = useState(true);
  const [closing, setClosing] = useState(null);
  const [msg, setMsg] = useState("");
  // 📒 سجلّ صفقاته الحقيقية — نفس مصدر بطاقة الإدارة (stats)
  //    فلا يختلف رقم بين الصفحتين.
  const [ledger, setLedger] = useState(null);

  async function load() {
    try {
      const data = await livePositions.binance();
      setPositions(data?.positions || []);
      setConnected(data?.connected !== false);
    } catch { /* */ }
    finally { setLoading(false); }
  }
  useEffect(() => {
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const pull = () => api.get("/api/profile/trades")
      .then((r) => setLedger(r || null)).catch(() => {});
    pull();
    const id2 = setInterval(pull, 20000);
    return () => clearInterval(id2);
  }, []);

  async function handleClose(symbol) {
    if (!window.confirm(`${t("closeConfirm") || "إغلاق صفقة"} ${symbol}؟`)) return;
    setClosing(symbol);
    setMsg("");
    try {
      await livePositions.close(symbol);
      setMsg(`✅ ${symbol}`);
      await load();
    } catch (e) {
      setMsg(`⚠️ ${e.message}`);
    } finally {
      setClosing(null);
    }
  }

  if (loading) return <div className="loading">{t("loadingTrades")}</div>;

  return (
    <>
      {!connected && <div className="alert info">{t("requiresBinance")}</div>}
      {msg && <div className="card" style={{ marginBottom: 12, padding: 10, fontSize: 13, textAlign: "center" }}>{msg}</div>}

      {ledger && (ledger.closed > 0 || ledger.open > 0) && (
        <div className="card" style={{ marginBottom: 12 }}>
          <div className="card-title">📒 {t("myLedger") || "سجلّ تداولي"}</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 7, marginBottom: 9 }}>
            <div style={{ padding: "9px 10px", background: "rgba(255,255,255,0.04)", borderRadius: 9 }}>
              <div style={{ fontSize: 10.5, color: "var(--txt-3)" }}>{t("closedTrades") || "صفقات مغلقة"}</div>
              <div style={{ fontSize: 15, fontWeight: 800 }}>
                {ledger.closed} <span style={{ fontSize: 11, color: "var(--txt-3)" }}>({ledger.open} {t("openLbl") || "مفتوحة"})</span>
              </div>
            </div>
            <div style={{ padding: "9px 10px", background: "rgba(255,255,255,0.04)", borderRadius: 9 }}>
              <div style={{ fontSize: 10.5, color: "var(--txt-3)" }}>{t("winRateLbl") || "نسبة النجاح"}</div>
              <div style={{ fontSize: 15, fontWeight: 800 }}>{ledger.win_rate}%</div>
            </div>
            <div style={{ padding: "9px 10px", background: "rgba(34,197,94,0.10)", borderRadius: 9 }}>
              <div style={{ fontSize: 10.5, color: "var(--txt-3)" }}>{t("winsLbl") || "رابحة"}</div>
              <div style={{ fontSize: 15, fontWeight: 800, color: "#22c55e" }}>{ledger.wins}</div>
            </div>
            <div style={{ padding: "9px 10px", background: "rgba(239,68,68,0.10)", borderRadius: 9 }}>
              <div style={{ fontSize: 10.5, color: "var(--txt-3)" }}>{t("lossesLbl") || "خاسرة"}</div>
              <div style={{ fontSize: 15, fontWeight: 800, color: "#ef4444" }}>{ledger.losses}</div>
            </div>
          </div>
          <div style={{
            padding: "10px 12px", borderRadius: 9, textAlign: "center",
            background: (ledger.net_usdt || 0) >= 0 ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
          }}>
            <div style={{ fontSize: 10.5, color: "var(--txt-3)" }}>{t("netRealized") || "صافي الربح الفعلي"}</div>
            <div dir="ltr" style={{ fontSize: 18, fontWeight: 800, color: (ledger.net_usdt || 0) >= 0 ? "#22c55e" : "#ef4444" }}>
              {(ledger.net_usdt || 0) >= 0 ? "+" : ""}{ledger.net_usdt} USDT
            </div>
            <div dir="ltr" style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 2 }}>
              ({(ledger.net_pct || 0) >= 0 ? "+" : ""}{ledger.net_pct}%)
            </div>
          </div>
          {(ledger.recent || []).length > 0 && (
            <div style={{ display: "grid", gap: 4, marginTop: 9 }}>
              {ledger.recent.slice(0, 8).map((r, i) => (
                <div key={i} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  fontSize: 11.5, padding: "7px 9px",
                  background: "rgba(255,255,255,0.03)", borderRadius: 7,
                }}>
                  <span><b>{r.symbol}</b> · {r.direction}
                    {r.close_reason ? <span style={{ color: "var(--txt-3)", marginInlineStart: 5 }}>· {r.close_reason}</span> : null}
                  </span>
                  <span dir="ltr" style={{ color: (r.pnl_pct || 0) >= 0 ? "#22c55e" : "#ef4444", fontWeight: 700 }}>
                    {(r.pnl_pct || 0) >= 0 ? "+" : ""}{Number(r.pnl_pct || 0).toFixed(2)}%
                    {r.pnl_usdt != null ? " · " + ((r.pnl_usdt >= 0 ? "+" : "") + Number(r.pnl_usdt).toFixed(2) + "$") : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="card">
        <div className="card-title">{t("openTrades")}</div>
        {positions.length === 0 ? (
          <div className="empty">{t("noOpenTrades")}</div>
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th>{t("coin")}</th><th>{t("direction")}</th><th>{t("entry")}</th>
                <th>{t("current")}</th><th>{t("pnl")}</th><th></th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p, i) => (
                <tr key={i}>
                  <td><b>{p.symbol}</b></td>
                  <td><span className={`badge ${p.direction === "LONG" ? "long" : "short"}`}>
                    {p.direction} {p.leverage}x
                  </span></td>
                  <td>{p.entry}</td>
                  <td>{p.current}</td>
                  <td style={{ color: p.pnl_pct >= 0 ? "var(--green)" : "var(--red)", fontWeight: 700 }}>
                    {p.pnl_pct >= 0 ? "+" : ""}{p.pnl_pct}%
                  </td>
                  <td>
                    <button onClick={() => handleClose(p.symbol)} disabled={closing === p.symbol}
                      style={{ background: "#ef4444", color: "#fff", border: "none", borderRadius: 6, padding: "4px 10px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>
                      {closing === p.symbol ? "..." : (t("closeBtn") || "إغلاق")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
