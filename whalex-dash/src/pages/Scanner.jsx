// فاحص العملات
import { useState } from "react";
import { api } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { Search } from "lucide-react";

export default function Scanner() {
  const { t } = useLang();
  const [symbol, setSymbol] = useState("");
  const [result, setResult] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function scan(e) {
    e.preventDefault();
    if (!symbol.trim()) return;
    setBusy(true); setErr(""); setResult(null);
    const sym = symbol.trim().toUpperCase();
    try {
      const data = await api.get(`/api/scanner/scan?symbol=${encodeURIComponent(sym)}`);
      setResult(data);
    } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-title"><Search size={14} style={{ verticalAlign: "middle", marginInlineEnd: 6 }} /> {t("liveScan")}</div>
        <form onSubmit={scan} style={{ display: "flex", gap: 10 }}>
          <input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder={t("scanPlaceholder")}
            style={{ flex: 1, padding: "12px 14px", borderRadius: "var(--radius-sm)",
              background: "var(--bg-0)", border: "1px solid var(--bg-3)",
              color: "var(--txt-1)", fontSize: 15, outline: "none" }} />
          <button className="btn btn-primary" disabled={busy}>
            {busy ? t("scanning") : t("scan")}
          </button>
        </form>
      </div>

      {err && <div className="alert info">{t("scanFail")}: {err}</div>}

      {result && (
        <div className="card">
          <div className="card-title">{t("scanResult")} — {symbol.toUpperCase()}</div>
          <pre style={{ fontSize: 13, color: "var(--txt-2)", whiteSpace: "pre-wrap",
            wordBreak: "break-word", direction: "ltr", textAlign: "left",
            background: "var(--bg-0)", padding: 16, borderRadius: "var(--radius-sm)" }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
