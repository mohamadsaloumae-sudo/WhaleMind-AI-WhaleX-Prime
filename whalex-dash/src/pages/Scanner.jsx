import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";

const V = {
  LONG:  { ar: "صالحة لونغ", en: "LONG setup",  ic: "🟢", c: "var(--green)" },
  SHORT: { ar: "صالحة شورت", en: "SHORT setup", ic: "🔴", c: "var(--red)" },
  WAIT:  { ar: "انتظار",      en: "WAIT",        ic: "⏸", c: "var(--amber)" },
};
const SPOT_V = {
  LONG:  { ar: "شراء الآن", en: "BUY now" },
  SHORT: { ar: "لا تشترِ",  en: "Don't buy" },
  WAIT:  { ar: "انتظار",    en: "WAIT" },
};
const EX_LOGO = {
  binance: "270", bybit: "521", okx: "294",
  bitget: "513", mexc: "544", gate: "302", bingx: "1064",
};
const LS_KEY = "wx_scanner_recent";
// 🔗 أسماء الروابط الرسمية
const LNK = {
  website: ["الموقع", "Website"], explorer: ["المستكشف", "Explorer"],
  source_code: ["الكود", "Source"], reddit: ["ريديت", "Reddit"],
  twitter: ["إكس", "X"], telegram: ["تيليجرام", "Telegram"],
  medium: ["ميديوم", "Medium"], youtube: ["يوتيوب", "YouTube"],
  facebook: ["فيسبوك", "Facebook"],
};

