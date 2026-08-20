import { useTier } from "../context/TierContext.jsx";

/**
 * 🔒 يُخفي التفاصيل عن المجرّب ويُظهرها للمشترك.
 *
 *   <Masked value={p.symbol} />         → ●●●●●● للمجرّب
 *   <Masked value={p.entry} chars={5} />
 *
 * الاستثناء: mine=true للصفقات المنفَّذة على حسابه — تلك ماله ويراها.
 */
export default function Masked({ value, chars = 0, mine = false, style }) {
  const { paid, trial } = useTier();
  if (paid || mine || !trial) return <span style={style}>{value}</span>;

  const n = chars || Math.min(8, String(value ?? "").length || 5);
  return (
    <span
      style={{ ...style, letterSpacing: 1.5, opacity: .55, userSelect: "none" }}
      title="اشترك لعرض التفاصيل"
    >
      {"•".repeat(n)}
    </span>
  );
}
