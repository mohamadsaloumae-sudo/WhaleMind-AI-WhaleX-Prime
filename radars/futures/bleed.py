"""📉 كاشف النزيف والركود — البُعد المفقود في مدير الصفقات.

مقيس (15 صفقة خسرت 8%+ كلّها sl_hit وصفر خروج تكتيكي):
  MNTUSDT LONG من شموع المنصّة نفسها:
    0→240د : بين +0.1% و +1.2%  ركود أربع ساعات
    240→280د: -2.5% ثم -4.5%     بداية النزيف
    628د   : -10.1% ضرب الوقف
والسبب: شرط الخروج التكتيكي الوحيد هو انقلاب دفتر الأوامر، وفي
النزيف البطيء يبقى الدفتر متوازناً بينما السعر ينزلق.
"""
import logging
log = logging.getLogger("bleed")

BLEED_MIN_TRAVEL = 0.45
BLEED_MIN_ADVERSE = 5
BLEED_MAX_PEAK = 3.0
BLEED_MIN_AGE_MIN = 20
STALE_HOURS = 3.0
STALE_BAND = 2.0
STALE_MAX_PEAK = 3.0


def travel_to_sl(pnl, sl_pnl):
    if sl_pnl >= 0 or pnl >= 0:
        return 0.0
    return min(1.0, pnl / sl_pnl)


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
    """بنية متدهورة — تميّز الانحدار الحقيقيّ عن التذبذب."""
    if len(closes) < 12:
        return False
    a, b, c = closes[-12:-8], closes[-8:-4], closes[-4:]
    if is_long:
        return max(c) < max(b) < max(a) or (max(c) < max(b) and min(c) < min(b))
    return min(c) > min(b) > min(a) or (min(c) > min(b) and max(c) > max(b))


def bleed_exit(pnl, sl_pnl, peak_pnl, age_min, closes, is_long):
    """أربعة شروط معاً حتى لا نخرج على تذبذب ولا نقتل رابحة تصحّح."""
    if age_min < BLEED_MIN_AGE_MIN:
        return False, ""
    if peak_pnl > BLEED_MAX_PEAK:
        return False, ""
    tr = travel_to_sl(pnl, sl_pnl)
    if tr < BLEED_MIN_TRAVEL:
        return False, ""
    adv = adverse_streak(closes, is_long)
    if adv < BLEED_MIN_ADVERSE:
        return False, ""
    if not lower_structure(closes, is_long):
        return False, ""
    return True, (f"📉 نزيف: قطعت {tr*100:.0f}% نحو الوقف · "
                  f"{adv}/8 شمعات ضدّنا · بنية متدهورة")


def stale_exit(pnl, peak_pnl, age_min):
    """⏱ ركود — رأس مال محجوز بلا عمل."""
    if age_min < STALE_HOURS * 60:
        return False, ""
    if abs(pnl) >= STALE_BAND or peak_pnl >= STALE_MAX_PEAK:
        return False, ""
    return True, f"⏱ ركود {age_min/60:.1f}س بلا حركة ({pnl:+.1f}%)"


def evaluate_exit(pnl, sl_pnl, peak_pnl, age_min, closes, is_long):
    hit, why = bleed_exit(pnl, sl_pnl, peak_pnl, age_min, closes, is_long)
    if hit:
        return True, why
    return stale_exit(pnl, peak_pnl, age_min)
