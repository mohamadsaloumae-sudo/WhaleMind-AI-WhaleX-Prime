import { T } from "./sections.js";

/**
 * ③ الفرق الجوهري — خدمات الإشارات ترسل نصّاً، ونحن ننفّذ.
 *   منافس معروف يقول في أسئلته: "لسنا روبوت تنفيذ — أنت تنفّذ يدوياً".
 *   هذا الجدول يجعل الفرق مرئياً في ثانيتين.
 */
export default function WhyDifferent({ lang = "ar" }) {
  const ar = lang !== "en";
  const rows = ar
    ? [
        ["يجد الفرصة", true, true],
        ["يفتح الصفقة على حسابك", false, true],
        ["يراقبها لحظة بلحظة", false, true],
        ["يحمي الربح عند القمة", false, true],
        ["يُغلق عند الانقلاب", false, true],
        ["يعمل وأنت نائم", false, true],
      ]
    : [
        ["Finds the setup", true, true],
        ["Opens it on your account", false, true],
        ["Watches it tick by tick", false, true],
        ["Locks profit at the peak", false, true],
        ["Exits on reversal", false, true],
        ["Runs while you sleep", false, true],
      ];

  return (
    <section style={{ padding: "10px 20px 36px", background: T.bg }}>
      <h2 style={{
        fontSize: 21, fontWeight: 800, color: T.txt,
        textAlign: "center", margin: "0 0 6px",
      }}>
        {ar ? "الفرق ليس في الإشارة" : "The difference isn't the signal"}
      </h2>
      <p style={{
        fontSize: 13, color: T.txt2, textAlign: "center",
        margin: "0 auto 20px", maxWidth: 380, lineHeight: 1.75,
      }}>
        {ar
          ? "خدمات التوصيات ترسل لك رسالة، ثم تتركك تفتح وتراقب وتُغلق بنفسك. نحن نفعلها كلها."
          : "Signal services send you a message, then leave you to open, watch and close it yourself. We do all of it."}
      </p>

      <div style={{
        maxWidth: 420, margin: "0 auto", borderRadius: 16, overflow: "hidden",
        border: `1px solid ${T.border}`, background: T.card,
      }}>
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 68px 68px",
          padding: "11px 14px", borderBottom: `1px solid ${T.border}`,
          background: "rgba(255,255,255,.03)",
          fontSize: 10.5, fontWeight: 700, color: T.txt3,
        }}>
          <span />
          <span style={{ textAlign: "center" }}>
            {ar ? "خدمة توصيات" : "Signals"}
          </span>
          <span style={{ textAlign: "center", color: T.brand }}>WhaleX</span>
        </div>

        {rows.map(([label, a, b], i) => (
          <div key={i} style={{
            display: "grid", gridTemplateColumns: "1fr 68px 68px",
            alignItems: "center", padding: "11px 14px",
            borderBottom: i < rows.length - 1 ? `1px solid ${T.border}` : "none",
          }}>
            <span style={{ fontSize: 12.5, color: T.txt, fontWeight: 500 }}>
              {label}
            </span>
            <span style={{
              textAlign: "center", fontSize: 15,
              color: a ? T.txt2 : "rgba(255,255,255,.16)",
            }}>{a ? "✓" : "—"}</span>
            <span style={{
              textAlign: "center", fontSize: 15, fontWeight: 800,
              color: b ? T.brand2 : "rgba(255,255,255,.16)",
            }}>{b ? "✓" : "—"}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
