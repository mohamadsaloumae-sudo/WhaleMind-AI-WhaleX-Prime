import React, { useState, useEffect } from "react";
import { api } from "../lib/api.js";

const SYS = [
  { id: "futures", ar: "الفيوتشر", en: "Futures", icon: "⚡" },
  { id: "spot", ar: "السبوت", en: "Spot", icon: "🪙" },
  { id: "meme", ar: "الميم كوينز", en: "Memecoins", icon: "🐸" },
];

const MON = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
             "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
const MON_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function monthName(p, ar) {
  const parts = String(p).split("-");
  const i = parseInt(parts[1], 10) - 1;
  return ((ar ? MON : MON_EN)[i] || parts[1]) + " " + parts[0];
}

function dayName(p) {
  const parts = String(p).split("-");
  return parts[2] + "/" + parts[1];
}

function Num({ v, suffix = "%", big = false }) {
  const n = Number(v) || 0;
  return (
    <span style={{
      color: n > 0 ? "#22c55e" : n < 0 ? "#ef4444" : "var(--txt-3, #8fa3ba)",
      fontWeight: big ? 800 : 700,
      fontSize: big ? 17 : 13.5,
      direction: "ltr",
      display: "inline-block",
    }}>{n > 0 ? "+" : ""}{n.toFixed(2)}{suffix}</span>
  );
}

function Bar({ wins, losses }) {
  const t = wins + losses;
  if (!t) return null;
  const w = Math.round(wins * 100 / t);
  return (
    <div style={{
      height: 5, borderRadius: 3, overflow: "hidden",
      background: "rgba(239,68,68,0.28)", marginTop: 7, display: "flex",
    }}>
      <div style={{ width: w + "%", background: "#22c55e" }} />
    </div>
  );
}

function Row({ d, label, onClick, ar }) {
  return (
    <div onClick={onClick} className="card"
         style={{ padding: "13px 15px", marginBottom: 8,
                  cursor: onClick ? "pointer" : "default" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 14, fontWeight: 800, flex: 1 }}>{label}</span>
        <Num v={d.net} big />
        {onClick ? (
          <span style={{ color: "var(--txt-3, #8fa3ba)", fontSize: 16 }}>›</span>
        ) : null}
      </div>
      <div style={{ display: "flex", gap: 14, marginTop: 6, flexWrap: "wrap",
                    fontSize: 12, color: "var(--txt-3, #8fa3ba)" }}>
        <span>{ar ? "صفقات" : "Trades"} {d.trades}</span>
        <span style={{ color: "#22c55e" }}>{ar ? "رابحة" : "Wins"} {d.wins}</span>
        <span style={{ color: "#ef4444" }}>{ar ? "خاسرة" : "Losses"} {d.losses}</span>
        <span>{ar ? "نسبة الفوز" : "Win rate"} {d.win_rate}%</span>
      </div>
      <Bar wins={d.wins} losses={d.losses} />
      <div style={{ display: "flex", gap: 14, marginTop: 8, flexWrap: "wrap",
                    fontSize: 11.5, color: "var(--txt-3, #8fa3ba)" }}>
        <span>{ar ? "مجموع الربح" : "Gross win"} <Num v={d.gross_win} /></span>
        <span>{ar ? "مجموع الخسارة" : "Gross loss"} <Num v={d.gross_loss} /></span>
        {d.best != null ? (
          <span>{ar ? "أفضل" : "Best"} <Num v={d.best} /></span>
        ) : null}
      </div>
    </div>
  );
}

