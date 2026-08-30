"""🎯 بوّابة الجودة للسبوت — جودة لا كثرة.

المشكلة المقيسة: 325 صفقة بفوز 29.8% واللازم للتعادل 36.9%، فالتوقّع
-0.277% لكل صفقة. ونسبة العائد للمخاطرة ممتازة (1.71:1) — أي الخروج
سليم والعطل في الدخول: سبعون بالمئة تفشل من البداية.

والقياس على 222 صفقة pullback وجد إشارتين تُميّزان:
  عمق التصحيح: رابحة 7.40% · خاسرة 5.60%
    <4%   فوز 28% | -4.7%      4-6%  فوز 15% | -17.7%
    6-9%  فوز 33% | +11.6%     9%+   فوز 44% | +23.8%
  تأكيد الحجم: مذكور فوز 31% (+21.9) · غائب فوز 26% (-11.3)

والتركيبة (تصحيح 6%+ مع حجم مؤكَّد):
  55 صفقة من 222 | فوز 43% | +33.6%   مقابل الكلّ 28% | +10.5%

واختبار نصف/نصف يُثبت الاستقرار:
  النصف الأول: 30% → 47%   |   النصف الثاني: 27% → 38%
  والنصف الثاني كان خاسراً (-11.5%) فصار رابحاً (+5.0%).
"""
import logging
import os
import re

log = logging.getLogger("spot_quality")

# 📏 عتبة 8% — مقيسة على 153 مساراً حقيقياً بشموع خمس دقائق:
#   الصفقة التي بلغت +3% متوسط تصحيحها 7.6%، والميّتة 4.3%.
#   والصافي حسب العتبة: 6%→-0.1 · 7%→+2.2 · 8%→+3.9 · 9%→+6.0
#   واختبار النصفين يتحسّن في كليهما عند الرفع من 6 إلى 8:
#     النصف الأول +11.0 و الثاني -11.0 → +6.7 و -2.8
#   والسبب: 67% من الصفقات لا تصعد 3% أبداً — فالدخول الضحل
#   يعني أن الحركة انتهت قبل أن ندخل.
MIN_PULLBACK = 8.0
MIN_PULLBACK_BIG = 3.0     # للعملات الكبيرة — حركتها أبطأ بطبيعتها
BIG_VOL = 50_000_000       # حجم 24 ساعة يجعلها "كبيرة"
NEED_VOLUME = True
OFF_FLAG = "/opt/whalex/db/spot_quality.off"
UNIVERSE_DB = "/opt/whalex/spot_universe.db"

_VOL_CACHE: dict = {}
_VOL_TS = [0.0]


def _volumes() -> dict:
    """أحجام الكون — كاش خمس دقائق."""
    import sqlite3
    import time as _t
    if _t.time() - _VOL_TS[0] < 300 and _VOL_CACHE:
        return _VOL_CACHE
    try:
        c = sqlite3.connect(UNIVERSE_DB)
        _VOL_CACHE.clear()
        for sym, vol in c.execute("SELECT symbol, volume_24h FROM spot_universe"):
            _VOL_CACHE[sym] = float(vol or 0)
        c.close()
        _VOL_TS[0] = _t.time()
    except Exception as e:
        log.debug("أحجام الكون: %s", e)
    return _VOL_CACHE


_VOL_CACHE_P: dict = {}
_VOL_P_TS = [0.0]
PROFILES_DB = "/opt/whalex/coin_profiles.db"


def _is_volatile(symbol: str) -> bool:
    """عملة صنّفها ملفّ الفيوتشر غير آمنة — وهي الأربح في السبوت."""
    import sqlite3
    import time as _t
    if not symbol:
        return False
    if _t.time() - _VOL_P_TS[0] > 900 or not _VOL_CACHE_P:
        try:
            c = sqlite3.connect(PROFILES_DB)
            _VOL_CACHE_P.clear()
            for sym, safe in c.execute(
                    "SELECT symbol, safe_to_trade FROM coin_profiles"):
                _VOL_CACHE_P[sym] = (safe == 0)
            c.close()
            _VOL_P_TS[0] = _t.time()
        except Exception as e:
            log.debug("ملفّات العملات: %s", e)
    return bool(_VOL_CACHE_P.get(symbol))


def is_big(symbol: str) -> bool:
    return _volumes().get(symbol, 0) >= BIG_VOL


def enabled() -> bool:
    return not os.path.exists(OFF_FLAG)


def _num(text: str, pattern: str):
    m = re.search(pattern, str(text or ""))
    return float(m.group(1)) if m else None


def check(strategies: str, path: str = "", symbol: str = "") -> tuple:
    """هل تستحقّ الفتح؟ يُعيد (نعم/لا، السبب)."""
    if not enabled():
        return True, "البوّابة مُطفأة"
    s = str(strategies or "")
    if path and path != "pullback":
        return True, "مسار آخر"

    # 🐋 العملات الكبيرة عتبتها أدنى — مقيس: وسيط تصحيحها 3.3%
    #    مقابل 5.5% للباقي، فعتبة 6% تستبعدها بحكم بطء حركتها لا
    #    بحكم جودتها. والتصحيح 3% في BTC يعادل 6% في عملة صغيرة.
    big = is_big(symbol) if symbol else False
    need = MIN_PULLBACK_BIG if big else MIN_PULLBACK

    depth = _num(s, r"تصحيح\s*([0-9.]+)")
    if depth is None:
        return False, "بلا عمق تصحيح"
    if depth < need:
        return False, (f"تصحيح ضحل {depth:.1f}% "
                       f"(الحدّ {need}%{' — عملة كبيرة' if big else ''})")

    # 📊 تأكيد الحجم أو عملة متقلّبة — أيّهما كفى.
    #    اكتشاف مقيس: ملفّات العملات بُنيت للفيوتشر، حيث التلاعب
    #    والتقلّب يقتلان المركز المرفوع. وفي السبوت — بلا رافعة ولا
    #    تصفية — التقلّب حركة أوسع وربح أكبر.
    #      آمنة للفيوتشر  : 163 صفقة | فوز 26% | -20.1%
    #      غير آمنة       :  73 صفقة | فوز 41% | +29.0%
    #    وبعد تثبيت عمق التصحيح والاختبار على نصفين، الفرق ثابت.
    #    والتركيبة (عمق 6%+ ومعها حجم أو تقلّب): 64 صفقة | فوز 43%
    #    | +39.4% — أفضل من اشتراط الحجم وحده (55 صفقة | +33.6%).
    if NEED_VOLUME:
        vol = _num(s, r"حجم\s*[x×]\s*([0-9.]+)")
        if vol is None and not _is_volatile(symbol):
            return False, "بلا تأكيد حجم ولا تقلّب"

    _tag = "حجم مؤكَّد" if _num(s, r"حجم\s*[x×]\s*([0-9.]+)") else "عملة متقلّبة"
    return True, (f"تصحيح {depth:.1f}% · {_tag}"
                  + (" · عملة كبيرة" if big else ""))
