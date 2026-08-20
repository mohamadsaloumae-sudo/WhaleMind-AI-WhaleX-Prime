import { T } from "./sections.js";

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
        {LIST.map(([name, id]) => (
          <div key={id} style={{
            background: T.card, border: `1px solid ${T.border}`,
            borderRadius: 13, padding: "13px 6px", textAlign: "center",
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
          </div>
        ))}
        <div style={{
          background: "rgba(45,212,191,.07)", border: `1px solid ${T.brand}33`,
          borderRadius: 13, padding: "13px 6px", textAlign: "center",
          display: "flex", flexDirection: "column", justifyContent: "center",
        }}>
          <div style={{ fontSize: 17, fontWeight: 900, color: T.brand }}>659</div>
          <div style={{ fontSize: 8.5, color: T.txt3, fontWeight: 600 }}>
            {ar ? "عملة" : "coins"}
          </div>
        </div>
      </div>
    </section>
  );
}
