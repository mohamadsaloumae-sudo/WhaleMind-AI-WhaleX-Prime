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

        <div style={{ flex: 1, minHeight: 0, background: "#0b0f19", position: "relative" }}>
          <div ref={box} style={{ width: "100%", height: "100%" }} />
          {/* 🎯 المستويات — طبقة شفّافة فوق الشارت */}
          <div style={{
            position: "absolute", insetInlineStart: 10, top: 10,
            display: "flex", flexDirection: "column", gap: 5,
            pointerEvents: "none", zIndex: 5,
          }}>
            {[
              [lang === "en" ? "Entry" : "دخول", entry, "#94a3b8"],
              [lang === "en" ? "Now" : "حالي", cur, up ? "#22c55e" : "#ef4444"],
              pos.sl ? [lang === "en" ? "Stop" : "وقف", pos.sl, "#ef4444"] : null,
              pos.tp1 ? ["TP1", pos.tp1, "#22c55e"] : null,
            ].filter(Boolean).map(([k, v, c], i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 6,
                background: "rgba(11,15,25,.55)", backdropFilter: "blur(6px)",
                padding: "3px 9px", borderRadius: 20, fontSize: 10.5,
                border: `1px solid ${c}33`,
              }}>
                <span style={{ width: 5, height: 5, borderRadius: 5, background: c }} />
                <span style={{ color: "#94a3b8" }}>{k}</span>
                <span style={{ color: c, fontWeight: 700, direction: "ltr" }}>{v}</span>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
