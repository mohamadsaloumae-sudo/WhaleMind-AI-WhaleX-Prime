import { KeyRound, Ban, Wallet, Eye } from "lucide-react";
import { T } from "./sections.js";

/** ⑦ الأمان — المخاوف الأربعة التي يسألها كل من يربط حسابه. */
export default function Security({ lang = "ar" }) {
  const ar = lang !== "en";
  const items = ar
    ? [
        [Wallet, "مالك يبقى عندك",
         "لا نستلم أموالاً ولا نحتفظ بها. رأس مالك في حسابك على منصّتك."],
        [Ban, "بلا صلاحية سحب",
         "المفتاح الذي تعطينا إياه للتداول فقط. لا يستطيع أحد سحب دولار."],
        [KeyRound, "مفاتيح مشفّرة",
         "تُخزَّن مشفّرة على خادمنا، ولا تظهر لأحد بعد الحفظ."],
        [Eye, "توقفه متى شئت",
         "زرّ واحد يوقف التداول الآلي، وآخر يفصل المنصّة نهائياً."],
      ]
    : [
        [Wallet, "Your funds stay yours",
         "We never receive or hold money. Your capital sits in your own exchange account."],
        [Ban, "No withdrawal permission",
         "The key you give us trades only. Nobody can move a dollar out."],
        [KeyRound, "Keys are encrypted",
         "Stored encrypted on our server and never shown again after saving."],
        [Eye, "Stop it anytime",
         "One switch pauses auto-trading, another unlinks the exchange entirely."],
      ];

  return (
    <section style={{ padding: "10px 20px 36px", background: T.bg }}>
      <h2 style={{
        fontSize: 21, fontWeight: 800, color: T.txt,
        textAlign: "center", margin: "0 0 20px",
      }}>
        {ar ? "أموالك لا تلمسها أيدينا" : "We never touch your funds"}
      </h2>

      <div style={{
        maxWidth: 420, margin: "0 auto",
        display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10,
      }}>
        {items.map(([Icon, title, desc], i) => (
          <div key={i} style={{
            background: T.card, border: `1px solid ${T.border}`,
            borderRadius: 14, padding: "15px 13px",
          }}>
            <Icon size={19} style={{ color: T.brand, marginBottom: 9 }} />
            <div style={{
              fontSize: 12.5, fontWeight: 800, color: T.txt, marginBottom: 5,
            }}>{title}</div>
            <div style={{ fontSize: 11, color: T.txt2, lineHeight: 1.7 }}>
              {desc}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
