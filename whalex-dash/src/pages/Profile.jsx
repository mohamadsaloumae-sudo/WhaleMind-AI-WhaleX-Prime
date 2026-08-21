import { useEffect, useState } from "react";
import { User, Save, Gift, Wallet } from "lucide-react";
import { api } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";

const NETS = ["TRC20", "BEP20", "ERC20", "SOL"];

/**
 * 👤 حسابي — بيانات المستخدم ومحفظته وإحالاته.
 *    البيانات اختيارية إلا عند طلب السحب.
 */
export default function Profile() {
  const { lang } = useLang();
  const ar = lang !== "en";
  const [p, setP] = useState(null);
  const [ref, setRef] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    api.get("/api/referral/profile").then(setP).catch(() => setP({}));
    api.get("/api/referral/me").then(setRef).catch(() => {});
  }, []);

  if (!p) return <div className="loading">…</div>;

  const set = (k, v) => setP({ ...p, [k]: v });

  const save = async () => {
    setBusy(true); setMsg(null);
    try {
      await api.post("/api/referral/profile", p);
      setMsg({ t: "ok", x: ar ? "✅ حُفظت بياناتك" : "✅ Saved" });
    } catch (e) {
      setMsg({ t: "err", x: e?.message || (ar ? "تعذّر الحفظ" : "Save failed") });
    } finally { setBusy(false); }
  };

  const F = ({ k, label, ph, type = "text" }) => (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginBottom: 5 }}>{label}</div>
      <input
        type={type}
        value={p[k] || ""}
        onChange={(e) => set(k, e.target.value)}
        placeholder={ph || ""}
        style={{
          width: "100%", padding: "11px 13px", borderRadius: 10,
          background: "rgba(255,255,255,.04)", border: "1px solid var(--border)",
          color: "var(--txt-1)", fontSize: 13,
        }}
      />
    </div>
  );

  return (
    <div style={{ maxWidth: 560, margin: "0 auto", paddingBottom: 30 }}>
      <div className="card" style={{ padding: 18, marginBottom: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 16 }}>
          <User size={18} style={{ color: "var(--brand)" }} />
          <span style={{ fontSize: 15, fontWeight: 800 }}>
            {ar ? "بياناتي" : "My details"}
          </span>
        </div>

        <F k="name" label={ar ? "الاسم الكامل" : "Full name"} />
        <F k="email" label={ar ? "البريد" : "Email"} type="email" />
        <F k="phone" label={ar ? "رقم الهاتف" : "Phone"} ph="+971 50 000 0000" />
        <F k="country" label={ar ? "البلد" : "Country"} />
        <F k="birth_date" label={ar ? "تاريخ الميلاد" : "Date of birth"} ph="1990-01-01" />

        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          marginTop: 18, marginBottom: 12,
          paddingTop: 14, borderTop: "1px solid rgba(255,255,255,.06)",
        }}>
          <Wallet size={16} style={{ color: "var(--brand)" }} />
          <span style={{ fontSize: 13, fontWeight: 700 }}>
            {ar ? "محفظة استلام الأرباح" : "Payout wallet"}
          </span>
        </div>

        <F k="usdt_wallet" label={ar ? "عنوان USDT" : "USDT address"} />

        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginBottom: 7 }}>
            {ar ? "الشبكة" : "Network"}
          </div>
          <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
            {NETS.map((n) => (
              <button key={n} onClick={() => set("usdt_network", n)}
                style={{
                  padding: "7px 14px", borderRadius: 9, cursor: "pointer",
                  fontSize: 11.5, fontWeight: p.usdt_network === n ? 800 : 600,
                  background: p.usdt_network === n ? "rgba(45,212,191,.14)" : "transparent",
                  border: `1px solid ${p.usdt_network === n ? "var(--brand)" : "rgba(255,255,255,.1)"}`,
                  color: p.usdt_network === n ? "var(--brand)" : "var(--txt-3)",
                }}>{n}</button>
            ))}
          </div>
        </div>

        <button className="btn btn-primary btn-block" onClick={save} disabled={busy}>
          <Save size={16} /> {busy ? "…" : (ar ? "حفظ" : "Save")}
        </button>

        {msg && (
          <div style={{
            marginTop: 11, fontSize: 12, textAlign: "center",
            color: msg.t === "ok" ? "#22c55e" : "#f87171",
          }}>{msg.x}</div>
        )}

        <div style={{ fontSize: 10.5, color: "var(--txt-3)", marginTop: 12, lineHeight: 1.75 }}>
          {ar
            ? "بياناتك مطلوبة عند طلب سحب أرباح الإحالة فقط."
            : "These details are required only when requesting a referral payout."}
        </div>
      </div>

      {ref && (
        <div className="card" style={{ padding: 18 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 12 }}>
            <Gift size={17} style={{ color: "var(--brand)" }} />
            <span style={{ fontSize: 14, fontWeight: 800 }}>
              {ar ? "إحالاتي" : "My referrals"}
            </span>
            <span style={{
              marginInlineStart: "auto", fontSize: 13, fontWeight: 900,
              color: "var(--brand)", direction: "ltr",
            }}>{ref.code}</span>
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            {[[ref.signups, ar ? "دعوة" : "Invited"],
              [ref.subscribers, ar ? "مشترك" : "Subscribed"],
              [`$${ref.total_earned}`, ar ? "أرباح" : "Earned"]].map(([v, l], i) => (
              <div key={i} style={{
                flex: 1, textAlign: "center", padding: "11px 4px",
                background: "rgba(255,255,255,.03)", borderRadius: 10,
                border: "1px solid var(--border)",
              }}>
                <div style={{ fontSize: 17, fontWeight: 900, color: i === 2 ? "#22c55e" : "var(--txt-1)" }}>{v}</div>
                <div style={{ fontSize: 10, color: "var(--txt-3)", marginTop: 2 }}>{l}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
