import { X } from "lucide-react";

const EX_LOGO = {
  binance: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/270.png",
  bybit: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/521.png",
  mexc: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/544.png",
  bingx: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/1064.png",
  bitget: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/513.png",
  gate: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/302.png",
  okx: "https://s2.coinmarketcap.com/static/img/exchanges/64x64/294.png",
};

const EX_NAME = {
  binance: "Binance", bybit: "Bybit", mexc: "MEXC", bingx: "BingX",
  bitget: "Bitget", gate: "Gate.io", okx: "OKX",
};

const REASON = {
  SL_HIT: ["🛑 ضرب الوقف", "Stop loss hit"],
  TP1_HIT: ["🎯 الهدف الأول", "Take profit 1"],
  TP2_HIT: ["🎯 الهدف الثاني", "Take profit 2"],
  TP3_HIT: ["🎯 الهدف الثالث", "Take profit 3"],
  REVERSAL: ["🔄 انعكاس التدفّق", "Flow reversal"],
  EXPIRED: ["⏳ انتهت المهلة", "Expired"],
  TACTICAL: ["🧠 خروج تكتيكي", "Tactical exit"],
  FLOOR: ["🔻 الأرضية", "Hard floor"],
  PROFIT_LOCK: ["🔒 قفل الربح", "Profit lock"],
};