const fmtUsd = (n) => {
  if (n == null) return "—";
  const v = Number(n);
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(2)}`;
};
const fmtPx = (n) => {
  const v = Number(n);
  if (!v) return "—";
  return v >= 1 ? v.toFixed(v >= 1000 ? 0 : 2) : v.toPrecision(4);
};

export default function Scanner() {
  const { lang } = useLang();
  const ar = lang === "ar";
  const [sym, setSym] = useState("");
  const [sug, setSug] = useState([]);
  const [open, setOpen] = useState(false);
  const [r, setR] = useState(null);
  const [mkt, setMkt] = useState(null);
  const [busy, setBusy] = useState(false);
  const [chart, setChart] = useState(false);
  // 🔀 السوق المختار — فيوتشر أو سبوت. الحكم يتبعه.
  const [mode, setMode] = useState("futures");
  const [expand, setExpand] = useState(false);
  const [recent, setRecent] = useState(() => {
    try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); }
    catch { return []; }
  });
  const boxRef = useRef(null);

  useEffect(() => {
    const q = sym.trim();
    if (!q) { setSug([]); return; }
    let dead = false;
    if (r && r.symbol && r.symbol.replace("USDT", "") === q) return;
    const t = setTimeout(async () => {
      try {
        const d = await api.get(`/api/scanner/symbols?q=${encodeURIComponent(q)}&limit=14`);
        if (!dead) { setSug(d.symbols || []); setOpen(true); }
      } catch { /* الصمت أفضل */ }
    }, 180);
    return () => { dead = true; clearTimeout(t); };
  }, [sym]);

  useEffect(() => {
    const h = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  async function go(s) {
    const q = (s || sym).trim().toUpperCase();
    if (!q || busy) return;
    // 🔽 نُغلق أوّلاً — كان الإغلاق بعد setBusy فتبقى ظاهرة
    setOpen(false); setSug([]);
    setBusy(true); setR(null); setMkt(null); setChart(false);
    setOpen(false); setSug([]);   // 🔽 تُغلق فوراً عند الاختيار
    setSym(q);
    const next = [q, ...recent.filter((x) => x !== q)].slice(0, 10);
    setRecent(next);
    try { localStorage.setItem(LS_KEY, JSON.stringify(next)); } catch { /* */ }
    const [sc, mk] = await Promise.allSettled([
      api.get(`/api/scanner/scan?symbol=${encodeURIComponent(q)}`),
      api.get(`/api/scanner/market?symbol=${encodeURIComponent(q)}`),
    ]);
    setR(sc.status === "fulfilled" ? sc.value : { ok: false });
    setMkt(mk.status === "fulfilled" ? mk.value : null);
    setBusy(false);
  }

  const Row = ({ l, v, c, hint }) => (
    <div style={{
      display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center",
      columnGap: 14, padding: "9px 12px", borderRadius: 9,
      background: "var(--bg-0)", marginBottom: 5, minHeight: 40,
    }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ color: "var(--txt-2)", fontSize: 12.5, fontWeight: 600 }}>{l}</div>
        {hint && (
          <div style={{ color: "var(--txt-3)", fontSize: 10.5, marginTop: 2, lineHeight: 1.4 }}>{hint}</div>
        )}
      </div>
      <b style={{
        color: c || "var(--txt-0)", direction: "ltr", fontSize: 14,
        whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums",
      }}>{v}</b>
    </div>
  );

  const Sec = ({ t }) => (
    <div style={{
      display: "flex", alignItems: "center", gap: 9, margin: "16px 0 9px",
    }}>
      <span style={{ color: "var(--txt-2)", fontSize: 11.5, fontWeight: 800, whiteSpace: "nowrap" }}>{t}</span>
      <span style={{ flex: 1, height: 1, background: "var(--bg-2)" }} />
    </div>
  );

  const m = mkt?.market || {};
  const pj = mkt?.project || {};
  const isFut = !!mkt?.futures;
  const useFut = mode === "futures" && isFut;
  const verdict = r?.ok && useFut ? V[r.verdict] : null;

  // حكم السبوت من الخادم — مقياسه الاتّجاه لا الضغط اللحظيّ
  const spotV = (() => {
    if (!r?.ok) return null;
    return r.spot_verdict || "WAIT";
  })();
  const SPOT_C = { LONG: "var(--green)", SHORT: "var(--red)", WAIT: "var(--amber)" };
  const SPOT_IC = { LONG: "\u{1F7E2}", SHORT: "\u{1F534}", WAIT: "\u23F8" };

  return (
    <div style={{ padding: 16, maxWidth: 560, margin: "0 auto" }}>
      <h2 style={{ marginBottom: 3, fontSize: 20 }}>🔍 WhaleX Scanner</h2>
      <div style={{ color: "var(--txt-3)", fontSize: 12.5, marginBottom: 14 }}>
        {ar
          ? "افحص أي عملة على سبع منصّات — الحكم والمؤشّرات وبيانات السوق"
          : "Scan any coin across seven venues — verdict, indicators, market data"}
      </div>

      <div style={{ display: "flex", gap: 7, marginBottom: 11 }}>
        {[["futures", "العقود الآجلة", "Futures"],
          ["spot", "العقود الفورية", "Spot"]].map(([k, a, e]) => (
          <button key={k} onClick={() => setMode(k)} style={{
            flex: 1, padding: "9px 0", borderRadius: 11, fontSize: 12.5,
            fontWeight: 700, cursor: "pointer",
            border: `1px solid ${mode === k ? "var(--brand)" : "var(--bg-2)"}`,
            background: mode === k ? "rgba(45,212,191,.12)" : "var(--bg-1)",
            color: mode === k ? "var(--brand)" : "var(--txt-3)",
          }}>{ar ? a : e}</button>
        ))}
      </div>

      {recent.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
          {recent.map((x) => (
            <button key={x} onClick={() => go(x)} style={{
              padding: "4px 10px", borderRadius: 20, fontSize: 11.5,
              border: "1px solid var(--bg-2)", background: "var(--bg-1)",
              color: "var(--txt-2)", cursor: "pointer", fontWeight: 600,
              direction: "ltr",
            }}>{x}</button>
          ))}
        </div>
      )}

      <div ref={boxRef} style={{ position: "relative" }}>
        <div style={{ display: "flex", gap: 8 }}>
          <div style={{ flex: 1, position: "relative" }}>
            <span style={{
              position: "absolute", insetInlineStart: 11, top: "50%",
              transform: "translateY(-50%)", opacity: .5, fontSize: 14,
            }}>🔍</span>
            <input value={sym}
              onChange={(e) => setSym(e.target.value.toUpperCase())}
              onFocus={() => sug.length && setOpen(true)}
              onKeyDown={(e) => e.key === "Enter" && go()}
              style={{
                width: "100%", padding: "10px 12px", paddingInlineStart: 32,
                borderRadius: 10, border: "1px solid var(--bg-2)",
                background: "var(--bg-1)", color: "var(--txt-0)",
                fontSize: 14, direction: "ltr",
              }} />
          </div>
          <button onClick={() => go()} disabled={busy} style={{
            padding: "10px 18px", borderRadius: 10, border: 0,
            background: "var(--brand)", color: "#04211c", fontWeight: 700,
            cursor: busy ? "wait" : "pointer",
          }}>{busy ? "…" : ar ? "افحص" : "Scan"}</button>
        </div>

        {open && sug.length > 0 && (
          <div style={{
            position: "absolute", top: "calc(100% + 6px)", left: 0, right: 0,
            background: "var(--bg-1)", zIndex: 60,
            border: "1px solid var(--bg-2)", borderRadius: 12,
            maxHeight: 260, overflowY: "auto", direction: "ltr",
            boxShadow: "0 16px 40px rgba(0,0,0,.6)",
          }}>
            {sug.map((x) => (
              <div key={x} onClick={() => go(x)} style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "11px 14px", cursor: "pointer", fontSize: 14,
                borderBottom: "1px solid var(--bg-2)",
                fontWeight: 700, letterSpacing: .3, textAlign: "left",
              }}>
                <img alt="" width="20" height="20" loading="lazy"
                  src={`https://assets.coincap.io/assets/icons/${x.toLowerCase()}@2x.png`}
                  style={{ borderRadius: 20, flexShrink: 0 }}
                  onError={(e) => { e.currentTarget.style.visibility = "hidden"; }} />
                <span style={{ color: "var(--txt-0)" }}>{x}</span>
                <span style={{ color: "var(--txt-3)", fontSize: 11,
                               fontWeight: 500 }}>USDT</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {busy && (
        <div style={{ marginTop: 18, color: "var(--txt-3)", fontSize: 13 }}>
          {ar ? "جارٍ الفحص على المنصّات…" : "Scanning venues…"}
        </div>
      )}

      {mkt && mkt.venues?.length > 0 && (
        <div className="card" style={{
          marginTop: 14, padding: 12, borderRadius: 14, background: "var(--bg-1)",
        }}>
          <div style={{
            display: "flex", justifyContent: "space-between",
            alignItems: "center", marginBottom: 8,
          }}>
            <span style={{ fontSize: 11.5, color: "var(--txt-3)", fontWeight: 600 }}>
              {ar ? "متاحة على" : "Available on"}
            </span>
            <button onClick={() => setChart(true)} title={ar ? "الرسم" : "Chart"}
              style={{
                border: 0, background: "transparent", cursor: "pointer",
                padding: 2, lineHeight: 0,
              }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <line x1="7" y1="3" x2="7" y2="21" stroke="var(--brand)"
                      strokeWidth="1.4" />
                <rect x="4.4" y="7" width="5.2" height="8" rx="1"
                      fill="var(--brand)" />
                <line x1="16.5" y1="3" x2="16.5" y2="21" stroke="var(--txt-3)"
                      strokeWidth="1.4" />
                <rect x="13.9" y="10" width="5.2" height="7" rx="1"
                      fill="var(--txt-3)" />
              </svg>
            </button>
          </div>
          <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
            {mkt.venues.map((v) => (
              <div key={v.id} style={{
                display: "flex", alignItems: "center", gap: 5,
                padding: "5px 9px", borderRadius: 9,
                background: "var(--bg-2)", fontSize: 11, fontWeight: 600,
              }}>
                <img alt={v.name} width="15" height="15"
                  src={`https://s2.coinmarketcap.com/static/img/exchanges/64x64/${EX_LOGO[v.id] || "270"}.png`}
                  style={{ borderRadius: 4 }}
                  onError={(e) => { e.currentTarget.style.display = "none"; }} />
                <span>{v.name}</span>
                <span style={{ color: v.futures ? "var(--brand)" : "var(--txt-3)", fontSize: 9.5 }}>
                  {v.futures ? "SPOT+FUT" : "SPOT"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {r && r.ok && (
        <div className="card" style={{
          marginTop: 12, padding: 14, borderRadius: 14, background: "var(--bg-1)",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <b style={{ fontSize: 18, direction: "ltr" }}>{r.symbol}</b>
              {m.name && <span style={{ color: "var(--txt-3)", fontSize: 12, marginInlineStart: 9, opacity: .75 }}>· {m.name}</span>}
            </div>
            {verdict ? (
              <span style={{ color: verdict.c, fontWeight: 800, fontSize: 12.5, padding: "5px 11px", borderRadius: 20, whiteSpace: "nowrap", background: "color-mix(in srgb, " + verdict.c + " 13%, transparent)", border: "1px solid color-mix(in srgb, " + verdict.c + " 35%, transparent)" }}>
                {verdict.ic} {ar ? verdict.ar : verdict.en}
              </span>
            ) : (
              <span style={{ color: SPOT_C[spotV], fontWeight: 800, fontSize: 12.5, padding: "5px 11px", borderRadius: 20, whiteSpace: "nowrap", background: "color-mix(in srgb, " + SPOT_C[spotV] + " 13%, transparent)", border: "1px solid color-mix(in srgb, " + SPOT_C[spotV] + " 35%, transparent)" }}>
                {SPOT_IC[spotV]} {ar ? SPOT_V[spotV]?.ar : SPOT_V[spotV]?.en}
              </span>
            )}
          </div>

          {mode === "futures" && !isFut && (
            <div style={{
              marginTop: 8, padding: "7px 10px", borderRadius: 9, fontSize: 11.5,
              background: "rgba(245,158,11,.1)", color: "var(--amber)",
            }}>
              {ar
                ? "غير مُدرجة في الفيوتشر — الحكم للتداول الفوريّ فقط"
                : "Not listed on futures — spot verdict only"}
            </div>
          )}

          <div style={{ fontSize: 12.5, color: "var(--txt-2)", margin: "9px 0 10px", lineHeight: 1.7 }}>
            {useFut ? (ar ? r.reason : r.reason_en) : (ar ? r.spot_reason : r.spot_reason_en)}
          </div>
          <div style={{
            fontSize: 12.5, lineHeight: 1.9, background: "var(--bg-2)",
            padding: "11px 13px", borderRadius: 10, marginBottom: 12,
          }}>
            <div style={{
              direction: ar ? "rtl" : "ltr",
              textAlign: ar ? "right" : "left",
              unicodeBidi: "plaintext", lineHeight: 2,
            }}>{ar ? r.brief : r.brief_en}</div>
          </div>

          <Sec t={ar ? "المؤشّرات الفنّية" : "Technical indicators"} />
          <Row l={ar ? "السعر الحيّ" : "Live price"} v={`$${fmtPx(m.price ?? r.price)}`} />
          <Row l={ar ? "تغيّر 24 ساعة" : "24h change"}
            v={`${(m.change24h ?? r.change24h) > 0 ? "+" : ""}${Number(m.change24h ?? r.change24h).toFixed(2)}%`}
            c={(m.change24h ?? r.change24h) >= 0 ? "var(--green)" : "var(--red)"} />
          <Row l="RSI" v={r.rsi} hint={ar ? (r.rsi > 70 ? "فوق 70 — متشبّعة شرائياً" : r.rsi < 30 ? "تحت 30 — متشبّعة بيعاً" : "بين 30 و70 — منطقة متوازنة") : "Momentum gauge (30-70 balanced)"} />
          <Row l={ar ? "موقع النطاق" : "Range position"} v={`${Math.round(r.range_pos * 100)}%`} hint={ar ? (r.range_pos > 0.75 ? "قرب قمّة الثمانية أيام — الشراء هنا مكلف" : r.range_pos < 0.25 ? "قرب قاع الثمانية أيام — سعر منخفض" : "وسط نطاق الثمانية أيام") : "Where price sits in the 8-day range"} />
          {useFut && r.lev != null && (
            <Row l={ar ? "الرافعة المقترحة" : "Suggested leverage"} v={`${r.lev}x`} c="var(--brand)" hint={ar ? "تضاعف الربح والخسارة معاً بنفس المقدار" : "Multiplies both profit and loss equally"} />
          )}

          {m.rank && (
            <>
              <Sec t={ar ? "بيانات السوق" : "Market data"} />
              <Row l={ar ? "الترتيب العالميّ" : "Global rank"} v={ar ? `#${m.rank}` : `#${m.rank}`} hint={ar ? (m.rank <= 20 ? "من كبار السوق — سيولة عالية" : m.rank <= 100 ? "عملة متوسّطة الحجم" : "عملة صغيرة — تقلّب أعلى") : "Market cap ranking"} />
              <Row l={ar ? "القيمة السوقية" : "Market cap"} v={fmtUsd(m.market_cap)} />
              <Row l={ar ? "حجم 24 ساعة" : "24h volume"} v={fmtUsd(m.vol24h_global ?? m.vol24h)} />
              {m.change_7d != null && (
                <Row l={ar ? "تغيّر 7 أيام" : "7d change"}
                  v={`${m.change_7d > 0 ? "+" : ""}${Number(m.change_7d).toFixed(2)}%`}
                  c={m.change_7d >= 0 ? "var(--green)" : "var(--red)"} />
              )}
              {m.ath_price && (
                <Row l={ar ? "القمّة التاريخية" : "All-time high"} v={`$${fmtPx(m.ath_price)}`} />
              )}
              {m.from_ath != null && (
                <Row l={ar ? "البعد عن القمّة" : "From ATH"}
                  v={`${Number(m.from_ath).toFixed(1)}%`} c="var(--red)" hint={ar ? "كم تبعد عن أعلى سعر بلغته في تاريخها" : "Distance from its all-time high"} />
              )}
            </>
          )}

          {pj.desc && (
            <>
              <div style={{ fontSize: 11, color: "var(--txt-3)", fontWeight: 700, margin: "13px 0 5px" }}>
                {ar ? "عن المشروع" : "About the project"}
              </div>
              <div style={{
                fontSize: 12, lineHeight: 1.85, color: "var(--txt-2)",
                background: "var(--bg-2)", padding: "11px 13px",
                borderRadius: 10,
                direction: ar && pj.desc_ar ? "rtl" : "ltr",
                textAlign: ar && pj.desc_ar ? "right" : "left",
                maxHeight: expand ? "none" : 96, overflow: "hidden",
                position: "relative",
              }}>{ar && pj.desc_ar ? pj.desc_ar : pj.desc}</div>
              {pj.desc.length > 180 && (
                <button onClick={() => setExpand(!expand)} style={{
                  marginTop: 5, border: 0, background: "transparent",
                  color: "var(--brand)", fontSize: 11.5, fontWeight: 700,
                  cursor: "pointer", padding: 0,
                }}>{expand ? (ar ? "أقلّ" : "Less") : (ar ? "المزيد" : "More")}</button>
              )}
            </>
          )}

          {pj.links && Object.keys(pj.links).length > 0 && (
            <>
              <div style={{ fontSize: 11, color: "var(--txt-3)", fontWeight: 700, margin: "13px 0 6px" }}>
                {ar ? "الروابط الرسمية" : "Official links"}
              </div>
              <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
                {Object.entries(pj.links).map(([k, u]) => (
                  <a key={k} href={u} target="_blank" rel="noopener noreferrer"
                    style={{
                      padding: "6px 11px", borderRadius: 9, fontSize: 11.5,
                      background: "var(--bg-2)", color: "var(--txt-2)",
                      textDecoration: "none", fontWeight: 600,
                    }}>{LNK[k] ? (ar ? LNK[k][0] : LNK[k][1]) : k}</a>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {chart && r?.ok && (
        <div onClick={() => setChart(false)} style={{
          position: "fixed", inset: 0, zIndex: 90, padding: 14,
          background: "rgba(0,0,0,.82)", display: "flex",
          alignItems: "center", justifyContent: "center",
        }}>
        <div onClick={(e) => e.stopPropagation()} style={{
          position: "relative", width: "100%", maxWidth: 620,
          borderRadius: 14, overflow: "hidden",
          border: "1px solid var(--bg-2)", height: "72vh",
          background: "var(--bg-0)",
        }}>
          <button onClick={() => setChart(false)} style={{
            position: "absolute", top: 8, insetInlineEnd: 8, zIndex: 5,
            width: 30, height: 30, borderRadius: 8, cursor: "pointer",
            border: 0, background: "rgba(0,0,0,.6)", color: "#fff",
            fontSize: 16, lineHeight: 1,
          }}>✕</button>
          <iframe title="chart" style={{ width: "100%", height: "100%", border: 0 }}
            src={`https://www.tradingview.com/widgetembed/?symbol=BINANCE:${r.symbol}&interval=60&theme=dark&style=1&locale=${ar ? "ar_AE" : "en"}&hide_side_toolbar=1&save_image=0`} />
        </div>
        </div>
      )}

      {r && !r.ok && (
        <div style={{ marginTop: 16, color: "var(--red)", fontSize: 13 }}>
          {ar ? "تعذّر الفحص — تأكّد من الرمز" : "Scan failed — check the symbol"}
        </div>
      )}
    </div>
  );
}