export default function History() {
  let lang = "ar";
  try {
    lang = localStorage.getItem("whalex_lang") || "ar";
  } catch (e) { /* */ }
  const ar = lang !== "en";
  const L = (a, e) => (ar ? a : e);

  const [sys, setSys] = useState("futures");
  const [months, setMonths] = useState([]);
  const [open, setOpen] = useState(null);
  const [days, setDays] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setBusy(true); setOpen(null); setDays([]);
    api.get("/api/history/monthly?system=" + sys)
      .then((r) => setMonths((r && r.months) || []))
      .catch(() => setMonths([]))
      .finally(() => setBusy(false));
  }, [sys]);

  const openMonth = (p) => {
    if (open === p) { setOpen(null); setDays([]); return; }
    setOpen(p); setBusy(true);
    api.get("/api/history/daily?system=" + sys + "&month=" + p)
      .then((r) => setDays((r && r.days) || []))
      .catch(() => setDays([]))
      .finally(() => setBusy(false));
  };

  const total = months.reduce((a, m) => a + (Number(m.net) || 0), 0);
  const totalTrades = months.reduce((a, m) => a + (m.trades || 0), 0);

  return (
    <div style={{ maxWidth: 760, margin: "0 auto", padding: "4px 2px 40px" }}>
      <h2 style={{ fontSize: 20, margin: "6px 0 4px" }}>
        {L("📅 السجلّ الزمنيّ", "📅 Performance history")}
      </h2>
      <p style={{ color: "var(--txt-3, #8fa3ba)", fontSize: 13,
                  lineHeight: 1.8, margin: "0 0 14px" }}>
        {L("أداء كل نظام شهراً بشهر. اضغط على أي شهر لترى تفصيل أيامه.",
           "Performance of each system month by month. Tap any month for its daily breakdown.")}
      </p>

      <div style={{ display: "flex", gap: 7, marginBottom: 14, flexWrap: "wrap" }}>
        {SYS.map((s) => (
          <button key={s.id} onClick={() => setSys(s.id)}
            style={{
              flex: 1, minWidth: 96, padding: "10px 8px", borderRadius: 9,
              border: "1px solid " + (sys === s.id ? "var(--brand, #2dd4bf)" : "var(--border, #223)"),
              background: sys === s.id ? "rgba(45,212,191,0.12)" : "transparent",
              color: sys === s.id ? "var(--brand, #2dd4bf)" : "var(--txt-3, #8fa3ba)",
              fontWeight: 700, fontSize: 13, cursor: "pointer",
            }}>
            {s.icon} {ar ? s.ar : s.en}
          </button>
        ))}
      </div>

      {months.length ? (
        <div className="card" style={{ padding: "13px 15px", marginBottom: 14,
             borderInlineStart: "3px solid var(--brand, #2dd4bf)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 800, flex: 1 }}>
              {L("الإجمالي منذ البداية", "All time")}
            </span>
            <Num v={total} big />
          </div>
          <div style={{ fontSize: 12, color: "var(--txt-3, #8fa3ba)", marginTop: 5 }}>
            {totalTrades} {L("صفقة عبر", "trades across")} {months.length} {L("شهراً", "months")}
          </div>
        </div>
      ) : null}

      {busy && !months.length ? (
        <div className="card"><div className="empty">{L("جارٍ التحميل", "Loading")}</div></div>
      ) : null}

      {!busy && !months.length ? (
        <div className="card">
          <div className="empty">{L("لا سجلّ بعد لهذا النظام", "No history yet")}</div>
        </div>
      ) : null}

      {months.map((m) => (
        <div key={m.period}>
          <Row d={m} label={monthName(m.period, ar)} ar={ar}
               onClick={() => openMonth(m.period)} />
          {open === m.period ? (
            <div style={{ marginInlineStart: 14, paddingInlineStart: 12,
                          marginBottom: 12,
                          borderInlineStart: "2px solid var(--border, #223)" }}>
              {busy ? (
                <div style={{ fontSize: 12.5, color: "var(--txt-3, #8fa3ba)", padding: "8px 0" }}>
                  {L("جارٍ التحميل", "Loading")}
                </div>
              ) : days.length ? (
                days.map((d) => (
                  <Row key={d.period} d={d} label={dayName(d.period)} ar={ar} />
                ))
              ) : (
                <div style={{ fontSize: 12.5, color: "var(--txt-3, #8fa3ba)", padding: "8px 0" }}>
                  {L("لا أيام مسجّلة", "No days recorded")}
                </div>
              )}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
