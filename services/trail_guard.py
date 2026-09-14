"""📈 وقف متحرّك — يمنع قطع الربح مبكّرا.

مقيس 14 سبتمبر على 1224 صفقة رابحة:
  التقاط الخروج التكتيكي 45% فقط من الذروة
  65% من الصفقات تُغلق وقد بقي فيها 2%+ (797 صفقة)
  14% فقط تُغلق في وقتها
  BIOUSDT اُغلق +0.02% وبلغ +24.24% · GIGGLE +0.20% وبلغ +19.20%

والاستمرار يزيد كلما ارتفع الاغلاق:
  من اُغلق عند 0-1% استمر 69% · عند 3-5% استمر 90% · فوق 5% استمر 96%
  فالانعكاس بعد 5% نادر (3%)، والخروج المبكر هو الخطر لا البقاء.

المحاكاة: تراجع 2% يعطي +3993 نقطة فوق الحالي.

القاعدة: بعد ان تبلغ الصفقة ARM_AT، لا نسمح بخروج تكتيكي الا اذا
تراجعت DROP_PCT من ذروتها. والحراس الاخرى (الوقف · النزيف · الحد
الصلب) تعمل كما هي — هذا يحكم الخروج التكتيكي وحده.

الاطفاء: touch /opt/whalex/db/trail.off
"""
import os
import logging

log = logging.getLogger("trail_guard")
OFF = "/opt/whalex/db/trail.off"

ARM_AT = 1.5      # يتسلّح بعد هذا الربح
DROP_PCT = 2.0    # يُغلق عند تراجع هذا القدر من الذروة
MIN_KEEP = 0.3    # لا نُغلق تحت هذا الربح

_STATE = {}


def allow_tactical(pos_id, pnl_pct, peak_pnl) -> tuple:
    """هل نسمح بالخروج التكتيكي؟ (نعم/لا، السبب).

    نُرجع (True, "") إن كان الخروج مسموحا — أي لم يتسلّح الوقف
    أو تراجعت الصفقة فعلا من ذروتها.
    """
    if os.path.exists(OFF):
        return True, ""
    try:
        p = float(pnl_pct or 0)
        pk = max(float(peak_pnl or 0), p)
        st = _STATE.setdefault(pos_id, {"armed": False})
        if not st["armed"] and pk >= ARM_AT:
            st["armed"] = True
        if not st["armed"]:
            return True, ""            # لم يتسلّح — الخروج مسموح
        drop = pk - p
        if drop >= DROP_PCT and p >= MIN_KEEP:
            _STATE.pop(pos_id, None)
            return True, "تراجع %.2f%% من ذروة %.2f%%" % (drop, pk)
        # مُتسلّح ولم يتراجع — نمنع الخروج ونترك الربح يجري
        return False, "ذروة %.2f%% · الآن %.2f%% (تراجع %.2f%% < %.1f%%)" % (
            pk, p, drop, DROP_PCT)
    except Exception as e:
        log.debug("allow_tactical %s: %s", pos_id, e)
        return True, ""


def clear(pos_id):
    _STATE.pop(pos_id, None)
