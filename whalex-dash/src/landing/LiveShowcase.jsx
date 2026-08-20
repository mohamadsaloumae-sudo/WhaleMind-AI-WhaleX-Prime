import { useEffect, useState } from "react";
import { T } from "./sections.js";

const EX = {
  binance: ["Binance", "https://s2.coinmarketcap.com/static/img/exchanges/64x64/270.png"],
  bybit: ["Bybit", "https://s2.coinmarketcap.com/static/img/exchanges/64x64/521.png"],
  mexc: ["MEXC", "https://s2.coinmarketcap.com/static/img/exchanges/64x64/544.png"],
  bingx: ["BingX", "https://s2.coinmarketcap.com/static/img/exchanges/64x64/1064.png"],
  bitget: ["Bitget", "https://s2.coinmarketcap.com/static/img/exchanges/64x64/513.png"],
  gate: ["Gate.io", "https://s2.coinmarketcap.com/static/img/exchanges/64x64/302.png"],
  okx: ["OKX", "https://s2.coinmarketcap.com/static/img/exchanges/64x64/294.png"],
};

/**
 * التوقيع — صفقة حقيقية مفتوحة الآن.
 * المنافسون يعرضون نموذجاً مكتوباً يدوياً. هذه تُجلب من قاعدتنا
 * وتتحدّث كل 20 ثانية — لا تُزيَّف بلا نظام حقيقي خلفها.
 */
export default function LiveShowcase({ lang = "ar" }) {
  const ar = lang !== "en";
  const [p, setP] = useState(null);
  const [pulse, setPulse] = useState(false);

  useEffect(() => {
    let dead = false;
    const load = async () => {
      try {
        const r = await fetch("/api/public/showcase");
        const d = await r.json();
        if (!dead && d && d.symbol) {
          setP(d);
          setPulse(true);
          setTimeout(() => setPulse(false), 700);
        }
      } catch { /* الصمت أفضل من خطأ في صفحة تعريفية */ }
    };
    load();
    const id = setInterval(load, 8000);
    return () => { dead = true; clearInterval(id); };
  }, []);

  if (!p) return null;

  const up = p.pnl_pct >= 0;
  const col = up ? T.brand2 : T.red;
  const ex = EX[String(p.exchange || "").toLowerCase()] || ["", ""];
  const isLong = p.direction === "LONG";

  const prog = (() => {
    const sl = Number(p.sl), tp = Number(p.tp1), cur = Number(p.current);
    if (!sl || !tp || !cur) return null;
    const lo = Math.min(sl, tp), hi = Math.max(sl, tp);
    if (hi <= lo) return null;
    const r = ((cur - lo) / (hi - lo)) * 100;
    return Math.max(0, Math.min(100, isLong ? r : 100 - r));
  })();

  const age = (() => {
    if (!p.opened_at) return "";
    const m = Math.round((Date.now() / 1000 - p.opened_at) / 60);
    if (m < 60) return ar ? `منذ ${m} دقيقة` : `${m}m`;
    return ar ? `منذ ${Math.floor(m / 60)} ساعة` : `${Math.floor(m / 60)}h`;
  })();

  return (
    <section style={{ padding: "4px 20px 32px", background: T.bg }}>
      <div style={{
        maxWidth: 420, margin: "0 auto", borderRadius: 18, overflow: "hidden",
        background: "linear-gradient(165deg, rgba(255,255,255,.05), rgba(255,255,255,.02))",
        border: `1px solid ${col}33`,
        boxShadow: "0 18px 50px rgba(0,0,0,.45)",
      }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "9px 15px", borderBottom: `1px solid ${T.border}`,
          background: "rgba(255,255,255,.02)",
        }}>
          <span style={{
            width: 7, height: 7, borderRadius: 7, background: T.red,
            boxShadow: `0 0 10px ${T.red}`,
            animation: "wxPulse 1.6s ease-in-out infinite",
          }} />
          <span style={{ fontSize: 10.5, fontWeight: 800, letterSpacing: .8, color: T.red }}>
            {ar ? "مباشر" : "LIVE"}
          </span>
          <span style={{ fontSize: 10.5, color: T.txt3, marginInlineStart: "auto" }}>
            {ar ? "صفقة مفتوحة الآن" : "Open right now"}
          </span>
        </div>

        <div style={{ padding: "16px 17px 18px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 13 }}>
            {ex[1] ? (
              <img src={ex[1]} alt={ex[0]} width="24" height="24"
                   style={{ borderRadius: 6 }}
                   onError={(e) => { e.target.style.display = "none"; }} />
            ) : null}
            <span style={{ fontSize: 15.5, fontWeight: 800, color: T.txt, direction: "ltr" }}>
              {p.symbol}
            </span>
            <span style={{
              fontSize: 10, fontWeight: 800, padding: "3px 8px", borderRadius: 6,
              background: isLong ? "rgba(34,197,94,.14)" : "rgba(239,68,68,.14)",
              color: isLong ? T.brand2 : T.red,
            }}>
              {p.direction} {Math.round(p.leverage)}x
            </span>
            <span style={{ fontSize: 10.5, color: T.txt3, marginInlineStart: "auto" }}>
              {ex[0]}
            </span>
          </div>

          <div style={{
            display: "flex", alignItems: "baseline", justifyContent: "center",
            gap: 11, marginBottom: 10, direction: "ltr",
          }}>
            <span style={{ fontSize: 15, color: T.txt3 }}>{p.entry}</span>
            <span style={{ fontSize: 13, color: T.txt3 }}>&rarr;</span>
            <span style={{
              fontSize: 19, fontWeight: 800, color: T.txt,
              transition: "opacity .35s", opacity: pulse ? .45 : 1,
            }}>{p.current}</span>
          </div>

          <div style={{
            textAlign: "center", fontSize: 36, fontWeight: 900, color: col,
            letterSpacing: -1, marginBottom: prog != null ? 14 : 4,
            textShadow: `0 0 34px ${col}44`, direction: "ltr",
          }}>
            {up ? "+" : ""}{p.pnl_pct.toFixed(2)}%
          </div>

          {prog != null && (
            <>
              <div style={{
                height: 5, borderRadius: 5, overflow: "hidden",
                background: "rgba(255,255,255,.06)", marginBottom: 7,
              }}>
                <div style={{
                  width: `${prog}%`, height: "100%", borderRadius: 5,
                  background: `linear-gradient(90deg, ${T.red}, ${T.gold}, ${T.brand2})`,
                  transition: "width .6s ease",
                }} />
              </div>
              <div style={{
                display: "flex", justifyContent: "space-between",
                fontSize: 9.5, color: T.txt3, direction: "ltr",
              }}>
                <span>{ar ? "وقف" : "Stop"} {p.sl}</span>
                <span>{age}</span>
                <span>{ar ? "هدف" : "Target"} {Number(p.tp1).toFixed(4)}</span>
              </div>
            </>
          )}
        </div>
      </div>

      <p style={{
        textAlign: "center", fontSize: 11, color: T.txt3,
        marginTop: 13, maxWidth: 380, marginInline: "auto", lineHeight: 1.7,
      }}>
        {ar
          ? "ليست صورة إعلانية — صفقة يديرها النظام الآن، تتحدّث كل ثماني ثوانٍ."
          : "Not a mockup — a live position the system is managing, refreshed every 8s."}
      </p>

      <style>{"@keyframes wxPulse{0%,100%{opacity:1}50%{opacity:.25}}"}</style>
    </section>
  );
}
