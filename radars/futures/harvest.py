"""🌾 حصاد الرابحة الراكدة — نأخذ الربح قبل أن يتبخّر.

القياس على 1,445 صفقة (عمرها 15 دقيقة فأكثر):
  قمّة 1-3%   → النهاية -4.17%   (تُعيد 6.13 نقطة)
  قمّة 3-6%   → النهاية -1.01%   (تُعيد 5.16)
  قمّة 6-12%  → النهاية +4.22%   (تُعيد 4.12)
  قمّة 12%+   → النهاية +12.30%  (تُعيد 5.54)

فكل شريحة تُعيد 4-6 نقاط من قمّتها. ولو حصدنا الرابحة التي بلغت +2%
ولم تتجاوز +4%: الواقع -224.0% والحصاد +312.0% (فرق 536 نقطة).

والفرق عن سلّم القفل: القفل ينتظر التراجع، والحصاد يسبقه — يقرأ
الركود ويخرج قبل أن يبدأ الهبوط.

⚠️ ولا نحصد المنفجرة: ما دامت قمّتها ترتفع فهي تعمل. والرابحة الكبيرة
   (8%+) تُمهَل ضعف المدّة لأنها تنتهي رابحة رغم تراجعها.
"""
import logging
import os
import time

log = logging.getLogger("harvest")

MIN_PROFIT = 1.0
STALL_SEC = 300
GIVEBACK_MAX = 0.35
EXPLOSIVE_RISE = 1.5
MIN_AGE_SEC = 60
MAX_PROFIT = 6.0          # ما فوقه يُترَك لسلّم القفل
BIG_WINNER = 8.0
OFF_FLAG = "/opt/whalex/db/harvest.off"

_PEAK_AT: dict = {}


def enabled() -> bool:
    return not os.path.exists(OFF_FLAG)


def note_peak(pos_id: str, peak_pnl: float, now: float = None):
    now = now or time.time()
    prev = _PEAK_AT.get(pos_id)
    if prev is None or peak_pnl > prev[0] + 0.15:
        _PEAK_AT[pos_id] = (peak_pnl, now)


def forget(pos_id: str):
    _PEAK_AT.pop(pos_id, None)


def is_explosive(pnl_now: float, pnl_2min_ago: float) -> bool:
    return (pnl_now - pnl_2min_ago) >= EXPLOSIVE_RISE


def should_harvest(pos_id: str, pnl: float, peak_pnl: float,
                   age_sec: float, pnl_2min_ago: float = None,
                   now: float = None) -> tuple:
    """هل نحصد الآن؟ يُعيد (نعم/لا، السبب)."""
    if not enabled():
        return False, ""
    now = now or time.time()
    if age_sec < MIN_AGE_SEC or pnl < MIN_PROFIT:
        return False, ""
    # 🚫 الرابحة الكبيرة لا تُحصَد — القياس على 30 مساراً حقيقياً:
    #    PENGUUSDT +14.2% صارت +4.5% وLABUSDT +8.8% صارت +1.8%.
    #    فما فوق 5% يُترَك لسلّم القفل الذي يحميه بأرضية ترتفع معه.
    if pnl > MAX_PROFIT or peak_pnl > MAX_PROFIT:
        return False, ""
    if pnl_2min_ago is not None and is_explosive(pnl, pnl_2min_ago):
        return False, ""

    note_peak(pos_id, peak_pnl, now)
    pk, at = _PEAK_AT.get(pos_id, (peak_pnl, now))

    # 🌾 التراجع المسموح يتّسع مع قوّة الحركة — كل صفقة تُقاس بذروتها هي.
    #    كان 35% ثابتاً للجميع، فيحصد الصفقة القويّة كما الضعيفة.
    #    مقيس على المسبار: 4 من 6 حالات واصل السعر لصالحنا بعد الحصاد.
    _gb = (0.35 if pk < 2.0 else 0.42 if pk < 3.0 else
           0.50 if pk < 4.0 else 0.58 if pk < 5.0 else 0.65)
    if pk > 0 and (pk - pnl) / pk >= _gb:
        return True, f"🌾 حصاد: تراجعت من {pk:+.1f}% إلى {pnl:+.1f}%"

    stalled = now - at
    limit = STALL_SEC * (2.0 if pk >= BIG_WINNER else 1.0)
    if stalled >= limit:
        return True, (f"🌾 حصاد: قمّة {pk:+.1f}% ثابتة {stalled/60:.0f}د "
                      f"· الربح {pnl:+.1f}%")
    return False, ""
