/**
 * 🔗 روابط التسجيل في المنصّات.
 * الشعار في قسم المنصّات يفتحها مباشرةً — بلا نصّ إضافيّ.
 */
export const REFS = {
  binance: "https://www.binance.com/activity/referral-entry/CPA?ref=CPA_00BOJIUJA6",
  bybit: "https://www.bybit.com/invite?ref=QDWX77P&medium=referral&utm_campaign=evergreen&share_to=post",
  mexc: "https://s.mexc.com/referral/rVuAM1ZWMc",
  bingx: "https://bingx.com/invite",
  bitget: "https://share.bitget.com/u/MWQNB0PK?clacCode=8YRUD3XM",
  gate: "https://www.gate.io/signup",
  okx: "https://www.okx.com/join",
};

export const refOf = (id) => {
  const k = String(id || "").toLowerCase().replace(".io", "").replace(/\s+/g, "");
  return REFS[k] || null;
};
