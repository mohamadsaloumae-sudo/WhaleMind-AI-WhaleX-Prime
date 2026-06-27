// الاشتراك — خطتان + دفع USDT-TRC20
import { useEffect, useState } from "react";
import { subscription } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";
import { Check, Crown, Copy, CheckCircle2 } from "lucide-react";

export default function Subscription() {
  const { t, lang } = useLang();
  const [sub, setSub] = useState(null);
  const [info, setInfo] = useState(null);
  const [plan, setPlan] = useState("month");
  const [txHash, setTxHash] = useState("");
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  async function load() {
    try { setSub(await subscription.status()); } catch { /* */ }
    try { setInfo(await subscription.plans()); } catch { /* */ }
  }
  useEffect(() => { load(); }, []);

  function copyWallet() {
    if (info?.wallet_address) {
      navigator.clipboard.writeText(info.wallet_address);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  async function upgrade(e) {
    e.preventDefault();
    setBusy(true); setMsg(null);
    try {
      const r = await subscription.upgrade({ tx_hash: txHash.trim(), plan });
      setMsg({ type: "success", text: t("upgradeSuccess") + " — " + r.plan });
      setTxHash(""); load();
      setTimeout(() => window.location.reload(), 2000);
    } catch (e) { setMsg({ type: "error", text: e.message }); }
    finally { setBusy(false); }
  }

  const isPro = sub?.is_active;
  const plans = info?.plans || [];
  const selectedPlan = plans.find((p) => p.id === plan);

  return (
    <div style={{ maxWidth: 560 }}>
      {msg && <div className={`alert ${msg.type}`}>{msg.text}</div>}

      {/* الباقة الحالية */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">{t("yourPlan")}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Crown size={28} color={isPro ? "var(--brand)" : "var(--txt-3)"} />
          <div>
            <div style={{ fontSize: 22, fontWeight: 800, color: isPro ? "var(--brand)" : "var(--txt-1)" }}>
              {isPro ? "PRO" : t("free")}
            </div>
            {isPro && sub?.expires_at && (
              <div style={{ fontSize: 13, color: "var(--txt-2)" }}>
                {t("expires")}: {new Date(sub.expires_at).toLocaleDateString(lang === "ar" ? "ar-AE" : "en-US", { timeZone: "Asia/Dubai" })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* الترقية */}
      <div className="card">
        <div className="card-title">{isPro ? t("renewSub") : t("upgradeToPro")}</div>

        {/* المزايا */}
        <ul style={{ listStyle: "none", display: "grid", gap: 10, marginBottom: 20 }}>
          {[t("feature1"), t("feature2"), t("feature3"), t("feature4")].map((f) => (
            <li key={f} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
              <Check size={16} color="var(--green)" /> {f}
            </li>
          ))}
        </ul>

        {/* اختيار الخطة */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 20 }}>
          {plans.map((p) => (
            <button
              key={p.id}
              onClick={() => setPlan(p.id)}
              style={{
                padding: "16px 12px", borderRadius: 12, cursor: "pointer",
                border: plan === p.id ? "2px solid var(--brand)" : "1px solid var(--border)",
                background: plan === p.id ? "var(--brand-dim)" : "var(--bg-2)",
                color: "var(--txt-1)", textAlign: "center",
              }}
            >
              <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{p.label}</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: "var(--brand)" }}>{p.price}$</div>
              <div style={{ fontSize: 11, color: "var(--txt-3)" }}>{p.days} {t("days")}</div>
            </button>
          ))}
        </div>

        {/* تعليمات الدفع */}
        <div style={{ background: "var(--bg-2)", borderRadius: 12, padding: 14, marginBottom: 16 }}>
          <div style={{ fontSize: 13, color: "var(--txt-2)", marginBottom: 8 }}>
            {t("payInstructions")} <strong style={{ color: "var(--brand)" }}>{selectedPlan?.price}$ USDT</strong> ({info?.network})
          </div>
          <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 6 }}>{t("walletAddress")}:</div>
          <div
            onClick={copyWallet}
            style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              gap: 8, padding: "10px 12px", background: "var(--bg-1)", borderRadius: 8,
              cursor: "pointer", fontFamily: "monospace", fontSize: 12, wordBreak: "break-all",
            }}
          >
            <span style={{ color: "var(--txt-1)" }}>{info?.wallet_address}</span>
            {copied ? <CheckCircle2 size={18} color="var(--green)" /> : <Copy size={18} color="var(--txt-3)" />}
          </div>
        </div>

        {/* إدخال tx_hash */}
        <form onSubmit={upgrade}>
          <div className="field">
            <label>{t("txHashLabel")}</label>
            <input value={txHash} onChange={(e) => setTxHash(e.target.value)} required placeholder={t("txHashPlaceholder")} />
          </div>
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? t("verifying") : t("confirmUpgrade")}
          </button>
        </form>
      </div>
    </div>
  );
}
