import { useEffect, useState } from "react";
import { T } from "./sections.js";

/**
 * ② الأرقام — تُجلب من قاعدتنا لا تُكتب يدوياً.
 * المنافس يكتب "74% موثّقة". نحن نعرض ما تقوله قاعدة البيانات.
 */
export default function LiveStats({ lang = "ar" }) {
  const ar = lang !== "en";
  const [s, setS] = useState(null);

  useEffect(() => {
    fetch("/api/public/stats")
      .then((r) => r.json())
      .then(setS)
      .catch(() => {});
  }, []);

  if (!s) return null;

  const cells = [
    {
      v: `${s.net_month >= 0 ? "+" : ""}${s.net_month}%`,
      l: ar ? "صافي هذا الشهر" : "Net this month",
      c: s.net_month >= 0 ? T.brand2 : T.red,
    },
    {
      v: String(s.trades_month),
      l: ar ? "صفقة منفّذة" : "Trades executed",
      c: T.txt,
    },
    {
      v: String(s.coins),
      l: ar ? "عملة تُراقَب" : "Coins watched",
      c: T.txt,
    },
    {
      v: String(s.exchanges),
      l: ar ? "منصّات" : "Exchanges",
      c: T.brand,
    },
  ];

  return (
    <section style={{ padding: "0 20px 34px", background: T.bg }}>
      <div style={{
        maxWidth: 420, margin: "0 auto",
        display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10,
      }}>
        {cells.map((x, i) => (
          <div key={i} style={{
            background: T.card, border: `1px solid ${T.border}`,
            borderRadius: 14, padding: "16px 12px", textAlign: "center",
          }}>
            <div style={{
              fontSize: 25, fontWeight: 900, color: x.c,
              letterSpacing: -.5, marginBottom: 4, direction: "ltr",
            }}>{x.v}</div>
            <div style={{ fontSize: 10.5, color: T.txt3, fontWeight: 600 }}>
              {x.l}
            </div>
          </div>
        ))}
      </div>

      <p style={{
        textAlign: "center", fontSize: 10.5, color: T.txt3,
        marginTop: 12, lineHeight: 1.7,
      }}>
        {ar
          ? "أرقام مباشرة من سجلّ النظام · تتحدّث كل دقيقة"
          : "Live from the system log · refreshed every minute"}
      </p>
    </section>
  );
}
