// 📒 سجلّ التداول الحقيقيّ — مكوّن واحد لصفحة المشترك ولوحة الإدارة،
//    فلا يختلف رقم بين الصفحتين.
import React, { useState } from "react";

const AR = {
  title: "📒 سجلّ التداول الحقيقيّ", closed: "صفقات مغلقة", open: "مفتوحة",
  winRate: "نسبة النجاح", wins: "رابحة", losses: "خاسرة",
  grossWin: "مجموع الأرباح", grossLoss: "مجموع الخسائر", net: "الصافي",
  avgWin: "متوسط الربح", avgLoss: "متوسط الخسارة",
  best: "أفضل صفقة", worst: "أسوأ صفقة",
  entry: "سعر الدخول", exit: "سعر الخروج", qty: "الكمّية",
  lev: "الرافعة", value: "قيمة الصفقة", reason: "سبب الإغلاق",
  openedAt: "وقت الفتح", closedAt: "وقت الإغلاق", duration: "المدّة",
  market: "السوق", tabOpen: "المفتوحة", tabClosed: "المغلقة",
  none: "لا صفقات بعد", h: "س", m: "د", still: "ما زالت مفتوحة",
  futures: "عقود آجلة", spot: "فوريّ", meme: "ميم كوينز",
  nowPrice: "السعر الحاليّ", livePnl: "الربح اللحظيّ",
};
const EN = {
  title: "📒 Live trading ledger", closed: "Closed", open: "open",
  winRate: "Win rate", wins: "Wins", losses: "Losses",
  grossWin: "Gross profit", grossLoss: "Gross loss", net: "Net",
  avgWin: "Avg win", avgLoss: "Avg loss",
  best: "Best trade", worst: "Worst trade",
  entry: "Entry", exit: "Exit", qty: "Quantity",
  lev: "Leverage", value: "Position size", reason: "Close reason",
  openedAt: "Opened", closedAt: "Closed", duration: "Duration",
  market: "Market", tabOpen: "Open", tabClosed: "Closed",
  none: "No trades yet", h: "h", m: "m", still: "still open",
  futures: "Futures", spot: "Spot", meme: "Memecoins",
  nowPrice: "Current price", livePnl: "Live PnL",
};

const REASON_AR = {
  harvest: "🌾 حصاد", tp1: "🎯 هدف أوّل", tp2: "🎯 هدف ثانٍ", tp3: "🎯 هدف ثالث",
  sl_hit: "🛑 ضرب الوقف", tactical_exit: "⚡ خروج تكتيكيّ",
  manual_close: "✋ إغلاق يدويّ", locked: "🔒 قفل الربح",
  flow_cut: "📉 انقلاب التدفّق", reversal: "🔻 انقلاب", bleed: "📉 نزيف",
};
const REASON_EN = {
  harvest: "🌾 Harvest", tp1: "🎯 TP1", tp2: "🎯 TP2", tp3: "🎯 TP3",
  sl_hit: "🛑 Stop loss", tactical_exit: "⚡ Tactical exit",
  manual_close: "✋ Manual", locked: "🔒 Locked profit",
  flow_cut: "📉 Flow cut", reversal: "🔻 Reversal", bleed: "📉 Bleed",
};

