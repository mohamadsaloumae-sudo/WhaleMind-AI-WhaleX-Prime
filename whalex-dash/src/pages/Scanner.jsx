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
  const [recent, setRecent] = useState(() => {
    try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); }
    catch { return []; }
  });
  const boxRef = useRef(null);

  useEffect(() => {
    const q = sym.trim();
    if (!q) { setSug([]); return; }
    let dead = false;
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
    setBusy(true); setR(null); setMkt(null); setOpen(false); setChart(false);
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

  const Row = ({ l, v, c }) => (
    <div style={{
      display: "flex", justifyContent: "space-between", padding: "7px 0",
      borderBottom: "1px solid var(--bg-2)", fontSize: 13,
    }}>
      <span style={{ color: "var(--txt-3)" }}>{l}</span>
      <b style={{ color: c || "var(--txt-0)", direction: "ltr" }}>{v}</b>
    </div>
  );

  const m = mkt?.market || {};
  const isFut = !!mkt?.futures;
  const verdict = r?.ok && isFut ? V[r.verdict] : null;

  return (
    <div style={{ padding: 16, maxWidth: 560, margin: "0 auto" }}>
      <h2 style={{ marginBottom: 3, fontSize: 20 }}>🔍 WhaleX Scanner</h2>
      <div style={{ color: "var(--txt-3)", fontSize: 12.5, marginBottom: 14 }}>
        {ar
          ? "افحص أي عملة على سبع منصّات — الحكم والمؤشّرات وبيانات السوق"
          : "Scan any coin across seven venues — verdict, indicators, market data"}
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
          <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginBottom: 8, fontWeight: 600 }}>
            {ar ? "متاحة على" : "Available on"}
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
              {m.name && <span style={{ color: "var(--txt-3)", fontSize: 12, marginInlineStart: 7 }}>{m.name}</span>}
            </div>
            {verdict ? (
              <span style={{ color: verdict.c, fontWeight: 800, fontSize: 13.5 }}>
                {verdict.ic} {ar ? verdict.ar : verdict.en}
              </span>
            ) : (
              <span style={{ color: "var(--amber)", fontWeight: 800, fontSize: 13.5 }}>
                🪙 {ar ? SPOT_V[r.verdict]?.ar : SPOT_V[r.verdict]?.en}
              </span>
            )}
          </div>

          {!isFut && (
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
            {ar ? r.reason : r.reason_en}
          </div>
          <div style={{
            fontSize: 13, lineHeight: 1.75, background: "var(--bg-2)",
            padding: "10px 12px", borderRadius: 10, marginBottom: 12,
          }}>
            {ar ? r.brief : r.brief_en}
          </div>

          <div style={{ fontSize: 11, color: "var(--txt-3)", fontWeight: 700, marginBottom: 4 }}>
            {ar ? "المؤشّرات" : "Indicators"}
          </div>
          <Row l={ar ? "السعر الحيّ" : "Live price"} v={`$${fmtPx(m.price ?? r.price)}`} />
          <Row l={ar ? "تغيّر 24 ساعة" : "24h change"}
            v={`${(m.change24h ?? r.change24h) > 0 ? "+" : ""}${Number(m.change24h ?? r.change24h).toFixed(2)}%`}
            c={(m.change24h ?? r.change24h) >= 0 ? "var(--green)" : "var(--red)"} />
          <Row l="RSI" v={r.rsi} />
          <Row l={ar ? "موقع النطاق" : "Range position"} v={`${Math.round(r.range_pos * 100)}%`} />

          {m.rank && (
            <>
              <div style={{ fontSize: 11, color: "var(--txt-3)", fontWeight: 700, margin: "12px 0 4px" }}>
                {ar ? "بيانات السوق" : "Market data"}
              </div>
              <Row l={ar ? "الترتيب العالميّ" : "Global rank"} v={`#${m.rank}`} />
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
                  v={`${Number(m.from_ath).toFixed(1)}%`} c="var(--red)" />
              )}
            </>
          )}

          <button onClick={() => setChart(!chart)} style={{
            marginTop: 14, width: "100%", padding: "10px", borderRadius: 10,
            border: "1px solid var(--brand)", background: "transparent",
            color: "var(--brand)", fontWeight: 700, fontSize: 13, cursor: "pointer",
          }}>
            {chart ? (ar ? "إخفاء الرسم" : "Hide chart")
                   : (ar ? "📈 عرض الرسم البيانيّ" : "📈 Show live chart")}
          </button>
        </div>
      )}

      {chart && r?.ok && (
        <div style={{
          marginTop: 12, borderRadius: 14, overflow: "hidden",
          border: "1px solid var(--bg-2)", height: 380,
        }}>
          <iframe title="chart" style={{ width: "100%", height: "100%", border: 0 }}
            src={`https://www.tradingview.com/widgetembed/?symbol=BINANCE:${r.symbol}&interval=60&theme=dark&style=1&locale=${ar ? "ar_AE" : "en"}&hide_side_toolbar=1&save_image=0`} />
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