/** 📊 تفاصيل الصفقة المغلقة — كل ما يحتاجه المستخدم للمراجعة. */
export default function TradeDetails({ trade: x, lang = "ar", onClose }) {
  if (!x) return null;
  const ar = lang !== "en";
  const L = (a, e) => (ar ? a : e);
  const ex = String(x.exchange || "binance").toLowerCase();
  const win = x.is_win;
  const pnl = Number(x.pnl_pct) || 0;

  // 📅 التاريخ بصيغة إنجليزية ثابتة — الصيغة العربية تعكس ترتيب الأرقام
  const fmtT = (ts) => {
    if (!ts) return "—";
    const d = new Date(Number(ts) * 1000);
    const p = (n) => String(n).padStart(2, "0");
    return `${p(d.getDate())}/${p(d.getMonth() + 1)}  ${p(d.getHours())}:${p(d.getMinutes())}`;
  };
  const dur = (() => {
    if (!x.opened_at || !x.closed_at) return "—";
    const m = Math.round((Number(x.closed_at) - Number(x.opened_at)) / 60);
    if (m < 60) return `${m} ${L("دقيقة", "min")}`;
    const h = Math.floor(m / 60);
    return `${h} ${L("ساعة", "h")} ${m % 60} ${L("د", "m")}`;
  })();
  const reasonTxt = (() => {
    const k = String(x.close_reason || "").toUpperCase();
    for (const [key, [a, e]] of Object.entries(REASON))
      if (k.includes(key)) return ar ? a : e;
    if (x.close_reason) return x.close_reason;
    // 🧠 الصفقات القديمة بلا حقل — نستنتج السبب من السعر
    const e = Number(x.entry), ex2 = Number(x.exit_price);
    const sl = Number(x.sl), tp = Number(x.tp1);
    if (e && ex2 && sl) {
      const hitSL = x.direction === "LONG" ? ex2 <= sl * 1.005 : ex2 >= sl * 0.995;
      if (hitSL) return ar ? "🛑 ضرب الوقف" : "Stop loss hit";
    }
    if (e && ex2 && tp) {
      const hitTP = x.direction === "LONG" ? ex2 >= tp * 0.995 : ex2 <= tp * 1.005;
      if (hitTP) return ar ? "🎯 بلغ الهدف" : "Target hit";
    }
    return win ? (ar ? "🔒 جني ربح" : "Profit taken")
               : (ar ? "🚪 خروج مبكر" : "Early exit");
  })();

  // 🎯 اسم الرادار الحقيقي من tier — لا اسم المنصّة
  const radarName = (() => {
    const t = String(x.tier || "").toUpperCase();
    if (t === "MX") return ar ? "🌐 رادار المنصّات" : "🌐 Multi-Exchange";
    if (t === "MEME") return ar ? "🐸 رادار الميم" : "🐸 Meme Radar";
    if (t === "SPOT") return ar ? "🪙 رادار السبوت" : "🪙 Spot Radar";
    if (t === "PH") return x.direction === "LONG"
      ? (ar ? "📈 واليكس لونج" : "📈 WhaleX Long")
      : (ar ? "🎯 واليكس شورت" : "🎯 WhaleX Short");
    if (t === "LV2") return ar ? "🔬 لونج V2" : "🔬 Long V2";
    return ar ? "⚡ واليكس بريديتر" : "⚡ WhaleX Predator";
  })();

  const Sec = ({ children }) => (
    <div style={{
      fontSize: 11, fontWeight: 700, color: "var(--brand, #2dd4bf)",
      marginTop: 14, marginBottom: 4, letterSpacing: .3,
    }}>{children}</div>
  );

  const Row = ({ label, value, color }) => (
    <div style={{
      display: "flex", justifyContent: "space-between", gap: 12,
      padding: "7px 0", fontSize: 12.5, borderBottom: "1px solid rgba(255,255,255,.04)",
    }}>
      <span style={{ color: "var(--txt-3, #7c8798)" }}>{label}</span>
      <span style={{ color: color || "#fff", fontWeight: 600, direction: "ltr" }}>{value}</span>
    </div>
  );

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, zIndex: 9999,
      background: "rgba(0,0,0,.85)", display: "flex",
      alignItems: "center", justifyContent: "center", padding: 14,
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: "var(--bg-1, #0b0f19)", borderRadius: 16, width: "100%",
        maxWidth: 460, maxHeight: "88vh", overflowY: "auto",
        border: "1px solid var(--border, #223)",
      }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 9, padding: "14px 16px",
          borderBottom: "1px solid var(--border, #223)",
        }}>
          <button onClick={onClose} style={{
            background: "transparent", border: "none", cursor: "pointer",
            color: "#fff", display: "flex", padding: 0,
          }}><X size={21} /></button>
          <img src={EX_LOGO[ex]} alt={ex} width="22" height="22"
               style={{ borderRadius: 5 }}
               onError={(e) => { e.target.style.display = "none"; }} />
          <strong style={{ color: "#fff", fontSize: 15, direction: "ltr" }}>{x.symbol}</strong>
          <span style={{
            fontSize: 10.5, fontWeight: 700, padding: "3px 8px", borderRadius: 6,
            background: x.direction === "LONG" ? "rgba(34,197,94,.15)" : "rgba(239,68,68,.15)",
            color: x.direction === "LONG" ? "#22c55e" : "#ef4444",
          }}>{x.direction}{x.leverage ? ` ${Math.round(x.leverage)}x` : ""}</span>
          <span style={{
            marginInlineStart: "auto", fontWeight: 800, fontSize: 17,
            color: win ? "#22c55e" : "#ef4444",
          }}>{pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}%</span>
        </div>

        <div style={{ padding: "10px 16px 16px" }}>
          <Sec>{L("الصفقة", "Trade")}</Sec>
          <Row label={L("المنصّة", "Exchange")} value={EX_NAME[ex] || ex} />
          <Row label={L("الرادار", "Radar")} value={radarName} />

          <Sec>{L("الدخول", "Entry")}</Sec>
          <Row label={L("التوقيت", "Time")} value={fmtT(x.opened_at)} />
          <Row label={L("السعر", "Price")} value={x.entry ?? "—"} />

          <Sec>{L("الخروج", "Exit")}</Sec>
          <Row label={L("التوقيت", "Time")} value={fmtT(x.closed_at)} />
          <Row label={L("السعر", "Price")} value={x.exit_price ?? "—"} />
          <Row label={L("المدّة", "Duration")} value={dur} />
          <Row label={L("السبب", "Reason")} value={reasonTxt} />

          <Sec>{L("المستويات", "Levels")}</Sec>
          <Row label={L("الوقف", "Stop loss")} value={x.sl ?? "—"} color="#ef4444" />
          {x.tp1 ? <Row label="🎯 TP1" value={x.tp1} color="#22c55e" /> : null}
          {x.tp2 ? <Row label="🎯 TP2" value={x.tp2} color="#22c55e" /> : null}
          {x.tp3 ? <Row label="🎯 TP3" value={x.tp3} color="#22c55e" /> : null}
          {x.peak_pnl != null ? (
            <Row label={L("أعلى ربح", "Peak profit")}
                 value={`${Number(x.peak_pnl) >= 0 ? "+" : ""}${Number(x.peak_pnl).toFixed(2)}%`}
                 color="#22c55e" />
          ) : null}
          <Sec>{L("أسباب الدخول", "Entry reasons")}</Sec>
          {(x.strategies || "").split("\n").slice(1).filter(Boolean).map((r, i) => (
            <div key={i} style={{
              fontSize: 12, color: "#fff", padding: "5px 0",
              borderBottom: "1px solid rgba(255,255,255,.04)",
            }}>✅ {r}</div>
          ))}

          <Sec>{L("المؤشّرات", "Indicators")}</Sec>
          {x.rsi ? <Row label="RSI" value={Number(x.rsi).toFixed(1)} /> : null}
          {x.range_pos != null ? (
            <Row label={L("الموقع في النطاق", "Range position")}
                 value={`${(Number(x.range_pos) * 100).toFixed(0)}%`} />
          ) : null}
          {x.volume_ratio ? (
            <Row label={L("نسبة الحجم", "Volume ratio")} value={`×${Number(x.volume_ratio).toFixed(2)}`} />
          ) : null}
          {x.score ? <Row label={L("النقاط", "Score")} value={Number(x.score).toFixed(1)} /> : null}
          {x.confidence ? (
            <Row label={L("الثقة", "Confidence")} value={`${Number(x.confidence).toFixed(0)}%`} />
          ) : null}
        </div>
      </div>
    </div>
  );
}
