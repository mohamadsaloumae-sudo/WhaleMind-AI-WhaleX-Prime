"""📉🔒 القاعدتان: قفل تدريجيّ للرابحة · خروج تكتيكي للخاسرة بلا استثناء.

مقيس على يومين (525 صفقة): 288 خرجت تكتيكياً بـ+493.7%، و35 ضربت
الوقف بـ-418.6%. والمانع الأكبر: 20 صفقة قمّتها تجاوزت 3% فاستُبعدت
من كاشف النزيف، و8 صفقات عمرها أقلّ من 20 دقيقة.

فنستبدل شرط القمّة بسلّم قفل: الرابحة تُحمى بأرضية ترتفع مع قمّتها،
والخاسرة تُفحص مهما كانت قمّتها السابقة.
"""
import logging
log = logging.getLogger("bleed")

BLEED_MIN_TRAVEL = 0.45
BLEED_MIN_ADVERSE = 5
BLEED_MIN_AGE_MIN = 3
STALE_HOURS = 3.0
STALE_BAND = 2.0

LOCK_LADDER = (
    (20.0, 12.0),
    (12.0, 7.0),
    (8.0, 4.0),
    (5.0, 2.0),
    (3.0, 0.5),
)


def lock_floor(peak_pnl: float):
    """أدنى ربح مقبول بعد بلوغ قمّة."""
    for arm, floor in LOCK_LADDER:
        if peak_pnl >= arm:
            return floor
    return None


def adverse_streak(closes, is_long):
    if len(closes) < 9:
        return 0
    n = 0
    for i in range(-8, 0):
        d = closes[i] - closes[i - 1]
        if (d < 0) if is_long else (d > 0):
            n += 1
    return n


def lower_structure(closes, is_long):
    if len(closes) < 12:
        return False
    a, b, c = closes[-12:-8], closes[-8:-4], closes[-4:]
    if is_long:
        return max(c) < max(b) < max(a) or (max(c) < max(b) and min(c) < min(b))
    return min(c) > min(b) > min(a) or (min(c) > min(b) and max(c) > max(b))


def evaluate_exit(pnl, sl_pnl, peak_pnl, age_min, closes, is_long):
    fl = lock_floor(peak_pnl)
    if fl is not None and pnl <= fl:
        return True, f"🔒 قفل: قمّة {peak_pnl:+.1f}% → أرضية {fl:+.1f}%"
    if pnl < 0 and age_min >= BLEED_MIN_AGE_MIN:
        tr = (pnl / sl_pnl) if sl_pnl < 0 else 0.0
        if tr >= BLEED_MIN_TRAVEL:
            adv = adverse_streak(closes, is_long)
            if adv >= BLEED_MIN_ADVERSE and lower_structure(closes, is_long):
                return True, (f"📉 نزيف: قطعت {tr*100:.0f}% نحو الوقف · "
                              f"{adv}/8 ضدّنا · بنية متدهورة")
    if age_min >= STALE_HOURS * 60 and abs(pnl) < STALE_BAND and peak_pnl < 3.0:
        return True, f"⏱ ركود {age_min/60:.1f}س ({pnl:+.1f}%)"
    return False, ""
