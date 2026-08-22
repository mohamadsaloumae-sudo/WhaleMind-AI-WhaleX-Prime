import { Zap, Coins, Rocket } from "lucide-react";
import { T } from "./sections.js";

/** ⑤ ثلاثة أسواق — الفيوتشر والسبوت والميم في نظام واحد. */
export default function Markets({ lang = "ar" }) {
  const ar = lang !== "en";
  const items = ar
    ? [
        [Zap, "العقود الآجلة", "رافعة محسوبة وثلاثة أهداف ووقف واضح. أكثر من ٦٥٠ عملة على سبع منصّات — بما فيها الحصرية التي لا توجد على باينانس.", T.brand],
        [Coins, "السبوت", "شراء وبيع بلا رافعة ولا تصفية. نصطاد القيعان بعد الهبوط العنيف، ونخرج عند التعافي.", T.gold],
        [Rocket, "الميم كوينز", "رصد لحظي للإدراجات الجديدة على سولانا. ندخل مبكّراً ونخرج قبل الانهيار.", "#a78bfa"],
      ]
    : [
        [Zap, "Futures", "Measured leverage, three targets, a clear stop. 650+ coins across seven exchanges — including exclusives you won't find on Binance.", T.brand],
        [Coins, "Spot", "Buy and sell with no leverage and no liquidation. We catch bottoms after sharp drops and exit on recovery.", T.gold],
        [Rocket, "Meme coins", "Real-time detection of new Solana launches. We enter early and exit before the collapse.", "#a78bfa"],
      ];

  return (
    <section style={{ padding: "10px 20px 36px", background: T.bg }}>
      <h2 style={{
        fontSize: 21, fontWeight: 800, color: T.txt,
        textAlign: "center", margin: "0 0 6px",
      }}>
        {ar ? "ثلاثة أسواق · نظام واحد" : "Three markets · one system"}
      </h2>
      <p style={{
        fontSize: 12.5, color: T.txt2, textAlign: "center",
        margin: "0 auto 20px", maxWidth: 380, lineHeight: 1.75,
      }}>
        {ar
          ? "لا يقتصر على العقود الآجلة. كل سوق له راداره وقواعده وإدارته."
          : "Not just futures. Each market has its own radar, rules and management."}
      </p>

      <div style={{
        maxWidth: 420, margin: "0 auto",
        display: "flex", flexDirection: "column", gap: 11,
      }}>
        {items.map(([Icon, title, desc, col], i) => (
          <div key={i} style={{
            display: "flex", gap: 13, alignItems: "flex-start",
            background: T.card, border: `1px solid ${T.border}`,
            borderRadius: 15, padding: "15px 15px",
          }}>
            <div style={{
              flexShrink: 0, width: 38, height: 38, borderRadius: 11,
              display: "flex", alignItems: "center", justifyContent: "center",
              background: `${col}18`, border: `1px solid ${col}44`,
            }}>
              <Icon size={18} style={{ color: col }} />
            </div>
            <div>
              <div style={{ fontSize: 14.5, fontWeight: 800, color: T.txt, marginBottom: 4 }}>
                {title}
              </div>
              <div style={{ fontSize: 12.5, color: T.txt2, lineHeight: 1.75 }}>
                {desc}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
