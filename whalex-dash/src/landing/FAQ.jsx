import { useState } from "react";
import { Plus } from "lucide-react";
import { T } from "./sections.js";

/** ⑩ الأسئلة — ما يسأله كل زائر قبل أن يربط حسابه فعلاً. */
export default function FAQ({ lang = "ar" }) {
  const ar = lang !== "en";
  const [open, setOpen] = useState(null);

  const qs = ar
    ? [
        ["هل تحتاجون أموالي؟",
         "لا. رأس مالك يبقى في حسابك على منصّتك، ونحن ننفّذ عليه بمفتاح تداول لا يملك صلاحية سحب."],
        ["كم أحتاج لأبدأ؟",
         "يعتمد على منصّتك، لكن ١٥-٢٠ دولاراً في محفظة الفيوتشر تكفي لأول صفقة اختبارية. وأنت تحدّد مبلغ كل صفقة."],
        ["هل أحتاج خبرة في التداول؟",
         "لا. النظام يفتح ويدير ويُغلق. لكن نُوصي بفهم المخاطر قبل رفع المبالغ — فالتداول ربح وخسارة."],
        ["هل أحتاج سيرفر أو برنامج؟",
         "لا شيء. كل شيء يعمل على خوادمنا، وأنت تراقب من جوّالك أو متصفّحك."],
        ["كيف أوقفه؟",
         "زرّ واحد يوقف التداول الآلي فوراً، وآخر يفصل المنصّة نهائياً. لا التزام ولا فترة انتظار."],
        ["ما نسبة النجاح؟",
         "الأرقام في أعلى الصفحة حيّة من سجلّ النظام وتتغيّر كل دقيقة — لا رقم ثابت نكتبه. والنتائج السابقة لا تضمن المستقبل."],
        ["كيف أدفع؟",
         "بالـUSDT. شهر بمئة دولار، أو ثلاثة أشهر بمئتين وسبعين."],
        ["ماذا لو خسرت؟",
         "إن كانت نتيجتك سلبية خلال أول ١٤ يوماً مع تشغيل النظام كما هو ودون تدخّل يدوي، نُرجع اشتراكك. التفاصيل في صفحة الاسترداد."],
      ]
    : [
        ["Do you need my money?",
         "No. Your capital stays in your own exchange account. We execute on it with a trade-only key that cannot withdraw."],
        ["How much do I need to start?",
         "Depends on your exchange, but $15-20 in your futures wallet covers a first test trade. You set the size per trade."],
        ["Do I need trading experience?",
         "No. The system opens, manages and closes. Still, understand the risk before scaling up — trading wins and loses."],
        ["Do I need a server or software?",
         "Nothing. Everything runs on our servers; you watch from your phone or browser."],
        ["How do I stop it?",
         "One switch pauses auto-trading instantly, another unlinks the exchange. No lock-in, no waiting period."],
        ["What's the win rate?",
         "The numbers at the top are live from the system log and change every minute — no fixed figure we type in. Past results don't guarantee future ones."],
        ["How do I pay?",
         "In USDT. $100 for a month, or $270 for three months."],
        ["What if I lose?",
         "If your net result is negative in the first 14 days while running the system as intended without manual interference, we refund your subscription. Details on the refund page."],
      ];

  return (
    <section style={{ padding: "10px 20px 30px", background: T.bg }}>
      <h2 style={{
        fontSize: 21, fontWeight: 800, color: T.txt,
        textAlign: "center", margin: "0 0 20px",
      }}>
        {ar ? "أسئلة يسألها الجميع" : "Questions everyone asks"}
      </h2>

      <div style={{ maxWidth: 420, margin: "0 auto" }}>
        {qs.map(([q, a], i) => (
          <div key={i} style={{
            background: T.card, border: `1px solid ${T.border}`,
            borderRadius: 13, marginBottom: 8, overflow: "hidden",
          }}>
            <button
              onClick={() => setOpen(open === i ? null : i)}
              style={{
                width: "100%", display: "flex", alignItems: "center", gap: 10,
                padding: "14px 15px", background: "transparent", border: "none",
                cursor: "pointer", textAlign: "start",
              }}
            >
              <span style={{
                flex: 1, fontSize: 13, fontWeight: 700, color: T.txt,
              }}>{q}</span>
              <Plus size={16} style={{
                color: T.brand, flexShrink: 0,
                transform: open === i ? "rotate(45deg)" : "none",
                transition: "transform .2s",
              }} />
            </button>
            {open === i && (
              <div style={{
                padding: "0 15px 14px", fontSize: 12.5,
                color: T.txt2, lineHeight: 1.85,
              }}>{a}</div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
