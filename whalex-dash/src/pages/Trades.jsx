// صفقاتي
import { useEffect, useState } from "react";
import { binance } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";

export default function Trades() {
  const { t } = useLang();
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  async function load() {
    try {
      const data = await binance.positions();
      setPositions(Array.isArray(data) ? data : data?.positions || []);
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    load();
    const t2 = setInterval(load, 10000);
    return () => clearInterval(t2);
  }, []);

  if (loading) return <div className="loading">{t("loadingTrades")}</div>;

  return (
    <>
      {err && <div className="alert info">{t("tradesFetchFail")}: {err} — ({t("requiresBinance")})</div>}
      <div className="card">
        <div className="card-title">{t("openTrades")}</div>
        {positions.length === 0 ? (
          <div className="empty">{t("noOpenTrades")}</div>
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th>{t("coin")}</th><th>{t("direction")}</th><th>{t("entry")}</th>
                <th>{t("current")}</th><th>{t("leverage")}</th><th>{t("pnl")}</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p, i) => (
                <tr key={i}>
                  <td><b>{p.symbol}</b></td>
                  <td><span className={`badge ${p.direction === "LONG" || p.positionAmt > 0 ? "long" : "short"}`}>
                    {p.direction || (p.positionAmt > 0 ? "LONG" : "SHORT")}
                  </span></td>
                  <td>{p.entry_price || p.entryPrice}</td>
                  <td>{p.mark_price || p.markPrice || "—"}</td>
                  <td>{p.leverage}x</td>
                  <td style={{ color: (p.unrealized_pnl ?? p.pnl ?? p.unRealizedProfit) >= 0 ? "var(--green)" : "var(--red)", fontWeight: 700 }}>
                    {Number((p.unrealized_pnl ?? p.pnl ?? p.unRealizedProfit) || 0).toFixed(2)}
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
