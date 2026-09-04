"""📐 مرشّح المعايير العالمية — معكوساً كما قاسه سجلّنا.

الكتاب يقول: اشترِ حين يُشبَع البيع فالسعر يعود لمتوسّطه.
وسجلّنا يقول العكس في الألتكوين — فالمُشبَع بيعاً يستمرّ في الموت:

  z-score < -1.5        19 إشارة | فوز 26% | -0.644%/صفقة
  بولنجر تحت السفليّ    16       | فوز 25% | -0.674%
  RSI-2 < 10            36       | فوز 25% | -0.624%
  RSI-14 < 30           17       | فوز 23% | -0.659%

  وفي المقابل:
  RSI-14 > 60           77       | فوز 51% | +0.094%  ← الوحيد الموجب
  بولنجر > 0.6         109       | فوز 50%

ومنطقنا الحاليّ يُعطي أعلى نقاطه (2.2) لشريحة RSI 30-55 الخاسرة.

والأثر المقيس على 199 إشارة بشموع تنتهي عند لحظة الدخول (بلا نظر
للمستقبل): -31.3% → +7.1% وفوز 43% → 51%، وموجب في النصفين
(+14 و +25).
"""
import logging
import math
import os

log = logging.getLogger("spot_std")

Z_MIN = -0.75          # أدنى z-score مقبول
BB_MIN = 0.30          # أدنى موقع بين حزامي بولنجر
RSI2_MIN = 10.0        # أدنى RSI فترة 2
RSI14_MIN = 45.0       # أدنى RSI فترة 14
OFF_FLAG = "/opt/whalex/db/spot_std.off"


def zscore(closes, n=20):
    if len(closes) < n: return None
    w = closes[-n:]; m = sum(w) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in w) / n)
    return (closes[-1] - m) / sd if sd > 0 else None


def bb_position(closes, n=20, k=2.0):
    """0 = الحزام السفليّ · 1 = العلويّ."""
    if len(closes) < n: return None
    w = closes[-n:]; m = sum(w) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in w) / n)
    if sd == 0: return None
    return (closes[-1] - (m - k * sd)) / (2 * k * sd)


def rsi_n(closes, period=14):
    if len(closes) < period + 1: return None
    g = l = 0.0
    for i in range(-period, 0):
        d = closes[i] - closes[i - 1]
        g += d if d > 0 else 0.0
        l += -d if d < 0 else 0.0
    if l == 0: return 100.0
    return 100 - 100 / (1 + (g / period) / (l / period))


def check(closes) -> tuple:
    """يُعيد (نقبل؟، السبب). وأي نقص بيانات يُمرّر."""
    if os.path.exists(OFF_FLAG):
        return True, ""
    try:
        z = zscore(closes)
        if z is not None and z < Z_MIN:
            return False, f"z-score {z:.2f} دون {Z_MIN} — مُشبَع بيعاً"
        bb = bb_position(closes)
        if bb is not None and bb < BB_MIN:
            return False, f"بولنجر {bb:.2f} دون {BB_MIN} — قرب الحزام السفليّ"
        r2 = rsi_n(closes, 2)
        if r2 is not None and r2 < RSI2_MIN:
            return False, f"RSI-2 {r2:.0f} دون {RSI2_MIN}"
        r14 = rsi_n(closes, 14)
        if r14 is not None and r14 < RSI14_MIN:
            return False, f"RSI-14 {r14:.0f} دون {RSI14_MIN}"
    except Exception as e:
        log.debug("مرشّح المعايير: %s", e)
        return True, ""
    return True, "معايير سليمة"
