import { useEffect, useRef } from "react";
import { X } from "lucide-react";

// 🌐 أسماء المنصّات كما يستخدمها TradingView
const TV_EX = {
  binance: "BINANCE", bybit: "BYBIT", mexc: "MEXC",
  bingx: "BINGX", bitget: "BITGET", gate: "GATEIO", okx: "OKX",
};

/**
 * 📊 شارت حيّ للصفقة — فيوتشر وسبوت.
 *    الفيوتشر يحمل لاحقة .P (عقد دائم) · السبوت بلا لاحقة.
 *    الميم مستثنى: رابط DexScreener موجود في إشارته أصلاً.
 */
export default function ChartModal({ pos, onClose, lang = "ar" }) {
  const box = useRef(null);
  if (!pos) return null;

  const ex = (pos.exchange || "binance").toLowerCase();
  const tvEx = TV_EX[ex] || "BINANCE";
  const isSpot = pos.radar_type === "spot";
  const tvSymbol = `${tvEx}:${pos.symbol}${isSpot ? "" : ".P"}`;

  useEffect(() => {
    if (!box.current) return;
    box.current.innerHTML = "";
    const s = document.createElement("script");
    s.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    s.async = true;
    s.innerHTML = JSON.stringify({
      symbol: tvSymbol,
      interval: "15",
      theme: "dark",
      style: "1",
      locale: lang === "en" ? "en" : "ar_AE",   // 🌐 يتبع لغة التطبيق
      autosize: true,
      hide_side_toolbar: true,
      allow_symbol_change: false,
      save_image: false,
      backgroundColor: "rgba(11,15,25,1)",
    });
    box.current.appendChild(s);
  }, [tvSymbol, lang]);

  const entry = Number(pos.entry) || 0;
  const cur = Number(pos.current ?? pos.last_price) || 0;
  const pnl = Number(pos.pnl_pct) || 0;
  const up = pnl >= 0;

  // 🎯 هل أُصيب هذا المستوى؟ (لونج: السعر تجاوزه · شورت: نزل تحته)
  const hit = (lvl) => {
    const v = Number(lvl), c = Number(cur);
    if (!v || !c) return false;
    return pos.direction === "LONG" ? c >= v : c <= v;
  };

  const Cell = ({ label, value, color, glow }) => (
    <div style={{
      background: glow ? `${color}1a` : "rgba(255,255,255,.03)",
      borderRadius: 10,
      border: glow ? `1.5px solid ${color}` : "1px solid rgba(255,255,255,.06)",
      boxShadow: glow ? `0 0 14px ${color}55` : "none",
      padding: "7px 6px", textAlign: "center", minWidth: 0,
      transition: "all .3s ease",
    }}>
      <div style={{ fontSize: 9.5, color: "var(--txt-3, #7c8798)", marginBottom: 3 }}>{label}</div>
      <div style={{
        fontSize: 12.5, fontWeight: 700, color, direction: "ltr",
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
      }}>{value}</div>
    </div>
  );

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, zIndex: 9999,
      background: "rgba(0,0,0,.85)", display: "flex", padding: "10px",
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: "var(--bg-1, #0b0f19)", borderRadius: "14px",
        border: "1px solid var(--border, #223)", overflow: "hidden",
        display: "flex", flexDirection: "column", width: "100%",
      }}>
        <div style={{
          display: "flex", alignItems: "center", gap: "10px",
          padding: "12px 14px", borderBottom: "1px solid var(--border, #223)",
        }}>
          <button onClick={onClose} style={{
            background: "transparent", border: "none", cursor: "pointer",
            color: "#fff", display: "flex", padding: 0,
          }}><X size={22} /></button>
          <span style={{ color: "#fff", fontWeight: 700, fontSize: "16px" }}>
            {pos.symbol}
          </span>
          <span style={{
            fontSize: "11px", padding: "3px 9px", borderRadius: "6px",
            background: "rgba(45,212,191,.14)", color: "var(--green, #2dd4bf)",
          }}>📍 {tvEx}</span>
          <span style={{
            marginInlineStart: "auto", fontWeight: 800, fontSize: "17px",
            color: up ? "var(--green, #2dd4bf)" : "var(--red, #f87171)",
          }}>{pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}%</span>
        </div>

        <div style={{ flex: 1, minHeight: 0, background: "#0b0f19" }}>
          <div ref={box} style={{ width: "100%", height: "100%" }} />
        </div>

        {/* 📊 شريط المستويات — أسفل الشارت بمساحته الخاصّة */}
        <div style={{
          padding: "12px 14px 14px",
          borderTop: "1px solid var(--border, #223)",
          background: "rgba(11,15,25,.6)",
        }}>
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10,
            marginBottom: 10,
          }}>
            <Cell label={lang === "en" ? "Entry" : "الدخول"} value={entry} color="#94a3b8" />
            <Cell label={lang === "en" ? "Now" : "الحالي"} value={cur || "—"}
                  color={up ? "#22c55e" : "#ef4444"} />
            <Cell label={lang === "en" ? "Leverage" : "الرافعة"}
                  value={pos.leverage ? `${Math.round(pos.leverage)}x` : "—"} color="#c7d2fe" />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
            <Cell label={lang === "en" ? "Stop" : "الوقف"} value={pos.sl || "—"}
                  color="#ef4444" />
            <Cell label={hit(pos.tp1) ? "TP1 ✓" : "TP1"} value={pos.tp1 || "—"}
                  color="#22c55e" glow={hit(pos.tp1)} />
            <Cell label={hit(pos.tp2) ? "TP2 ✓" : "TP2"} value={pos.tp2 || "—"}
                  color="#38bdf8" glow={hit(pos.tp2)} />
            <Cell label={hit(pos.tp3) ? "TP3 ✓" : "TP3"} value={pos.tp3 || "—"}
                  color="#fbbf24" glow={hit(pos.tp3)} />
          </div>
        </div>

      </div>
    </div>
  );
}
