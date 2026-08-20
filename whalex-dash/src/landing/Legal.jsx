import { AlertTriangle } from "lucide-react";
import { T } from "./sections.js";

/**
 * ⑪ تحذير المخاطر — ليس تزييناً قانونياً.
 *   التداول بالرافعة يُفقد المال، ومن حقّ الزائر أن يعرف قبل أن يدفع.
 */
export default function Legal({ lang = "ar", onStart }) {
  const ar = lang !== "en";
  return (
    <section style={{
      padding: "24px 20px 40px", background: T.bg,
      borderTop: `1px solid ${T.border}`,
    }}>
      <div style={{
        maxWidth: 420, margin: "0 auto 22px", textAlign: "center",
      }}>
        <h2 style={{
          fontSize: 19, fontWeight: 800, color: T.txt, margin: "0 0 8px",
        }}>
          {ar ? "جرّبه أسبوعاً بلا مقابل" : "Try it free for a week"}
        </h2>
        <p style={{
          fontSize: 12.5, color: T.txt2, margin: "0 0 16px", lineHeight: 1.75,
        }}>
          {ar
            ? "اربط حسابك، فعّل التداول، وشاهد النظام يعمل. توقفه متى شئت."
            : "Link your account, switch it on, and watch it work. Stop whenever you want."}
        </p>
        <button onClick={onStart} style={{
          width: "100%", padding: "14px 20px", borderRadius: 13,
          border: "none", cursor: "pointer",
          background: `linear-gradient(95deg, ${T.brand}, ${T.brand2})`,
          color: "#04121a", fontSize: 15, fontWeight: 800,
        }}>
          {ar ? "ابدأ الآن" : "Start now"}
        </button>
      </div>

      <div style={{
        maxWidth: 420, margin: "0 auto 18px",
        display: "flex", gap: 10, alignItems: "flex-start",
        background: "rgba(248,113,113,.06)",
        border: `1px solid ${T.red}33`,
        borderRadius: 13, padding: "14px 15px",
      }}>
        <AlertTriangle size={17} style={{ color: T.red, flexShrink: 0, marginTop: 2 }} />
        <div style={{ fontSize: 11, color: T.txt2, lineHeight: 1.85 }}>
          <b style={{ color: T.txt, display: "block", marginBottom: 4, fontSize: 12 }}>
            {ar ? "تنبيه المخاطر" : "Risk warning"}
          </b>
          {ar
            ? "تداول العملات الرقمية بالرافعة ينطوي على مخاطر عالية وقد يؤدّي إلى خسارة رأس مالك كلّه. النتائج السابقة مرجعية ولا تضمن نتائج مستقبلية. لا تُخاطر بمال تحتاجه، والقرار النهائي ومسؤوليته عليك وحدك."
            : "Leveraged crypto trading carries high risk and can lose your entire capital. Past results are indicative only and do not guarantee future performance. Never risk money you need, and the final decision and its consequences are yours alone."}
        </div>
      </div>

      <div style={{
        maxWidth: 420, margin: "0 auto", textAlign: "center",
        fontSize: 10.5, color: T.txt3, lineHeight: 2,
      }}>
        <div style={{ marginBottom: 6 }}>
          <a href="/terms" style={{ color: T.txt3, textDecoration: "none" }}>
            {ar ? "الشروط والأحكام" : "Terms"}
          </a>
          {"  ·  "}
          <a href="/privacy" style={{ color: T.txt3, textDecoration: "none" }}>
            {ar ? "الخصوصية" : "Privacy"}
          </a>
          {"  ·  "}
          <a href="/refund" style={{ color: T.txt3, textDecoration: "none" }}>
            {ar ? "الاسترداد" : "Refunds"}
          </a>
          {"  ·  "}
          <a href="/support" style={{ color: T.txt3, textDecoration: "none" }}>
            {ar ? "الدعم" : "Support"}
          </a>
        </div>
        <div>© {new Date().getFullYear()} WhaleX Prime</div>
      </div>
    </section>
  );
}
