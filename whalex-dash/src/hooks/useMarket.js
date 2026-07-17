// سوق الواجهة الحالي: futures | spot — معزول بالكامل، التبديل يعيد التحميل
export const getMarket = () => localStorage.getItem("wx_market") || "futures";
export const setMarket = (m) => { localStorage.setItem("wx_market", m); location.reload(); };
