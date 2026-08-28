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

MIN_PULLBACK = 6.0
NEED_VOLUME = True
OFF_FLAG = "/opt/whalex/db/spot_quality.off"


def enabled() -> bool:
    return not os.path.exists(OFF_FLAG)


def _num(text: str, pattern: str):
    m = re.search(pattern, str(text or ""))
    return float(m.group(1)) if m else None


def check(strategies: str, path: str = "") -> tuple:
    """هل تستحقّ الفتح؟ يُعيد (نعم/لا، السبب)."""
    if not enabled():
        return True, "البوّابة مُطفأة"
    s = str(strategies or "")
    if path and path != "pullback":
        return True, "مسار آخر"

    depth = _num(s, r"تصحيح\s*([0-9.]+)")
    if depth is None:
        return False, "بلا عمق تصحيح"
    if depth < MIN_PULLBACK:
        return False, f"تصحيح ضحل {depth:.1f}% (الحدّ {MIN_PULLBACK}%)"

    if NEED_VOLUME:
        vol = _num(s, r"حجم\s*[x×]\s*([0-9.]+)")
        if vol is None:
            return False, "بلا تأكيد حجم"

    return True, f"تصحيح {depth:.1f}% · حجم مؤكَّد"
