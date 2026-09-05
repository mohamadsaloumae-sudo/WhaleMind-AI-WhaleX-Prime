import { useEffect, useState } from "react";
import { T } from "./sections.js";

/**
 * 📈 شريط الأسعار والأخبار — يلفّ بلا توقّف.
 *
 * أسعار حقيقية من باينانس وعناوين من Cointelegraph. والحركة بـCSS
 * لا JavaScript، فلا تستهلك بطارية الهاتف ولا تتقطّع عند التمرير.
 * والقائمة تُكرَّر مرّتين فيبدو اللفّ متّصلاً بلا قفزة.
 */
export default function Ticker({ lang = "ar" }) {
  const ar = lang !== "en";
  const [d, setD] = useState(null);

  useEffect(() => {
    let dead = false;
    const load = () => {
      // 🌐 اللغة تُمرَّر للخادم: العربية تُترجَم والإنجليزية كما وردت
      fetch(`/api/public/ticker?lang=${ar ? "ar" : "en"}`)
        .then((r) => r.json())
        .then((x) => { if (!dead) setD(x); })
        .catch(() => {});
    };
    load();
    const id = setInterval(load, 45000);
    return () => { dead = true; clearInterval(id); };
  }, [ar]);

  if (!d || !(d.prices || []).length) return null;

  // سعران ثم خبر — فلا يطغى أحدهما
  const items = [];
  const news = d.news || [];
  let ni = 0;
  (d.prices || []).forEach((p, i) => {
    items.push({ t: "p", ...p });
    if (i % 2 === 1 && ni < news.length) items.push({ t: "n", ...news[ni++] });
  });
  while (ni < news.length) items.push({ t: "n", ...news[ni++] });

  const fmt = (v) =>
    v >= 1000 ? v.toLocaleString("en-US", { maximumFractionDigits: 0 })
    : v >= 1 ? v.toFixed(2) : v.toFixed(4);

  const Row = ({ k }) => (
    <div style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
      {items.map((x, i) => (
        <span key={`${k}${i}`} style={{
          display: "inline-flex", alignItems: "center", gap: 5,
          padding: "0 14px", fontSize: 11.5, fontWeight: 700,
          whiteSpace: "nowrap", direction: "ltr",
          borderRight: `1px solid ${T.border}`,
        }}>
          {x.t === "p" ? (
            <>
              <span style={{ color: T.txt }}>{x.symbol}</span>
              <span style={{ color: T.txt2 }}>${fmt(x.price)}</span>
              <span style={{ color: x.up ? T.brand2 : T.red, fontWeight: 800 }}>
                {x.up ? "▲" : "▼"} {Math.abs(x.change).toFixed(2)}%
              </span>
            </>
          ) : (
            <span style={{ color: T.txt3, fontWeight: 600 }}>
              📰 {x.title}
            </span>
          )}
        </span>
      ))}
    </div>
  );

  return (
    <div style={{
      background: "rgba(255,255,255,.03)",
      borderTop: `1px solid ${T.border}`,
      borderBottom: `1px solid ${T.border}`,
      overflow: "hidden", padding: "8px 0", direction: "ltr",
    }}>
      <style>{`
        @keyframes wxTicker {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
        .wx-tick { animation: wxTicker 70s linear infinite; }
        .wx-tick:hover { animation-play-state: paused; }
        @media (prefers-reduced-motion: reduce) {
          .wx-tick { animation-duration: 200s; }
        }
      `}</style>
      <div className="wx-tick" style={{ display: "flex", width: "max-content" }}>
        <Row k="a" />
        <Row k="b" />
      </div>
    </div>
  );
}
