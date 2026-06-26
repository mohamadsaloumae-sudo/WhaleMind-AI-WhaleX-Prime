// الاشتراك
import { useEffect, useState } from "react";
import { subscription } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { Check, Crown } from "lucide-react";

export default function Subscription() {
  const { t } = useLang();
  const [sub, setSub] = useState(null);
  const [txHash, setTxHash] = useState("");
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try { setSub(await subscription.status()); } catch { /* */ }
  }
  useEffect(() => { load(); }, []);

  async function upgrade(e) {
    e.preventDefault();
    setBusy(true); setMsg(null);
    try {
      await subscription.upgrade({ tx_hash: txHash });
      setMsg({ type: "success", text: t("upgradeSuccess") });
      setTxHash(""); load();
    } catch (e) { setMsg({ type: "error", text: e.message }); }
    finally { setBusy(false); }
  }

  const isPro = sub?.tier === "pro" || sub?.tier === "admin";

  return (
    <div style={{ maxWidth: 560 }}>
      {msg && <div className={`alert ${msg.type}`}>{msg.text}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">{t("yourPlan")}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Crown size={28} color={isPro ? "var(--brand)" : "var(--txt-3)"} />
          <div>
            <div style={{ fontSize: 22, fontWeight: 800, color: isPro ? "var(--brand)" : "var(--txt-1)" }}>
              {isPro ? "PRO" : t("free")}
            </div>
            {sub?.expires_at && <div style={{ fontSize: 13, color: "var(--txt-2)" }}>{t("expires")}: {new Date(sub.expires_at).toLocaleDateString()}</div>}
          </div>
        </div>
      </div>

      {!isPro && (
        <div className="card">
          <div className="card-title">{t("upgradeToPro")}</div>
          <ul style={{ listStyle: "none", display: "grid", gap: 10, marginBottom: 20 }}>
            {[t("feature1"), t("feature2"), t("feature3"), t("feature4")].map((f) => (
              <li key={f} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
                <Check size={16} color="var(--green)" /> {f}
              </li>
            ))}
          </ul>
          <form onSubmit={upgrade}>
            <div className="field">
              <label>{t("txHash")}</label>
              <input value={txHash} onChange={(e) => setTxHash(e.target.value)} required placeholder="0x..." />
            </div>
            <button className="btn btn-primary btn-block" disabled={busy}>
              {busy ? t("processing") : t("confirmUpgrade")}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
