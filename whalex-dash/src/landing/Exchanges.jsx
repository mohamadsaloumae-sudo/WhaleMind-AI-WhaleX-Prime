import { T } from "./sections.js";
import { refOf } from "./refs.js";

const LIST = [
  ["Binance", "270"], ["Bybit", "521"], ["OKX", "294"],
  ["Bitget", "513"], ["MEXC", "544"], ["Gate.io", "302"], ["BingX", "1064"],
];

/** ⑥ المنصّات السبع — وحسابات متعدّدة معاً، وهي ميزة نادرة. */
export default function Exchanges({ lang = "ar" }) {
  const ar = lang !== "en";
  return (
    <section style={{ padding: "10px 20px 36px", background: T.bg }}>
      <h2 style={{
        fontSize: 21, fontWeight: 800, color: T.txt,
        textAlign: "center", margin: "0 0 6px",
      }}>
        {ar ? "سبع منصّات · حساباتك كلها" : "Seven exchanges · all your accounts"}
      </h2>
      <p style={{
        fontSize: 12.5, color: T.txt2, textAlign: "center",
        margin: "0 auto 20px", maxWidth: 380, lineHeight: 1.75,
      }}>
        {ar
          ? "تربط حساباً واحداً أو سبعة. كل إشارة تُنفَّذ على منصّتها — فلا تفوتك فرصة لأن عملتها ليست على باينانس."
          : "Link one account or seven. Each signal executes on its own exchange — so you never miss a setup just because the coin isn't on Binance."}
      </p>

      <div style={{
        maxWidth: 420, margin: "0 auto",
        display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 9,
      }}>
        {LIST.map(([name, id]) => {
          // 🔗 الشعار يفتح صفحة التسجيل — بلا نصّ إضافيّ يُشوّه القسم.
          const href = refOf(name);
          return (
            <a key={id} href={href || undefined}
               target={href ? "_blank" : undefined}
               rel={href ? "noopener noreferrer" : undefined}
               style={{
                 background: T.card, border: `1px solid ${T.border}`,
                 borderRadius: 13, padding: "13px 6px", textAlign: "center",
                 textDecoration: "none", display: "block",
                 cursor: href ? "pointer" : "default",
                 transition: "transform .15s, border-color .15s",
               }}
               onMouseEnter={(e) => {
                 if (!href) return;
                 e.currentTarget.style.transform = "translateY(-2px)";
                 e.currentTarget.style.borderColor = T.brand + "66";
               }}
               onMouseLeave={(e) => {
                 e.currentTarget.style.transform = "none";
                 e.currentTarget.style.borderColor = T.border;
               }}>
              <img
                src={`https://s2.coinmarketcap.com/static/img/exchanges/64x64/${id}.png`}
                alt={name} width="28" height="28"
                style={{ borderRadius: 7, marginBottom: 6 }}
                onError={(e) => { e.target.style.display = "none"; }}
              />
              <div style={{ fontSize: 9.5, color: T.txt2, fontWeight: 600 }}>
                {name}
              </div>
            </a>
          );
        })}
        {/* 🔗 ديكس سكرينر — مصدر بيانات الميم. الشعار وحده، بلا نصّ،
            والنقر يفتح موقعهم مباشرة. */}
        <a href="https://dexscreener.com" target="_blank"
           rel="noopener noreferrer" title="DexScreener"
           style={{
             background: "rgba(45,212,191,.07)",
             border: `1px solid ${T.brand}33`,
             borderRadius: 13, padding: "13px 6px", textAlign: "center",
             display: "flex", flexDirection: "column",
             alignItems: "center", justifyContent: "center",
             gap: 5, textDecoration: "none",
           }}>
          <img src="https://dexscreener.com/favicon.png" alt="DexScreener"
               width="26" height="26"
               style={{ borderRadius: 7, objectFit: "contain" }}
               onError={(e) => { e.target.style.display = "none"; }} />
          <div style={{ fontSize: 9.5, color: T.txt2, fontWeight: 600 }}>
            DexScreener
          </div>
        </a>
      </div>
    </section>
  );
}
