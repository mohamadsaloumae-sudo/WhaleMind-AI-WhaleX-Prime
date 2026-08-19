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
export default function ChartModal({ pos, onClose }) {
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
      locale: "ar_AE",
      autosize: true,
      hide_side_toolbar: true,
      allow_symbol_change: false,
      save_image: false,
      backgroundColor: "rgba(11,15,25,1)",
    });
    box.current.appendChild(s);
  }, [tvSymbol]);

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

        <div ref={box} style={{ flex: 1, minHeight: 0, background: "#0b0f19" }} />

        <div style={{
          display: "flex", gap: "14px", flexWrap: "wrap",
          padding: "11px 14px", borderTop: "1px solid var(--border, #223)",
          fontSize: "12px",
        }}>
          <span style={{ color: "#9aa4b2" }}>دخول <b style={{ color: "#fff" }}>{entry}</b></span>
          <span style={{ color: "#9aa4b2" }}>حالي <b style={{ color: "#fff" }}>{cur || "—"}</b></span>
          {pos.sl ? <span style={{ color: "#9aa4b2" }}>وقف <b style={{ color: "var(--red, #f87171)" }}>{pos.sl}</b></span> : null}
          {pos.leverage ? <span style={{ color: "#9aa4b2" }}>رافعة <b style={{ color: "#fff" }}>{pos.leverage}x</b></span> : null}
        </div>
      </div>
    </div>
  );
}
