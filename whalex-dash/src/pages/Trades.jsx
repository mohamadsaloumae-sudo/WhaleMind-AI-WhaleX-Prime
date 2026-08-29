// صفقاتي — صفقات Binance الحقيقية (حيّة + زرّ إغلاق)
import { useEffect, useState } from "react";
import { livePositions, api } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import TradeLedger from "../components/TradeLedger.jsx";

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

      <TradeLedger data={ledger} ar={(localStorage.getItem("whalex_lang") || "ar") !== "en"} />

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
