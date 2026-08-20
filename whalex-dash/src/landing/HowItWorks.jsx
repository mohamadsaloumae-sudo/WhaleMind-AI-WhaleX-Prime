import { Link2, ToggleRight, Eye } from "lucide-react";
import { T } from "./sections.js";

/**
 * ⑤ كيف يعمل — ثلاث خطوات حقيقية لا مراحل تسويقية.
 *   الترقيم هنا مبرَّر: هذا تسلسل فعلي يمرّ به المستخدم.
 */
export default function HowItWorks({ lang = "ar" }) {
  const ar = lang !== "en";
  const steps = ar
    ? [
        [Link2, "اربط منصّتك",
         "مفتاح API من منصّتك المفضّلة — بلا صلاحية سحب. تربط حساباً أو سبعة."],
        [ToggleRight, "اضبط ثم فعّل",
         "تحدّد مبلغ الصفقة وعدد الصفقات المتزامنة والدرجات المقبولة. ثم تضغط تفعيل."],
        [Eye, "راقب فقط",
         "النظام يفتح ويدير ويُغلق. أنت ترى كل صفقة وشارتها وتفاصيلها لحظياً."],
      ]
    : [
        [Link2, "Connect your exchange",
         "An API key from your exchange — no withdrawal permission. One account or seven."],
        [ToggleRight, "Set limits, then enable",
         "You set trade size, max concurrent positions and accepted grades. Then flip it on."],
        [Eye, "Just watch",
         "The system opens, manages and closes. You see every trade, its chart and details, live."],
      ];

  return (
    <section style={{ padding: "10px 20px 36px", background: T.bg }}>
      <h2 style={{
        fontSize: 21, fontWeight: 800, color: T.txt,
        textAlign: "center", margin: "0 0 22px",
      }}>
        {ar ? "ثلاث خطوات وينتهي دورك" : "Three steps, then you're done"}
      </h2>

      <div style={{
        maxWidth: 420, margin: "0 auto",
        display: "flex", flexDirection: "column", gap: 12,
      }}>
        {steps.map(([Icon, title, desc], i) => (
          <div key={i} style={{
            display: "flex", gap: 13, alignItems: "flex-start",
            background: T.card, border: `1px solid ${T.border}`,
            borderRadius: 15, padding: "15px 15px",
          }}>
            <div style={{
              flexShrink: 0, width: 40, height: 40, borderRadius: 11,
              display: "flex", alignItems: "center", justifyContent: "center",
              background: "rgba(45,212,191,.1)", border: `1px solid ${T.brand}33`,
              position: "relative",
            }}>
              <Icon size={19} style={{ color: T.brand }} />
              <span style={{
                position: "absolute", top: -6, insetInlineEnd: -6,
                width: 19, height: 19, borderRadius: 19,
                background: T.brand, color: "#04121a",
                fontSize: 10.5, fontWeight: 900,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>{i + 1}</span>
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{
                fontSize: 14.5, fontWeight: 800, color: T.txt, marginBottom: 4,
              }}>{title}</div>
              <div style={{
                fontSize: 12.5, color: T.txt2, lineHeight: 1.75,
              }}>{desc}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
