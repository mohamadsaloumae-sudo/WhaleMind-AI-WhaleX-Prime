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

  const [_tab, _setTab] = useState("futures");
  const [spotClosed, setSpotClosed] = useState([]);

  async function load() {
    try {
      const data = await livePositions.binance();
      // 🪙 صفقات السبوت لم تكن تظهر اطلاقاً — جدول منفصل ومسار
      //    منفصل. نجلبها وندمجها بالترتيب الزمنيّ نفسه.
      let _spot = [];
      try {
        const _sr = await fetch("/api/live/my-spot-positions", {
          headers: { Authorization:
            `Bearer ${localStorage.getItem("wx_token") || ""}` },
        }).then((x) => x.json());
        _spot = Array.isArray(_sr?.positions) ? _sr.positions : [];
      } catch { /* السبوت اختياريّ */ }
      // 🗄️ سجلّ السبوت المغلق — كان يختفي بلا اثر عند الاغلاق.
      try {
        const _cr = await fetch("/api/live/my-spot-closed", {
          headers: { Authorization:
            `Bearer ${localStorage.getItem("wx_token") || ""}` },
        }).then((x) => x.json());
        setSpotClosed(Array.isArray(_cr?.trades) ? _cr.trades : []);
      } catch { /* اختياريّ */ }
      const _fut = Array.isArray(data?.positions) ? data.positions : [];
      const _all = [
        ..._fut.map((x) => ({ ...x, _kind: "futures" })),
        ..._spot.map((x) => ({ ...x, _kind: "spot",
                               leverage: x.leverage || 1 })),
      ].sort((a, b) =>
        (Number(b?.opened_at ?? 0) || 0) - (Number(a?.opened_at ?? 0) || 0));
      setPositions(_all);
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

  // 🔀 تبويبان داخل الصفحة — فصل تامّ بين الفيوتشر والسبوت
  //    حتى لا تختلط صفقات نظامين مختلفين على المشترك.
  const _isSpot = (x) => x?._kind === "spot";
  const _shown = (positions || []).filter((x) =>
    _tab === "spot" ? _isSpot(x) : !_isSpot(x));
  const _cnt = {
    futures: (positions || []).filter((x) => !_isSpot(x)).length,
    spot: (positions || []).filter(_isSpot).length,
  };

  return (
    <>
      {!connected && <div className="alert info">{t("requiresBinance")}</div>}
      {msg && <div className="card" style={{ marginBottom: 12, padding: 10, fontSize: 13, textAlign: "center" }}>{msg}</div>}

      <TradeLedger data={ledger} ar={(localStorage.getItem("whalex_lang") || "ar") !== "en"} />

      <div className="card">
        <div className="card-title">{t("openTrades")}</div>
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          {[["futures", "⚡", "فيوتشر", "Futures"],
            ["spot", "🪙", "سبوت", "Spot"]].map(([k, ic, ar, en]) => (
            <button key={k} onClick={() => _setTab(k)} style={{
              flex: 1, padding: "9px 6px", borderRadius: 10,
              border: _tab === k ? "1px solid var(--brand)"
                                 : "1px solid var(--border)",
              background: _tab === k ? "rgba(45,212,191,.12)" : "transparent",
              color: _tab === k ? "var(--brand)" : "var(--txt2)",
              fontWeight: 700, fontSize: 13, cursor: "pointer",
              fontFamily: "inherit",
            }}>
              {ic} {(localStorage.getItem("whalex_lang") || "ar") !== "en"
                    ? ar : en} ({_cnt[k]})
            </button>
          ))}
        </div>
        {_shown.length === 0 ? (
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
              {_shown.map((p, i) => (
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
