import { useEffect, useState } from "react";

/* 💰 رأس مال التداول — حقل واحد يضبط المبلغ والسقف تلقائياً.
   المشترك يحدّد كم يريد أن يتداول به، ولا نمسّ ما زاد عنه. */

export default function CapitalField({ market = "futures", exchange = "binance",
                                       ar = true, onSaved }) {
  const [cap, setCap] = useState("");
  const [prev, setPrev] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch("/api/capital/current", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const a = (d.accounts || []).find((x) => x.exchange === exchange);
        if (a?.capital > 0) { setCap(String(a.capital)); }
      })
      .catch(() => {});
  }, [exchange]);

  useEffect(() => {
    const v = Number(cap);
    if (!Number.isFinite(v) || v <= 0) { setPrev(null); return; }
    const t = setTimeout(() => {
      fetch(`/api/capital/preview?capital=${v}&market=${market}`)
        .then((r) => r.json()).then(setPrev).catch(() => setPrev(null));
    }, 300);
    return () => clearTimeout(t);
  }, [cap, market]);

  async function save() {
    const v = Number(cap);
    if (!Number.isFinite(v) || v <= 0) return;
    setBusy(true); setMsg(""); setErr("");
    try {
      const r = await fetch("/api/capital", {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ capital: v, market, exchange }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "تعذّر الحفظ");
      setMsg(ar ? "حُفظ ✓" : "Saved ✓");
      onSaved && onSaved(d);
      setTimeout(() => setMsg(""), 2500);
    } catch (e) { setErr(String(e.message || e)); }
    finally { setBusy(false); }
  }

  const L = ar
    ? { title: "رأس مال التداول", ph: "المبلغ الذي يتداول به البوت",
        amt: "مبلغ الصفقة", slots: "حتى", trades: "صفقة",
        res: "احتياطيّ", save: "حفظ",
        note: "لن نمسّ ما زاد عن هذا المبلغ في محفظتك — البوت يتداول بهذا القدر فقط." }
    : { title: "Trading capital", ph: "Amount the bot may trade with",
        amt: "Per trade", slots: "Up to", trades: "trades",
        res: "Reserve", save: "Save",
        note: "Anything above this stays untouched — the bot only trades this amount." };

  return (
    <div style={{
      background: "rgba(15,163,146,.06)", border: "1px solid rgba(15,163,146,.22)",
      borderRadius: 14, padding: 16, marginBottom: 16,
      direction: ar ? "rtl" : "ltr", textAlign: ar ? "right" : "left",
    }}>
      <div style={{ fontWeight: 700, fontSize: 14.5, color: "#eaf6f4", marginBottom: 10 }}>
        💰 {L.title}
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <input
          type="number" min="1" value={cap} placeholder={L.ph}
          onChange={(e) => setCap(e.target.value)}
          style={{
            flex: 1, padding: "11px 13px", borderRadius: 11,
            border: "1px solid rgba(255,255,255,.12)",
            background: "rgba(0,0,0,.25)", color: "#eaf6f4",
            fontSize: 15, fontWeight: 600, textAlign: ar ? "right" : "left",
          }}
        />
        <button onClick={save} disabled={busy || !prev?.ok}
          style={{
            padding: "11px 20px", borderRadius: 11, border: "none",
            background: prev?.ok ? "#0fa392" : "rgba(255,255,255,.08)",
            color: prev?.ok ? "#04211f" : "#6b8088",
            fontWeight: 800, fontSize: 13.5,
            cursor: prev?.ok ? "pointer" : "not-allowed",
          }}>
          {busy ? "…" : L.save}
        </button>
      </div>

      {prev && !prev.ok && (
        <div style={{ fontSize: 12, color: "#ffb3b3", marginBottom: 8 }}>
          ⚠️ {prev.why}
        </div>
      )}

      {prev?.ok && (
        <div style={{
          background: "rgba(0,0,0,.2)", borderRadius: 10, padding: "10px 12px",
          marginBottom: 9, fontSize: 13,
        }}>
          <Row k={L.amt} v={`${prev.amount}$`} hi />
          <Row k={L.slots} v={`${prev.slots} ${L.trades}`} />
          <Row k={L.res} v={`${prev.reserve}$`} dim last />
        </div>
      )}

      <div style={{ fontSize: 11.5, color: "#8fa9b4", lineHeight: 1.65 }}>
        ⓘ {L.note}
      </div>

      {msg && <div style={{ fontSize: 12.5, color: "#22c55e", marginTop: 8 }}>{msg}</div>}
      {err && <div style={{ fontSize: 12.5, color: "#ef4444", marginTop: 8 }}>{err}</div>}
    </div>
  );
}

function Row({ k, v, hi, dim, last }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", padding: "5px 0",
      borderBottom: last ? "none" : "1px solid rgba(255,255,255,.05)",
    }}>
      <span style={{ color: "#8fa9b4" }}>{k}</span>
      <b style={{ color: hi ? "#0fa392" : dim ? "#8fa9b4" : "#eaf6f4",
                  fontSize: hi ? 15 : 13 }}>{v}</b>
    </div>
  );
}
