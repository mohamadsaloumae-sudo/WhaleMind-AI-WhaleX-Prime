// 🏪 سوق الواجهة — useSyncExternalStore (React 18+).
//
// كان setMarket يستدعي location.reload() فيُعيد تحميل التطبيق كاملا
// عند كل تبديل (فيوتشر · سبوت · ميم): تهيئة React من الصفر وإعادة
// كل الاستدعاءات — 5 الى 10 ثوان.
//
// useSyncExternalStore هو الحل القياسي للمزامنة مع مخزن خارجي مثل
// localStorage، وهو ما تستعمله Zustand و Jotai داخليا. و subscribe
// و getSnapshot معرّفتان خارج المكوّن — والا صارتا جديدتين كل رسم.
//
// getMarket() للاستدعاء خارج الرسم (داخل useEffect والدوال)،
// و useMarket() للمكوّنات التي تحتاج إعادة رسم عند التبديل.
// مقيس برسم React حقيقي: useMarket يتحدث فورا و getMarket يتجمد.
import { useSyncExternalStore } from "react";

const KEY = "wx_market";
const VALID = ["futures", "spot", "meme"];
let _cur = null;
const _subs = new Set();

function _read() {
  try {
    const v = localStorage.getItem(KEY);
    return VALID.includes(v) ? v : "futures";
  } catch { return "futures"; }
}

function _subscribe(cb) {
  _subs.add(cb);
  const onStorage = (e) => {
    if (e && e.key === KEY) { _cur = _read(); _subs.forEach((f) => f()); }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    _subs.delete(cb);
    window.removeEventListener("storage", onStorage);
  };
}

function _getSnapshot() {
  if (_cur === null) _cur = _read();
  return _cur;
}

const _getServerSnapshot = () => "futures";

export const getMarket = () => _getSnapshot();

export const setMarket = (m) => {
  if (!VALID.includes(m) || m === _getSnapshot()) return;
  try { localStorage.setItem(KEY, m); } catch { /* */ }
  _cur = m;
  _subs.forEach((f) => f());
};

export function useMarket() {
  return useSyncExternalStore(_subscribe, _getSnapshot, _getServerSnapshot);
}
