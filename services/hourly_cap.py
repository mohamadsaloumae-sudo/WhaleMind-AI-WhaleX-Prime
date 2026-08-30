"""⏱️ سقف ساعيّ للإشارات — أوّل ما يجيء، بلا انتظار.

المشكلة: النظام يفتح 21 صفقة يومياً في دفعات متلاصقة، فترتفع
رسوم المنصّة ويحتاج المشترك 22 مركزاً متزامناً، ومع مئات
المشتركين تصير مئات الأوامر في ثانية واحدة على باينانس.

والقياس على 638 صفقة في 30 يوماً (بعتبة 6.5):
  بلا سقف : +0.142%/صفقة | الشهر  +90.4% | تزامن 22
  سقف 5   : +0.171%       | الشهر +102.2% | تزامن 15
  سقف 3   : +0.235%       | الشهر +129.0% | تزامن 12  ✅
  سقف 2   : +0.279%       | الشهر +131.7% | تزامن  9

فاخترنا 3: موجب ومستقرّ في النصفين (+0.297 و +0.181)،
ويخفض رأس المال المطلوب 45% ويرفع الربح 43%.

ولا انتظار: أوّل ثلاث إشارات قوية في الساعة تُفتَح فوراً،
والرابعة تُؤجَّل للساعة التالية.
"""
import logging
import os
import time

log = logging.getLogger("hourly_cap")

CAP_PER_HOUR = 3
OFF_FLAG = "/opt/whalex/db/hourly_cap.off"

_used = {}          # الساعة → العدد
_stats = {"taken": 0, "capped": 0}


def allow(symbol: str = "") -> tuple:
    """هل نسمح بهذه الإشارة؟ يُعيد (نعم/لا، السبب)."""
    if os.path.exists(OFF_FLAG):
        return True, ""
    h = int(time.time()) // 3600
    # ننظّف الساعات القديمة
    for k in [k for k in _used if k < h - 2]:
        _used.pop(k, None)
    n = _used.get(h, 0)
    if n >= CAP_PER_HOUR:
        _stats["capped"] += 1
        return False, f"السقف الساعيّ {CAP_PER_HOUR} مكتمل ({n})"
    _used[h] = n + 1
    _stats["taken"] += 1
    return True, f"{n + 1}/{CAP_PER_HOUR} هذه الساعة"


def stats() -> dict:
    h = int(time.time()) // 3600
    return {**_stats, "this_hour": _used.get(h, 0), "cap": CAP_PER_HOUR}
