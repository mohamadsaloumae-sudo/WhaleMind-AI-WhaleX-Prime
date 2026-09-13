/* 📊 مصدر الاحصاء الوحيد — SWR (stale-while-revalidate).
 *
 * المشكلة: كل شاشة كانت تبني استدعاءها وتحسب بنفسها، فتختلف
 * الارقام بين الرئيسية (+25.5%) والصفقات (+20.2%) لنفس اليوم.
 * ومجموع النسب لا يساوي المال اصلا.
 *
 * SWR تُعيد المخزّن فورا وتتحقق خلفيا، وتُلغي الطلبات المتزامنة
 * المكرّرة تلقائيا — فثلاث شاشات تطلب نفس المفتاح = طلب واحد.
 * وهي ما تُشغّل لوحات Vercel نفسها (اختير 13 سبتمبر بعد بحث).
 */
import useSWR from "swr";

const tk = () => localStorage.getItem("whalex_token") || "";

const fetcher = (url) =>
  fetch(url, { headers: tk() ? { Authorization: "Bearer " + tk() } : {} })
    .then((r) => (r.ok ? r.json() : null));

const OPTS = {
  refreshInterval: 15000,      // تحديث دوري
  revalidateOnFocus: true,     // عند عودة المستخدم للتطبيق
  revalidateOnReconnect: true, // عند عودة الشبكة
  dedupingInterval: 3000,      // لا طلبين متطابقين خلال 3 ثوان
  keepPreviousData: true,      // لا وميض عند تبديل السوق
  revalidateIfStale: true,
};

/** 🪝 احصاء موحّد — اليوم · امس · اسبوع · شهر */
export function useStats(market = "futures") {
  const { data, error, isLoading } = useSWR(
    "/api/stats/summary?market=" + market, fetcher, OPTS);
  return {
    all: data || {},
    today: (data && data.today) || {},
    yesterday: (data && data.yesterday) || {},
    week: (data && data.week) || {},
    month: (data && data.month) || {},
    capital: (data && data.capital) || 0,
    loading: isLoading && !data,
    error,
  };
}

/** 🪝 اي مسار آخر بنفس السلوك */
export function useApi(path, opts) {
  return useSWR(path, fetcher, { ...OPTS, ...(opts || {}) });
}

export const fmtUsd = (n) =>
  (n === null || n === undefined) ? "—"
    : (Number(n) > 0 ? "+" : "") + Number(n).toFixed(2) + "$";

export const fmtPct = (n) =>
  (n === null || n === undefined) ? "—"
    : (Number(n) > 0 ? "+" : "") + Number(n).toFixed(2) + "%";
