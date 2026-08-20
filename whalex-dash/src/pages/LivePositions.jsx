// صفقات الرادارات المفتوحة — مشاهدة حيّة فقط (بلا إغلاق)
import { useEffect, useState } from "react";
import { livePositions } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import ChartModal from "../components/ChartModal.jsx";
import { LineChart } from "lucide-react";

// 🖼️ شعارات المنصّات (CoinMarketCap)
const EX_LOGO = {
  binance: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/270.png",
  bybit: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/521.png",
  mexc: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/544.png",
  bingx: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/1064.png",
  bitget: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/513.png",
  gate: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/302.png",
  okx: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/294.png",
};
import { getMarket } from "../hooks/useMarket.js";
import Paywall from "../components/Paywall.jsx";

const fmtPx = (v) =>
  (v === 0 || v) ? String(Number(Number(v).toPrecision(6))) : "";

function fmtAge(openedAt, lang) {
  if (!openedAt) return "";
  const s = Math.max(0, Math.floor(Date.now() / 1000 - openedAt));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  const age = lang === "ar"
    ? (h > 0 ? `${h}س ${m}د` : `${m}د`)
    : (h > 0 ? `${h}h ${m}m` : `${m}m`);
  const tm = new Date(openedAt * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return lang === "ar" ? `⏱ منذ ${age} · فُتحت ${tm}` : `⏱ ${age} ago · opened ${tm}`;
}

export default function LivePositions() {
  const { t, lang } = useLang();
  const [radar, setRadar] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [chartPos, setChartPos] = useState(null);   // 📊 الصفقة المعروض شارتها

  async function loadRadar() {
    try {
      const r = await fetch(`/api/live/radar-positions?market=${getMarket()}`, { headers: { Authorization: `Bearer ${localStorage.getItem("wx_token") || ""}` } }).then((x) => x.json());
      setRadar(r?.positions || []);
    } catch { /* */ }
    finally { setLoaded(true); }
  }

  useEffect(() => {
    loadRadar();
    const id = setInterval(loadRadar, 1000);
    return () => clearInterval(id);
  }, []);

  function Card({ p }) {
    if (p.chain) {
      const mp = (p.pnl_pct || 0) >= 0;
      return (
        <div className="card" style={{ marginBottom: 10, padding: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontWeight: 700, fontSize: 15 }}>{p.symbol}</span>
              <span style={{ fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 6, background: "rgba(74,222,128,0.15)", color: "var(--brand)" }}>🐸 {p.chain}</span>
              <span style={{ fontSize: 11, color: "var(--txt-3)" }}>{p.score}/100</span>
            </div>
            <span style={{ fontWeight: 800, fontSize: 16, color: mp ? "#22c55e" : "#ef4444" }}>{mp ? "+" : ""}{Number(p.pnl_pct || 0).toFixed(1)}%</span>
          </div>
          <div style={{ display: "flex", gap: 14, marginTop: 8, fontSize: 12.5, color: "var(--txt-2)", flexWrap: "wrap" }}>
            <span>{lang === "ar" ? "دخول" : "Entry"}: <b style={{ color: "var(--txt-1)" }}>{fmtPx(p.entry_price)}</b></span>
            <span>{lang === "ar" ? "الآن" : "Now"}: <b style={{ color: "var(--txt-1)" }}>{fmtPx(p.last_price || p.entry_price)}</b></span>
            <span>{lang === "ar" ? "القمة" : "Peak"}: <b style={{ color: "#22c55e" }}>+{Number(p.peak_pnl || 0).toFixed(1)}%</b></span>
          </div>
          <div style={{ marginTop: 6, fontSize: 12, color: "var(--txt-3)" }}>{fmtAge(p.ts, lang)}</div>
        </div>
      );
    }
    const isLong = p.direction === "LONG";
    const isProfit = p.pnl_pct >= 0;
    return (
      <div className="card" onClick={() => setChartPos(p)}
           style={{ marginBottom: 10, padding: 14, cursor: "pointer" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap", flex: 1, minWidth: 0 }}>
            <img src={EX_LOGO[(p.exchange || "binance").toLowerCase()]}
                 alt={p.exchange} width="20" height="20"
                 style={{ borderRadius: 5, flexShrink: 0 }}
                 onError={(e) => { e.target.style.display = "none"; }} />
            <span style={{
              fontWeight: 700, fontSize: 15, whiteSpace: "nowrap",
              flexShrink: 0, direction: "ltr",
            }}>{p.symbol}</span>
            <LineChart size={15} style={{ color: "var(--brand, #2dd4bf)", flexShrink: 0 }} />
            <span style={{
              fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 6,
              background: isLong ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
              color: isLong ? "#22c55e" : "#ef4444",
            }}>
              {isLong ? "LONG" : "SHORT"} {p.leverage > 1 ? `${Math.round(p.leverage)}x` : ""}
            </span>
            <span style={{
              fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 6,
              background: "rgba(99,102,241,0.15)", color: "var(--accent)",
            }}>
              {p.radar ? p.radar : p.tier === "PH" ? (isLong ? "📈 WhaleX Long" : "🎯 WhaleX Short") : "⚡ WhaleX Predator"}
            </span>
          </div>
          <span style={{ fontSize: 17, fontWeight: 800, flexShrink: 0, marginInlineStart: 8, color: isProfit ? "#22c55e" : "#ef4444" }}>
            {isProfit ? "+" : ""}{p.pnl_pct}%
          </span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8, fontSize: 12, color: "var(--txt-3)" }}>
          <span>{t("entry") || "دخول"}: {fmtPx(p.entry)}</span>
          <span>{t("current") || "حالياً"}: {fmtPx(p.current)}</span>
          <span style={{ fontSize: 16 }}>{isProfit ? "🟢" : "🔴"}</span>
        </div>
        {p.opened_at ? (
          <div style={{ marginTop: 6, fontSize: 11, color: "var(--txt-3)" }}>
            {fmtAge(p.opened_at, lang)}
          </div>
        ) : null}
        <div style={{
          marginTop: 8, fontSize: 11, color: "var(--brand, #2dd4bf)",
          display: "flex", alignItems: "center", gap: 5, opacity: .85,
        }}>
          <LineChart size={12} />
          {lang === "ar" ? "اضغط لعرض الشارت الحيّ" : "Tap to view live chart"}
        </div>
      </div>
    );
  }

  return (
    <Paywall>
    <>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>{t("liveRadarTitle") || "صفقات الرادارات"}</h2>
      <p style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 12 }}>{t("liveRadarSub") || "مشاهدة حيّة · الربح والخسارة مباشرة"}</p>

      {radar.length > 0 && (() => {
        const win = radar.filter((p) => (p.pnl_pct || 0) >= 0).length;
        const net = radar.reduce((a, p) => a + (Number(p.pnl_pct) || 0), 0);
        const S = ({ label, value, color, sub }) => (
          <div style={{ flex: 1, textAlign: "center", padding: "9px 4px" }}>
            <div style={{ fontSize: 10, color: "var(--txt-3)", marginBottom: 2 }}>{label}</div>
            <div style={{ fontSize: 16, fontWeight: 800, color: color || "#fff" }}>{value}</div>
            {sub ? <div style={{ fontSize: 9, color: "var(--txt-3)", marginTop: 2 }}>{sub}</div> : null}
          </div>
        );
        return (
          <div className="card" style={{
            display: "flex", padding: 0, marginBottom: 14,
            divide: "1px solid var(--border)",
          }}>
            <S label={lang === "en" ? "Open" : "مفتوحة"} value={radar.length} />
            <S label={lang === "en" ? "In profit" : "رابحة"} value={win} color="#22c55e" />
            <S label={lang === "en" ? "In loss" : "خاسرة"} value={radar.length - win} color="#ef4444" />
            <S label={lang === "en" ? "Net" : "الصافي"}
               value={`${net >= 0 ? "+" : ""}${net.toFixed(1)}%`}
               sub={`${lang === "en" ? "avg" : "متوسط"} ${(net / radar.length).toFixed(2)}%`}
               color={net >= 0 ? "#22c55e" : "#ef4444"} />
          </div>
        );
      })()}

      {!loaded ? (
        <div className="loading">{t("loading")}</div>
      ) : radar.length === 0 ? (
        <div className="card" style={{ padding: 14, fontSize: 13, color: "var(--txt-3)" }}>
          {t("noOpenPositions") || "لا صفقات مفتوحة حالياً."}
        </div>
      ) : (
        radar.map((p, i) => <Card key={`r-${i}`} p={p} />)
      )}
      {chartPos && <ChartModal pos={chartPos} lang={lang} onClose={() => setChartPos(null)} />}
    </>
    </Paywall>
  );
}
