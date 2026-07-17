import { useState } from "react";
import { api } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";

const V = {
  LONG:  { ar: "🟢 صالحة لونغ",  en: "🟢 LONG setup",  c: "var(--green)" },
  SHORT: { ar: "🔴 صالحة شورت", en: "🔴 SHORT setup", c: "var(--red)" },
  WAIT:  { ar: "⏸ انتظار",       en: "⏸ WAIT",         c: "var(--amber)" },
};

export default function Scanner() {
  const { lang } = useLang();
  const [sym, setSym] = useState("");
  const [r, setR] = useState(null);
  const [busy, setBusy] = useState(false);
  const ar = lang === "ar";

  async function go() {
    if (!sym.trim() || busy) return;
    setBusy(true); setR(null);
    try { setR(await api.get(`/api/scanner/scan?symbol=${encodeURIComponent(sym.trim())}`)); }
    catch { setR({ ok: false, error: "network" }); }
    setBusy(false);
  }

  const Row = ({ l, v }) => (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--bg-2)", fontSize: 13 }}>
      <span style={{ color: "var(--txt-3)" }}>{l}</span><b>{v}</b>
    </div>
  );

  return (
    <div style={{ padding: 16 }}>
      <h2 style={{ marginBottom: 4 }}>{ar ? "🦅 عين الصقر" : "🦅 Hawk Eye"}</h2>
      <div style={{ color: "var(--txt-3)", fontSize: 13, marginBottom: 12 }}>
        {ar ? "افحص أي عملة بنفس عيون الرادار — حكم مباشر وسبب" : "Scan any coin with the radar's own eyes — direct verdict + reason"}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <input value={sym} onChange={(e) => setSym(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && go()}
          placeholder={ar ? "مثال: ZEC أو SOLUSDT" : "e.g. ZEC or SOLUSDT"}
          style={{ flex: 1, padding: "10px 12px", borderRadius: 10, border: "1px solid var(--bg-2)", background: "var(--bg-1)", color: "var(--txt-0)" }} />
        <button onClick={go} disabled={busy}
          style={{ padding: "10px 18px", borderRadius: 10, border: 0, background: "var(--brand)", color: "#04211c", fontWeight: 700 }}>
          {busy ? "…" : ar ? "افحص" : "Scan"}
        </button>
      </div>

      {r && !r.ok && (
        <div style={{ marginTop: 16, color: "var(--red)" }}>
          {ar ? "تعذّر الفحص — تأكد من الرمز" : "Scan failed — check the symbol"}
        </div>
      )}

      {r && r.ok && (
        <div className="card" style={{ marginTop: 16, padding: 14, borderRadius: 14, background: "var(--bg-1)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <b style={{ fontSize: 17 }}>{r.symbol}</b>
            <span style={{ color: V[r.verdict].c, fontWeight: 800 }}>{ar ? V[r.verdict].ar : V[r.verdict].en}</span>
          </div>
          <div style={{ fontSize: 12.5, color: "var(--txt-2)", margin: "6px 0 10px" }}>
            {ar ? r.reason : r.reason_en}
          </div>
          <div style={{ fontSize: 13, lineHeight: 1.7, background: "var(--bg-2)", padding: "10px 12px", borderRadius: 10, marginBottom: 10 }}>
            {ar ? r.brief : r.brief_en}
          </div>
          <Row l={ar ? "السعر الحي" : "Live price"} v={String(Number(Number(r.price).toPrecision(6)))} />
          <Row l={ar ? "تغيّر 24س" : "24h change"} v={`${r.change24h > 0 ? "+" : ""}${r.change24h}%`} />
          <Row l="RSI" v={r.rsi} />
          <Row l={ar ? "موقع النطاق" : "Range position"} v={`${Math.round(r.range_pos * 100)}%`} />
          <Row l={ar ? "ضغط العمق" : "Depth pressure"} v={r.ob_pressure === null ? "—" : r.ob_pressure} />
          <Row l={ar ? "التدفق المنفَّذ" : "Executed flow"} v={r.cvd_flow || "—"} />
          <Row l={ar ? "النموذج لونغ/شورت" : "Model L/S"} v={`${r.p_long}% / ${r.p_short}%`} />
          <Row l={ar ? "رافعة مقترحة" : "Suggested lev"} v={`${r.lev}x`} />
        </div>
      )}
    </div>
  );
}
