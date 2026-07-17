// ترجمة أسطر الاستراتيجيات — ثنائية الاتجاه (المخزون مختلط عربي/إنجليزي)
const AR2EN = {
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
  "قاع_نطاق_صامد": "Holding range bottom",
  "تجميع_هادئ_بالقاع": "Quiet accumulation at bottom",
};
const AR2EN_P = [
  [/^RSI مضغوط \(([\d.]+)\)$/, (m) => `Compressed RSI (${m[1]})`],
  [/^RSI مرتفع \(([\d.]+)\) — ارتداد ناضج$/, (m) => `High RSI (${m[1]}) — mature rebound`],
  [/^💥 قمة انفجار \(([^)]+)\)$/, (m) => `💥 Explosion peak (${m[1]})`],
  [/^📊 ضغط بيع OB \(([-\d.]+)\)$/, (m) => `📊 OB sell pressure (${m[1]})`],
  [/^📍 قمة ارتداد \(([^)]+)\)$/, (m) => `📍 Rebound peak (${m[1]})`],
];
const EN2AR = {
  "🎯 Peak Hunter SHORT": "🎯 صائد القمم — شورت",
  "🪙 Spot Accumulation": "🪙 تجميع سبوت",
  "📈 Peak Hunter LONG": "📈 صائد القيعان — لونغ",
  "BB Upper Touch": "لمس الحد العلوي BB",
  "BB Lower Touch": "لمس الحد السفلي BB",
  "MACD Bullish": "MACD صاعد",
  "MACD Bearish": "MACD هابط",
  "FVG Bullish Zone": "منطقة FVG صاعدة",
  "FVG Bearish Zone": "منطقة FVG هابطة",
  "⚡ Imminent Explosion": "⚡ انفجار وشيك",
  "🎯 Stop Hunt LONG": "🎯 صيد وقف — لونغ",
  "🎯 Stop Hunt SHORT": "🎯 صيد وقف — شورت",
  "💥 Liquidation Cascade → LONG": "💥 شلال تصفيات → لونغ",
  "💥 Liquidation Cascade → SHORT": "💥 شلال تصفيات → شورت",
};
const EN2AR_P = [
  [/^⚡ Delta Reversal \(([^)]+)\)$/, (m) => `⚡ انعكاس دلتا (${m[1]})`],
  [/^CVD Divergence \(([^)]+)\)$/, (m) => `انحراف CVD (${m[1]})`],
  [/^📊 Volume Spike \(([^)]+)\)$/, (m) => `📊 قفزة حجم (${m[1]})`],
];
function _map(k, exact, pats) {
  if (exact[k]) return exact[k];
  for (const [re, fn] of pats) { const m = k.match(re); if (m) return fn(m); }
  return null;
}
export function trStrat(s, lang) {
  if (!s) return s;
  const k = s.trim();
  if (lang === "ar") return _map(k, EN2AR, EN2AR_P) || s;   // عربي: عرّب الإنجليزي
  return _map(k, AR2EN, AR2EN_P) || s;                       // إنجليزي: ترجم العربي
}
