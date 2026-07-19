// الإشارات الحيّة
import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { trStrat } from "../lib/strats.js";
import { getMarket } from "../hooks/useMarket.js";
import Paywall from "../components/Paywall.jsx";


function useLangSpotMsg() {
  const ar = (localStorage.getItem("wx_lang") || document.documentElement.lang || "ar") !== "en";
  return ar ? "رادار السبوت قيد الإطلاق — المرحلة الثانية 🚧" : "Spot radar launching — phase 2 🚧";
}

const fmtPx = (n) => { const v = Number(n) || 0; return v >= 100 ? v.toFixed(2) : v >= 1 ? v.toFixed(3) : v >= 0.01 ? v.toFixed(4) : v.toFixed(6); };

export default function Signals() {
  const { t, lang } = useLang();
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  async function load() {
    try {
      const data = await api.get(`/api/signals/all?market=${getMarket()}`);
      setSignals(Array.isArray(data) ? data : data?.signals || []);
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    load();
    const tm = setInterval(load, 15000);
    return () => clearInterval(tm);
  }, []);

  if (loading) return <div className="loading">{t("loadingSignals")}</div>;

  return (
    <Paywall>
    <>
      {err && <div className="alert info">{t("signalsFetchFail")}: {err}</div>}
      {getMarket() === "spot" && signals.length === 0 ? (
        <div style={{ textAlign: "center", padding: 40, color: "var(--txt-2)" }}>
          🪙 {"" }{useLangSpotMsg()}
        </div>
      ) : signals.length === 0 ? (
        <div className="card"><div className="empty">{t("noSignals")}</div></div>
      ) : getMarket() === "meme" ? (
        <div className="grid grid-3">
          {signals.map((s, i) => (
            <div className="card" key={i}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                <strong>{s.symbol}</strong>
                <span className="badge" style={{ background: "rgba(74,222,128,0.15)", color: "var(--brand)" }}>{s.score}/100</span>
              </div>
              <div style={{ fontSize: 13, color: "var(--txt-2)", display: "grid", gap: 6 }}>
                <div>🌐 {lang === "ar" ? "الشبكة" : "Chain"}: <b style={{ color: "var(--txt-1)" }}>{s.chain}</b></div>
                <div>💧 {lang === "ar" ? "السيولة" : "Liquidity"}: <b>${Number(s.liq || 0).toLocaleString()}</b></div>
                <div>📊 {lang === "ar" ? "الحجم 24س" : "Volume 24h"}: <b>${Number(s.vol || 0).toLocaleString()}</b></div>
                <span className="badge" style={{ background: "rgba(74,222,128,0.15)", color: "var(--brand)", width: "fit-content" }}>✅ {lang === "ar" ? "اجتاز كل الفيتوهات" : "Passed all vetoes"}</span>
                {s.url ? <a href={s.url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", fontSize: 12.5 }}>🔗 DexScreener</a> : null}
                <div style={{ color: "var(--txt-3)", fontSize: 12, marginTop: 4 }}>🕐 {s.created_at ? new Date(s.created_at.replace(" ", "T") + "Z").toLocaleString(lang === "ar" ? "ar-AE" : "en-US", { timeZone: "Asia/Dubai", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : ""}</div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-3">
          {signals.map((s, i) => (
            <div className="card" key={i}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                <strong>{s.symbol}</strong>
                <span className={`badge ${s.direction === "LONG" ? "long" : "short"}`}>{s.direction}</span>
              </div>
              <div style={{ fontSize: 13, color: "var(--txt-2)", display: "grid", gap: 6 }}>
                <div>{t("entry")}: <b style={{ color: "var(--txt-1)" }}>{fmtPx(s.entry)}</b></div>
                <div>{t("stopLoss")}: {fmtPx(s.sl)}</div>
                <div>{t("target")} 1: <b style={{ color: "var(--green)" }}>{fmtPx(s.tp1)}</b></div>
                <div>{t("target")} 2: <b style={{ color: "var(--green)" }}>{fmtPx(s.tp2)}</b></div>
                <div>{t("target")} 3: <b style={{ color: "var(--green)" }}>{fmtPx(s.tp3)}</b></div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 4 }}>
                  <span className="badge" style={{ background: "rgba(99,102,241,0.15)", color: "var(--accent)" }}>{s.radar_type === "spot" ? "🪙 WhaleX Spot" : s.radar_type === "explosion" ? (s.direction === "SHORT" ? "🎯 WhaleX Short" : "📈 WhaleX Long") : "⚡ WhaleX Predator"}</span>
                </div>
                {s.strategies && (
                  <div style={{ display: "grid", gap: 4, marginTop: 6, marginBottom: 6 }}>
                    {s.strategies.split("\n").filter(Boolean).map((line, k) => (
                      <div key={k} style={{ fontSize: 12.5, color: "var(--txt-1)", background: "var(--bg-2)", padding: "5px 9px", borderRadius: 7 }}>{trStrat(line, lang)}</div>
                    ))}
                  </div>
                )}
                <div>{t("grade")}: <span className="badge" style={{ background: s.grade === "B" ? "rgba(245,158,11,0.18)" : "rgba(45,212,191,0.15)", color: s.grade === "B" ? "var(--amber)" : "var(--brand)" }}>{s.grade}{s.grade === "B" ? " ⚠️" : ""}</span> · {t("confidence")} {s.confidence}%{s.leverage ? <> · <span className="badge" style={{ background: "rgba(99,102,241,0.15)", color: "#a5b4fc" }}>{Math.round(s.leverage)}x</span></> : null}</div>
                <div style={{ color: "var(--txt-3)", fontSize: 12, marginTop: 4 }}>
                  🕐 {s.created_at ? new Date(s.created_at.replace(" ", "T") + "Z").toLocaleString(lang === "ar" ? "ar-AE" : "en-US", { timeZone: "Asia/Dubai", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : ""}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
    </Paywall>
  );
}
