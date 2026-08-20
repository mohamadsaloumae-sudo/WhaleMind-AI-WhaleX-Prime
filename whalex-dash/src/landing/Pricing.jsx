import { Check, Shield } from "lucide-react";
import { T } from "./sections.js";

/**
 * ⑧ الاشتراك — $100 شهر · $270 ثلاثة أشهر · أسبوع مجاني.
 *   بلا عدّاد تنازلي ولا "مقاعد متبقّية": ضغط زائف يُفقد الثقة.
 */
export default function Pricing({ lang = "ar", onStart }) {
  const ar = lang !== "en";

  const perks = ar
    ? ["كل الرادارات · بلا استثناء",
       "تنفيذ آلي على سبع منصّات",
       "ربط حسابات متعدّدة معاً",
       "مدير صفقات يحرس الربح",
       "شارت حيّ لكل صفقة",
       "دعم بالعربية والإنجليزية"]
    : ["Every radar · no exceptions",
       "Automated execution on 7 exchanges",
       "Link multiple accounts at once",
       "Position manager guarding profit",
       "Live chart for every trade",
       "Support in Arabic and English"];

  const plans = [
    {
      name: ar ? "شهري" : "Monthly",
      price: "$100",
      per: ar ? "/ شهر" : "/ month",
      note: "",
      hot: false,
    },
    {
      name: ar ? "ثلاثة أشهر" : "3 months",
      price: "$270",
      per: ar ? "/ ٣ أشهر" : "/ 3 months",
      note: ar ? "توفير $30" : "Save $30",
      hot: true,
    },
  ];

  return (
    <section style={{ padding: "10px 20px 36px", background: T.bg }}>
      <h2 style={{
        fontSize: 21, fontWeight: 800, color: T.txt,
        textAlign: "center", margin: "0 0 6px",
      }}>
        {ar ? "خطّة واحدة · كل شيء مفتوح" : "One plan · everything included"}
      </h2>
      <p style={{
        fontSize: 12.5, color: T.txt2, textAlign: "center",
        margin: "0 auto 20px", maxWidth: 360, lineHeight: 1.7,
      }}>
        {ar
          ? "لا باقات مجزّأة ولا مزايا محجوبة. الدفع بالـUSDT."
          : "No tiered packages, no locked features. Paid in USDT."}
      </p>

      <div style={{
        maxWidth: 420, margin: "0 auto 16px",
        display: "grid", gridTemplateColumns: "1fr 1fr", gap: 11,
      }}>
        {plans.map((pl, i) => (
          <div key={i} style={{
            position: "relative", borderRadius: 16, padding: "18px 13px",
            textAlign: "center",
            background: pl.hot ? "rgba(45,212,191,.07)" : T.card,
            border: `1px solid ${pl.hot ? T.brand + "66" : T.border}`,
          }}>
            {pl.hot && (
              <span style={{
                position: "absolute", top: -9, insetInline: 0, margin: "0 auto",
                width: "fit-content", padding: "3px 10px", borderRadius: 20,
                background: T.brand, color: "#04121a",
                fontSize: 9.5, fontWeight: 900,
              }}>{ar ? "الأوفر" : "BEST VALUE"}</span>
            )}
            <div style={{ fontSize: 12, color: T.txt3, marginBottom: 7, fontWeight: 600 }}>
              {pl.name}
            </div>
            <div style={{
              fontSize: 30, fontWeight: 900, color: T.txt,
              letterSpacing: -1, direction: "ltr",
            }}>{pl.price}</div>
            <div style={{ fontSize: 11, color: T.txt3, marginTop: 2 }}>{pl.per}</div>
            {pl.note && (
              <div style={{ fontSize: 10.5, color: T.brand2, marginTop: 6, fontWeight: 700 }}>
                {pl.note}
              </div>
            )}
          </div>
        ))}
      </div>

      <div style={{
        maxWidth: 420, margin: "0 auto 16px",
        background: T.card, border: `1px solid ${T.border}`,
        borderRadius: 15, padding: "15px 16px",
      }}>
        {perks.map((x, i) => (
          <div key={i} style={{
            display: "flex", alignItems: "center", gap: 9,
            padding: "6px 0", fontSize: 12.5, color: T.txt,
          }}>
            <Check size={15} style={{ color: T.brand2, flexShrink: 0 }} />
            {x}
          </div>
        ))}
      </div>

      <button onClick={onStart} style={{
        display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
        width: "100%", maxWidth: 420, margin: "0 auto 12px",
        padding: "15px 20px", borderRadius: 13, border: "none", cursor: "pointer",
        background: `linear-gradient(95deg, ${T.brand}, ${T.brand2})`,
        color: "#04121a", fontSize: 15.5, fontWeight: 800,
      }}>
        {ar ? "ابدأ أسبوعك المجاني" : "Start your free week"}
      </button>

      <div style={{
        maxWidth: 420, margin: "0 auto",
        display: "flex", alignItems: "flex-start", gap: 9,
        background: "rgba(45,212,191,.06)", border: `1px solid ${T.brand}33`,
        borderRadius: 13, padding: "13px 14px",
      }}>
        <Shield size={17} style={{ color: T.brand, flexShrink: 0, marginTop: 1 }} />
        <div>
          <div style={{ fontSize: 12.5, fontWeight: 800, color: T.txt, marginBottom: 3 }}>
            {ar ? "ضمان الاسترجاع" : "Money-back guarantee"}
          </div>
          <div style={{ fontSize: 11.5, color: T.txt2, lineHeight: 1.7 }}>
            {ar
              ? "إن كانت نتيجتك سلبية خلال ١٤ يوماً مع تشغيل النظام كما هو، نُرجع اشتراكك. الشروط في صفحة الاسترداد."
              : "If your net result is negative within 14 days while running the system as intended, we refund your subscription. Conditions on the refund page."}
          </div>
        </div>
      </div>
    </section>
  );
}
