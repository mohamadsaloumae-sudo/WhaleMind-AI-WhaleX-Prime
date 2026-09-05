/**
 * 🔗 روابط التسجيل في المنصّات.
 * الشعار في قسم المنصّات يفتحها مباشرةً — بلا نصّ إضافيّ.
 */
export const REFS = {
  binance: "https://www.binance.com/activity/referral-entry/CPA?ref=CPA_00BOJIUJA6",
  bybit: "https://www.bybit.com/invite",
  mexc: "https://www.mexc.com/register",
  bingx: "https://bingx.com/invite",
  bitget: "https://www.bitget.com/referral",
  gate: "https://www.gate.io/signup",
  okx: "https://www.okx.com/join",
};

export const refOf = (id) => {
  const k = String(id || "").toLowerCase().replace(".io", "").replace(/\s+/g, "");
  return REFS[k] || null;
};