function fmtTime(ts, ar) {
  if (!ts) return "—";
  const d = new Date(Number(ts) * 1000);
  return d.toLocaleString(ar ? "ar-AE" : "en-GB", {
    timeZone: "Asia/Dubai", day: "2-digit", month: "2-digit",
    year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function fmtDur(a, b, L) {
  if (!a) return "—";
  const end = b || Math.floor(Date.now() / 1000);
  const mins = Math.max(0, Math.round((end - a) / 60));
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return (h ? h + L.h + " " : "") + m + L.m + (b ? "" : " · " + L.still);
}

function num(v, d = 2) {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(d) : "—";
}

function Amount({ pct, usdt, big }) {
  const p = Number(pct) || 0;
  const col = p > 0 ? "#22c55e" : p < 0 ? "#ef4444" : "var(--txt-3, #8fa3ba)";
  return (
    <span dir="ltr" style={{ color: col, fontWeight: 800, fontSize: big ? 17 : 13 }}>
      {p > 0 ? "+" : ""}{num(p)}%
      {usdt != null ? (
        <span style={{ fontSize: big ? 14 : 11.5, marginInlineStart: 6 }}>
          ({Number(usdt) >= 0 ? "+" : ""}{num(usdt)}$)
        </span>
      ) : null}
    </span>
  );
}

function Cell({ k, v, dir }) {
  return (
    <div style={{ padding: "6px 8px", background: "rgba(255,255,255,0.03)", borderRadius: 7 }}>
      <div style={{ fontSize: 9.5, color: "var(--txt-3, #8fa3ba)", marginBottom: 1 }}>{k}</div>
      <div dir={dir} style={{ fontSize: 12, fontWeight: 700 }}>{v}</div>
    </div>
  );
}

function TradeCard({ t, L, ar, isOpen }) {
  const [show, setShow] = useState(false);
  const R = ar ? REASON_AR : REASON_EN;
  const reason = t.close_reason ? (R[t.close_reason] || t.close_reason) : null;
  const value = (Number(t.entry) || 0) * (Number(t.qty) || 0);
  const mkt = L[t.market] || t.market || "";
  return (
    <div
      onClick={() => setShow(!show)}
      style={{
        padding: "9px 11px", marginBottom: 6, borderRadius: 9, cursor: "pointer",
        background: isOpen ? "rgba(234,179,8,0.06)"
          : (Number(t.pnl_pct) || 0) >= 0 ? "rgba(34,197,94,0.06)" : "rgba(239,68,68,0.06)",
        borderInlineStart: "3px solid " + (
          isOpen
            ? (t.live_pnl != null
                ? (t.live_pnl >= 0 ? "#22c55e" : "#ef4444")
                : "#eab308")
            : (Number(t.pnl_pct) || 0) >= 0 ? "#22c55e" : "#ef4444"),
      }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 12.5, fontWeight: 800 }}>
          {t.symbol}
          <span style={{ color: t.direction === "LONG" ? "#22c55e" : "#ef4444", marginInlineStart: 6, fontSize: 11 }}>
            {t.direction}
          </span>
          <span style={{ color: "var(--txt-3, #8fa3ba)", marginInlineStart: 6, fontSize: 10.5 }}>
            {mkt}
          </span>
        </span>
        {isOpen ? (
          t.live_pnl != null
            ? <Amount pct={t.live_pnl} usdt={t.live_usdt} />
            : <span style={{ fontSize: 11, color: "#eab308", fontWeight: 700 }}>{L.still}</span>
        ) : (
          <Amount pct={t.pnl_pct} usdt={t.pnl_usdt} />
        )}
      </div>
      {show && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 5, marginTop: 8 }}>
          <Cell k={L.entry} v={t.entry} dir="ltr" />
          <Cell k={isOpen ? L.nowPrice : L.exit} v={t.exit_price || t.live_price || "—"} dir="ltr" />
          <Cell k={L.qty} v={t.qty} dir="ltr" />
          <Cell k={L.lev} v={(t.leverage || 1) + "x"} dir="ltr" />
          <Cell k={L.value} v={num(value) + "$"} dir="ltr" />
          <Cell k={L.duration} v={fmtDur(t.opened_at, t.closed_at, L)} />
          <Cell k={L.openedAt} v={fmtTime(t.opened_at, ar)} dir="ltr" />
          <Cell k={L.closedAt} v={t.closed_at ? fmtTime(t.closed_at, ar) : "—"} dir="ltr" />
          {reason ? (
            <div style={{ gridColumn: "1 / -1" }}>
              <Cell k={L.reason} v={reason} />
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

export default function TradeLedger({ data, ar = true }) {
  const L = ar ? AR : EN;
  // 📂 نفتح على التبويب الذي فيه بيانات — فالمشترك الجديد كل صفقاته
  //    مفتوحة، وتبويب "المغلقة" الفارغ يوهم بأن الصفحة لا تعمل.
  const [tab, setTab] = useState(
    (data && (data.recent || []).length) ? "closed" : "open");
  if (!data) return null;
  const closed = data.recent || [];
  const open = data.open_list || [];
  const list = tab === "open" ? open : closed;

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div className="card-title">{L.title}</div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 6, marginBottom: 8 }}>
        <Cell k={L.closed} v={`${data.closed} (${data.open} ${L.open})`} />
        <Cell k={L.winRate} v={`${data.win_rate}%`} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 6, marginBottom: 8 }}>
        <div style={{ padding: "8px 10px", background: "rgba(34,197,94,0.10)", borderRadius: 8 }}>
          <div style={{ fontSize: 10, color: "var(--txt-3, #8fa3ba)" }}>{L.wins} · {L.grossWin}</div>
          <div style={{ fontSize: 14, fontWeight: 800, color: "#22c55e" }}>
            {data.wins} <span dir="ltr" style={{ fontSize: 12 }}>
              (+{num(data.gross_win_pct)}% · +{num(data.gross_win_usdt)}$)
            </span>
          </div>
        </div>
        <div style={{ padding: "8px 10px", background: "rgba(239,68,68,0.10)", borderRadius: 8 }}>
          <div style={{ fontSize: 10, color: "var(--txt-3, #8fa3ba)" }}>{L.losses} · {L.grossLoss}</div>
          <div style={{ fontSize: 14, fontWeight: 800, color: "#ef4444" }}>
            {data.losses} <span dir="ltr" style={{ fontSize: 12 }}>
              ({num(data.gross_loss_pct)}% · {num(data.gross_loss_usdt)}$)
            </span>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 6, marginBottom: 8 }}>
        <Cell k={L.avgWin} v={"+" + num(data.avg_win_pct) + "%"} dir="ltr" />
        <Cell k={L.avgLoss} v={num(data.avg_loss_pct) + "%"} dir="ltr" />
        {data.best != null ? <Cell k={L.best} v={"+" + num(data.best) + "%"} dir="ltr" /> : null}
        {data.worst != null ? <Cell k={L.worst} v={num(data.worst) + "%"} dir="ltr" /> : null}
      </div>

      <div style={{
        padding: "10px 12px", borderRadius: 9, textAlign: "center", marginBottom: 10,
        background: (data.net_usdt || 0) >= 0 ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
      }}>
        <div style={{ fontSize: 10.5, color: "var(--txt-3, #8fa3ba)" }}>{L.net}</div>
        <Amount pct={data.net_pct} usdt={data.net_usdt} big />
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
        {[["closed", `${L.tabClosed} (${closed.length})`], ["open", `${L.tabOpen} (${open.length})`]].map(([k, lbl]) => (
          <button key={k} onClick={() => setTab(k)} style={{
            flex: 1, padding: "7px 6px", borderRadius: 8, fontSize: 12, fontWeight: 700,
            cursor: "pointer",
            border: "1px solid " + (tab === k ? "var(--brand, #2dd4bf)" : "var(--border, #223)"),
            background: tab === k ? "rgba(45,212,191,0.12)" : "transparent",
            color: tab === k ? "var(--brand, #2dd4bf)" : "var(--txt-3, #8fa3ba)",
          }}>{lbl}</button>
        ))}
      </div>

      {list.length === 0 ? (
        <div className="empty" style={{ fontSize: 12 }}>{L.none}</div>
      ) : (
        list.map((t, i) => (
          <TradeCard key={t.id || i} t={t} L={L} ar={ar} isOpen={tab === "open"} />
        ))
      )}
    </div>
  );
}
