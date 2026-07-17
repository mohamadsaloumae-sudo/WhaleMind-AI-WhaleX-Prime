// ترجمة أسماء الاستراتيجيات (تُحفظ عربية في القاعدة)
const EXACT = {
  "اختلال_شراء_قرب_السعر": "Buy imbalance near price",
  "اختلال_قرب_السعر": "Imbalance near price",
  "تآكل_البائعين": "Seller erosion",
  "تآكل_المشترين": "Buyer erosion",
  "جدار_بيع_ضخم": "Huge sell wall",
  "جدار_شراء_ضخم": "Huge buy wall",
  "ضغط_بيع_عام": "Broad sell pressure",
  "ضغط_شراء_عام": "Broad buy pressure",
  "جبل_ثلجي": "Iceberg",
  "BB Upper — قمة قصوى": "BB Upper — extreme top",
  "BB Upper — قمة محلية": "BB Upper — local top",
  "RSI ارتداد": "RSI rebound",
  "Stoch RSI صاعد من القاع": "Stoch RSI rising from bottom",
  "Stoch RSI هابط من القمة": "Stoch RSI falling from top",
  "ارتداد من منطقة دعم": "Rebound from support zone",
  "قاع النطاق + RSI منخفض": "Range bottom + low RSI",
  "قمة النطاق + RSI مرتفع": "Range top + high RSI",
};
const PATTERNS = [
  [/^RSI مرتفع \(([\d.]+)\) — ارتداد ناضج$/, (m) => `High RSI (${m[1]}) — mature rebound`],
  [/^💥 قمة انفجار \(([^)]+)\)$/, (m) => `💥 Explosion peak (${m[1]})`],
  [/^📊 ضغط بيع OB \(([-\d.]+)\)$/, (m) => `📊 OB sell pressure (${m[1]})`],
  [/^📍 قمة ارتداد \(([^)]+)\)$/, (m) => `📍 Rebound peak (${m[1]})`],
];
export function trStrat(s, lang) {
  if (lang === "ar" || !s) return s;
  const k = s.trim();
  if (EXACT[k]) return EXACT[k];
  for (const [re, fn] of PATTERNS) {
    const m = k.match(re);
    if (m) return fn(m);
  }
  return s; // إنجليزي أصلاً أو غير معروف
}
