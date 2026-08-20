import { useEffect, useState } from "react";
import { Gift, Check } from "lucide-react";
import { binance } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";

/** 🎁 بطاقة التجربة — أسبوع مجاني ببصمة الجهاز. */
export default function TrialCard() {
  const { lang } = useLang();
  const ar = lang !== "en";
  const [st, setSt] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const load = () =>
    binance.trialStatus().then(setSt).catch(() => setSt({ used: false }));

  useEffect(() => { load(); }, []);

  const fp = () => {
    let v = localStorage.getItem("wx_device");
    if (!v) {
      v = Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem("wx_device", v);
    }
    return v;
  };

  const start = async () => {
    setBusy(true); setMsg("");
    try {
      const r = await binance.trialStart(fp());
      setMsg(ar ? `✅ بدأت تجربتك — ${r.days} أيام` : `✅ Trial started — ${r.days} days`);
      load();
      setTimeout(() => window.location.reload(), 1400);
    } catch (e) {
      setMsg("⚠️ " + (e?.message || (ar ? "تعذّر البدء" : "Could not start")));
    } finally { setBusy(false); }
  };

  if (!st) return null;

  if (st.active) {
    return (
      <div className="card" style={{
        padding: 16, marginBottom: 14,
        background: "rgba(45,212,191,.07)", border: "1px solid rgba(45,212,191,.35)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <Check size={18} style={{ color: "var(--brand)" }} />
          <div>
            <div style={{ fontSize: 13.5, fontWeight: 800, color: "var(--txt-1)" }}>
              {ar ? "تجربتك المجانية نشطة" : "Your free trial is active"}
            </div>
            <div style={{ fontSize: 11.5, color: "var(--txt-2)", marginTop: 2 }}>
              {ar ? `بقي ${st.days_left} يوماً` : `${st.days_left} days left`}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (st.used) return null;

  return (
    <div className="card" style={{
      padding: 18, marginBottom: 14,
      background: "rgba(45,212,191,.07)", border: "1px solid rgba(45,212,191,.35)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 8 }}>
        <Gift size={19} style={{ color: "var(--brand)" }} />
        <span style={{ fontSize: 15, fontWeight: 800, color: "var(--txt-1)" }}>
          {ar ? "جرّب أسبوعاً مجاناً" : "Try a free week"}
        </span>
      </div>
      <p style={{ fontSize: 12.5, color: "var(--txt-2)", lineHeight: 1.75, marginBottom: 14 }}>
        {ar
          ? "سبعة أيام كاملة بلا بطاقة ائتمان. يعمل النظام على حسابك، وتفاصيل الإشارات تُفتح عند الاشتراك."
          : "Seven full days, no credit card. The system runs on your account; signal details unlock when you subscribe."}
      </p>
      <button className="btn btn-primary btn-block" onClick={start} disabled={busy}>
        {busy ? (ar ? "..." : "...") : (ar ? "ابدأ التجربة الآن" : "Start trial now")}
      </button>
      {msg && (
        <div style={{ fontSize: 12, marginTop: 10, textAlign: "center", color: "var(--txt-2)" }}>
          {msg}
        </div>
      )}
    </div>
  );
}
