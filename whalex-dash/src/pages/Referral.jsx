import { useEffect, useState } from "react";
import { Gift, Copy, Check, Clock, Hourglass, CircleDollarSign } from "lucide-react";
import { api } from "../lib/api.js";
import { useLang } from "../context/LangContext.jsx";

/**
 * 🎁 برنامج الإحالة — الرابط بضغطة، والبيانات عند السحب فقط.
 */
export default function Referral() {
  const { lang } = useLang();
  const ar = lang !== "en";
  const [d, setD] = useState(null);
  const [copied, setCopied] = useState(false);
  const [wallet, setWallet] = useState("");
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/api/referral/me").then(setD).catch(() => {});
  useEffect(() => { load(); }, []);

  if (!d) return <div className="loading">…</div>;

  const link = `${window.location.origin}/?ref=${d.code}`;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch { /* المتصفّح منع النسخ */ }
  };

  const ask = async () => {
    setBusy(true); setMsg(null);
    try {
      const r = await api.post("/api/referral/withdraw", { wallet });
      setMsg({ t: "ok", x: ar ? `✅ طُلب سحب ${r.amount}$` : `✅ Withdrawal requested: $${r.amount}` });
      setWallet(""); load();
    } catch (e) {
      setMsg({ t: "err", x: e?.message || (ar ? "تعذّر الطلب" : "Request failed") });
    } finally { setBusy(false); }
  };

  const STATE = {
    signed_up: [Clock, ar ? "سجّل فقط" : "Signed up", "var(--txt-3)"],
    trial: [Gift, ar ? "تجربة مجانية" : "Free trial", "var(--brand)"],
    trial_ended: [Hourglass, ar ? "انتهت التجربة — لم يشترك" : "Trial ended — didn't subscribe", "#fbbf24"],
    subscribed: [CircleDollarSign, ar ? "مشترك" : "Subscribed", "#22c55e"],
  };

  const Stat = ({ v, l, c }) => (
    <div style={{ flex: 1, textAlign: "center", padding: "12px 4px" }}>
      <div style={{ fontSize: 20, fontWeight: 900, color: c || "var(--txt-1)" }}>{v}</div>
      <div style={{ fontSize: 10.5, color: "var(--txt-3)", marginTop: 2 }}>{l}</div>
    </div>
  );

  return (
    <div style={{ maxWidth: 620, margin: "0 auto", paddingBottom: 30 }}>
      <div className="card" style={{ padding: 18, marginBottom: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 14 }}>
          <Gift size={19} style={{ color: "var(--brand)" }} />
          <span style={{ fontSize: 15.5, fontWeight: 800 }}>
            {ar ? "ادعُ أصدقاءك واربح" : "Invite and earn"}
          </span>
        </div>

        <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginBottom: 6 }}>
          {ar ? "رمزك" : "Your code"}
        </div>
        <div onClick={copy} style={{
          display: "flex", alignItems: "center", gap: 10, cursor: "pointer",
          background: "rgba(45,212,191,.08)", border: "1px solid rgba(45,212,191,.3)",
          borderRadius: 12, padding: "13px 15px", marginBottom: 10,
        }}>
          <span style={{
            flex: 1, fontSize: 17, fontWeight: 900, letterSpacing: 1.5,
            color: "var(--brand)", direction: "ltr",
          }}>{d.code}</span>
          {copied
            ? <Check size={17} style={{ color: "#22c55e" }} />
            : <Copy size={16} style={{ color: "var(--txt-3)" }} />}
        </div>

        <div onClick={copy} style={{
          fontSize: 10.5, color: "var(--txt-3)", cursor: "pointer",
          wordBreak: "break-all", direction: "ltr", marginBottom: 14,
        }}>{link}</div>

        <div style={{
          display: "flex", background: "rgba(255,255,255,.03)",
          borderRadius: 12, border: "1px solid var(--border)",
        }}>
          <Stat v={d.signups} l={ar ? "سجّلوا" : "Signed up"} />
          <Stat v={d.trials} l={ar ? "بالتجربة" : "In trial"} c="var(--brand)" />
          <Stat v={d.subscribers} l={ar ? "مشتركون" : "Subscribed"} c="#22c55e" />
          <Stat v={`$${d.total_earned}`} l={ar ? "أرباحك" : "Earned"} c="#22c55e" />
        </div>

        <div style={{
          fontSize: 11, color: "var(--txt-3)", textAlign: "center",
          marginTop: 12, lineHeight: 1.8,
        }}>
          {ar
            ? `${d.pct_first}% من أول اشتراك · ${d.pct_renew}% من ثلاثة تجديدات · السحب من ${d.min_withdraw}$`
            : `${d.pct_first}% of the first payment · ${d.pct_renew}% on three renewals · withdraw from $${d.min_withdraw}`}
        </div>
      </div>

      {d.people.length > 0 && (
        <div className="card" style={{ padding: "14px 16px", marginBottom: 14 }}>
          <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--txt-2)", marginBottom: 10 }}>
            {ar ? "من دعوتَهم" : "People you invited"}
          </div>
          {d.people.map((p, i) => {
            const [Icon, label, col] = STATE[p.state] || STATE.signed_up;
            return (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "10px 0",
                borderTop: i ? "1px solid rgba(255,255,255,.05)" : "none",
              }}>
                <Icon size={16} style={{ color: col, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--txt-1)" }}>
                    {p.name || (ar ? "مستخدم" : "User")}
                  </div>
                  <div style={{ fontSize: 10.5, color: col, marginTop: 2 }}>
                    {label}
                    {p.state === "trial" && p.trial_days_left > 0
                      ? ` · ${p.trial_days_left} ${ar ? "أيام" : "days"}`
                      : ""}
                  </div>
                </div>
                {p.earned > 0 && (
                  <span style={{ fontSize: 13, fontWeight: 800, color: "#22c55e", direction: "ltr" }}>
                    +${p.earned}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="card" style={{ padding: 18 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
          <span style={{ fontSize: 12.5, color: "var(--txt-3)", flex: 1 }}>
            {ar ? "الرصيد المتاح" : "Available balance"}
          </span>
          <span style={{ fontSize: 20, fontWeight: 900, color: "#22c55e", direction: "ltr" }}>
            ${d.available}
          </span>
        </div>

        {d.available >= d.min_withdraw ? (
          <>
            <input
              value={wallet}
              onChange={(e) => setWallet(e.target.value)}
              placeholder={ar ? "عنوان محفظة USDT (TRC20)" : "USDT wallet address (TRC20)"}
              style={{
                width: "100%", padding: "12px 14px", borderRadius: 11,
                background: "rgba(255,255,255,.04)", border: "1px solid var(--border)",
                color: "var(--txt-1)", fontSize: 12.5, marginBottom: 10,
                direction: "ltr",
              }}
            />
            <button className="btn btn-primary btn-block" onClick={ask} disabled={busy}>
              {busy ? "…" : (ar ? `طلب سحب $${d.available}` : `Withdraw $${d.available}`)}
            </button>
            <div style={{ fontSize: 10.5, color: "var(--txt-3)", marginTop: 9, lineHeight: 1.7 }}>
              {ar
                ? "نراجع الطلب ونرسل خلال ٤٨ ساعة. تأكّد من صحّة العنوان والشبكة."
                : "We review and send within 48 hours. Double-check the address and network."}
            </div>
          </>
        ) : (
          <div style={{
            fontSize: 12, color: "var(--txt-3)", textAlign: "center",
            padding: "10px 0", lineHeight: 1.8,
          }}>
            {ar
              ? `تحتاج $${(d.min_withdraw - d.available).toFixed(2)} إضافية للوصول لحدّ السحب`
              : `$${(d.min_withdraw - d.available).toFixed(2)} more to reach the withdrawal threshold`}
          </div>
        )}

        {msg && (
          <div style={{
            marginTop: 11, fontSize: 12, textAlign: "center",
            color: msg.t === "ok" ? "#22c55e" : "#f87171",
          }}>{msg.x}</div>
        )}
      </div>
    </div>
  );
}
