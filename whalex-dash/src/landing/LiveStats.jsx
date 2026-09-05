import { useEffect, useState } from "react";
import { T } from "./sections.js";

/**
 * ② الأرقام — شبكة متناسقة: عمود لكل نظام، وصفّ لكل مقياس.
 *
 * كانت تعرض الفيوتشر وحده فلا يرى الزائر أن عندنا ثلاثة أنظمة.
 * والآن ثلاثة أعمدة (فيوتشر · سبوت · ميم) وثلاثة صفوف
 * (الصافي · الصفقات المنفَّذة · العملات المُراقَبة).
 *
 * والتجاوب عبر auto-fit: عمود على الهاتف الضيّق، وثلاثة على
 * الآيباد واللابتوب — بلا media queries.
 */
const MEME_LOGOS = [
  ["Solana", "https://s2.coinmarketcap.com/static/img/coins/64x64/5426.png"],
  ["Ethereum", "https://s2.coinmarketcap.com/static/img/coins/64x64/1027.png"],
  ["Base", "https://s2.coinmarketcap.com/static/img/coins/64x64/27716.png"],
  ["DexScreener", "https://dexscreener.com/favicon.png"],
];

export default function LiveStats({ lang = "ar" }) {
  const ar = lang !== "en";
  const [s, setS] = useState(null);

  useEffect(() => {
    fetch("/api/public/stats")
      .then((r) => r.json())
      .then(setS)
      .catch(() => {});
  }, []);

  if (!s) return null;
  const sys = s.systems || {};

  const COLS = [
    { k: "futures", icon: "⚡", en: "Futures", ar: "فيوتشر", coins: s.coins },
    { k: "spot", icon: "🪙", en: "Spot", ar: "سبوت",
      coins: s.spot_coins || 372 },
    { k: "meme", icon: "🐸", en: "Meme", ar: "ميم", coins: null },
  ].filter((x) => sys[x.k]);

  const fmt = (n) => `${n >= 0 ? "+" : ""}${Number(n).toFixed(1)}%`;
  const box = {
    background: T.card, border: `1px solid ${T.border}`,
    borderRadius: 12, padding: "12px 8px", textAlign: "center",
  };
  const lbl = { fontSize: 9.5, color: T.txt3, fontWeight: 600, marginTop: 4 };

  return (
    <section style={{ padding: "0 16px 34px", background: T.bg }}>
      <div style={{
        maxWidth: 700, margin: "0 auto",
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(105px, 1fr))",
        gap: 8,
      }}>
        {COLS.map((x) => (
          <div key={`h${x.k}`} style={{
            textAlign: "center", fontSize: 11.5, fontWeight: 800,
            color: T.txt, padding: "2px 0 4px", letterSpacing: .2,
          }}>
            {x.icon} {ar ? x.ar : x.en}
          </div>
        ))}

        {COLS.map((x) => {
          const d = sys[x.k] || {};
          const up = (d.net_pct || 0) >= 0;
          return (
            <div key={`n${x.k}`} style={{
              ...box,
              border: `1px solid ${up ? T.brand2 + "44" : T.red + "33"}`,
            }}>
              <div style={{
                fontSize: 19, fontWeight: 900, direction: "ltr",
                color: up ? T.brand2 : T.red, letterSpacing: -.4,
              }}>{fmt(d.net_pct || 0)}</div>
              <div style={lbl}>{ar ? "صافي الشهر" : "Net month"}</div>
            </div>
          );
        })}

        {COLS.map((x) => {
          const d = sys[x.k] || {};
          return (
            <div key={`t${x.k}`} style={box}>
              <div style={{
                fontSize: 19, fontWeight: 900, color: T.txt,
                direction: "ltr", letterSpacing: -.4,
              }}>{d.trades || 0}</div>
              <div style={lbl}>
                {ar ? "صفقة منفَّذة" : "Trades executed"}
              </div>
            </div>
          );
        })}

        {COLS.map((x) => (
          <div key={`c${x.k}`} style={box}>
            {x.coins != null ? (
              <>
                <div style={{
                  fontSize: 19, fontWeight: 900, color: T.brand,
                  direction: "ltr", letterSpacing: -.4,
                }}>{x.coins}</div>
                <div style={lbl}>{ar ? "عملة تُراقَب" : "Coins watched"}</div>
              </>
            ) : (
              <>
                <div style={{
                  display: "flex", justifyContent: "center",
                  alignItems: "center", height: 25, gap: 2,
                }}>
                  {MEME_LOGOS.map(([nm, src]) => (
                    <span key={nm} title={nm} style={{
                      width: 21, height: 21, borderRadius: 5,
                      background: "rgba(255,255,255,.06)",
                      border: `1px solid ${T.border}`,
                      display: "inline-flex", alignItems: "center",
                      justifyContent: "center", overflow: "hidden",
                    }}>
                      <img src={src} alt={nm}
                        style={{ width: 15, height: 15, objectFit: "contain" }}
                        onError={(e) => { e.currentTarget.style.opacity = 0; }}
                      />
                    </span>
                  ))}
                </div>
                <div style={lbl}>{ar ? "المصادر" : "Sources"}</div>
              </>
            )}
          </div>
        ))}
      </div>

      <p style={{
        textAlign: "center", fontSize: 10.5, color: T.txt3,
        marginTop: 14, lineHeight: 1.7,
      }}>
        {ar
          ? `أرقام مباشرة من سجلّ النظام · ${s.exchanges} منصّات`
          : `Live from the system log · ${s.exchanges} exchanges`}
      </p>
    </section>
  );
}
