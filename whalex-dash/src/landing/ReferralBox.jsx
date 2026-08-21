import { Gift, Users, Wallet } from "lucide-react";
import { T } from "./sections.js";

/** ⑨ برنامج الإحالة — ادعُ واربح بلا حدّ. */
export default function ReferralBox({ lang = "ar" }) {
  const ar = lang !== "en";

  const steps = ar
    ? [
        [Users, "شارك رابطك", "رابط خاصّ بك بضغطة واحدة — بلا نماذج ولا شروط."],
        [Gift, "يشترك صديقك", "تُحتسب عمولتك تلقائياً على كل دفعة يدفعها."],
        [Wallet, "اسحب أرباحك", "بالـUSDT إلى محفظتك عند بلوغ ٥٠ دولاراً."],
      ]
    : [
        [Users, "Share your link", "Your own link in one click — no forms, no conditions."],
        [Gift, "They subscribe", "Your commission is credited automatically on each payment."],
        [Wallet, "Withdraw", "In USDT to your wallet once you reach $50."],
      ];

  return (
    <section style={{ padding: "10px 20px 36px", background: T.bg }}>
      <h2 style={{
        fontSize: 21, fontWeight: 800, color: T.txt,
        textAlign: "center", margin: "0 0 6px",
      }}>
        {ar ? "ادعُ أصدقاءك واربح" : "Invite friends and earn"}
      </h2>
      <p style={{
        fontSize: 12.5, color: T.txt2, textAlign: "center",
        margin: "0 auto 20px", maxWidth: 380, lineHeight: 1.75,
      }}>
        {ar
          ? "لكل مشترك رابط إحالة مجاني. تكسب من كل من يشترك عبره."
          : "Every subscriber gets a free referral link. You earn from everyone who subscribes through it."}
      </p>

      {/* 💰 النسب — بارزة وواضحة */}
      <div style={{
        maxWidth: 420, margin: "0 auto 16px",
        display: "grid", gridTemplateColumns: "1fr 1fr", gap: 11,
      }}>
        <div style={{
          background: "rgba(45,212,191,.09)", border: `1px solid ${T.brand}55`,
          borderRadius: 16, padding: "20px 12px", textAlign: "center",
        }}>
          <div style={{
            fontSize: 38, fontWeight: 900, color: T.brand,
            letterSpacing: -1.5, lineHeight: 1, direction: "ltr",
          }}>15%</div>
          <div style={{ fontSize: 11.5, color: T.txt, marginTop: 8, fontWeight: 700 }}>
            {ar ? "من أول اشتراك" : "of the first payment"}
          </div>
        </div>
        <div style={{
          background: "rgba(34,197,94,.08)", border: `1px solid ${T.brand2}44`,
          borderRadius: 16, padding: "20px 12px", textAlign: "center",
        }}>
          <div style={{
            fontSize: 38, fontWeight: 900, color: T.brand2,
            letterSpacing: -1.5, lineHeight: 1, direction: "ltr",
          }}>10%</div>
          <div style={{ fontSize: 11.5, color: T.txt, marginTop: 8, fontWeight: 700 }}>
            {ar ? "من ٣ تجديدات تالية" : "on 3 renewals after"}
          </div>
        </div>
      </div>

      <div style={{
        maxWidth: 420, margin: "0 auto 16px",
        display: "flex", flexDirection: "column", gap: 10,
      }}>
        {steps.map(([Icon, title, desc], i) => (
          <div key={i} style={{
            display: "flex", gap: 12, alignItems: "flex-start",
            background: T.card, border: `1px solid ${T.border}`,
            borderRadius: 14, padding: "13px 14px",
          }}>
            <Icon size={17} style={{ color: T.brand, flexShrink: 0, marginTop: 2 }} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.txt, marginBottom: 3 }}>
                {title}
              </div>
              <div style={{ fontSize: 11.5, color: T.txt2, lineHeight: 1.7 }}>
                {desc}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div style={{
        maxWidth: 420, margin: "0 auto", textAlign: "center",
        fontSize: 11, color: T.txt3, lineHeight: 1.8,
      }}>
        {ar
          ? "مثال: صديقك يشترك شهرياً بـ١٠٠$ → تكسب ١٥$ أول مرّة، ثم ١٠$ لكل تجديد (٣ مرّات)."
          : "Example: a friend subscribes at $100/month → you earn $15 first, then $10 per renewal (3 times)."}
      </div>
    </section>
  );
}
