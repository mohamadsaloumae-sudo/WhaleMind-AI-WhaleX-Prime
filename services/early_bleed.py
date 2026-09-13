"""🩸 حارس النزيف المبكّر — يشمل كل الرادارات.

مقيس 12 سبتمبر على 897 صفقة فيها mae مسجّل:
  الصفقة التي تتراجع 1.5% في اول 3 دقائق:
    عددها 96 (10% من الكل) · تفوز 6% فقط
    تخسر فعليا -523 نقطة
    لو أُغلقت فورا -144 ⇒ التوفير +379

  نقتل 6 رابحات (+28) وننقذ 90 خاسرة (-551).
  النسبة 15 الى 1.

والسبب البنيوي: الصفقة المنهارة تبلغ ذروتها في 2.7 دقيقة ثم تنهار،
والرابحة تصعد 28.3 دقيقة. فالنافذة الاولى تفصلهما.

الاطفاء: touch /opt/whalex/db/early_bleed.off
"""
import os
import time
import logging

log = logging.getLogger("early_bleed")

WINDOW_SEC = 180.0      # نافذة المراقبة من الفتح
MAE_PCT = -1.5          # التراجع من الذروة الذي يُغلق

# 🆕 الحد المطلق — مقيس 12 سبتمبر على 942 صفقة:
#    الصفقة التي تخسر 2% ولم ترتفع 1% ابدا تفوز 5% فقط.
#    عددها 180 (19%) · تخسر -929 · لو أُغلقت -360 ⇒ توفير +569.
#    والسبب: خسائر امس الست كلها MFE=0 — تنهار من الثانية الاولى
#    فلا ذروة تتراجع عنها، وحارس النزيف لا يمسكها.
HARD_PCT = -2.0         # الخسارة المطلقة
# 📊 مقيس على 942 صفقة — التوفير حسب العتبة:
#    <1.0% : n=180 فوز 5% · +569
#    <2.0% : n=224 فوز 7% · +675  ← المختارة
#    <3.0% : n=249 فوز 8% · +763 (تقتل رابحات اكثر)
#    و GRIFFAIN امس ارتفعت 1.85% فأُعفيت ثم انهارت -7.85%.
PEAK_MIN = 2.0          # من ارتفع هذا القدر يُعفى من الحد المطلق
OFF = "/opt/whalex/db/early_bleed.off"

_STATE = {}


def check(pos_id, opened_at, pnl_pct, now=None) -> tuple:
    """(نُغلق؟، السبب). خارج النافذة يتولّاها الحارس العادي."""
    if os.path.exists(OFF):
        return False, ""
    try:
        now = now or time.time()
        age = now - float(opened_at or 0)
        if age <= 0 or age > WINDOW_SEC:
            _STATE.pop(pos_id, None)
            return False, ""
        st = _STATE.setdefault(pos_id, {"peak": pnl_pct})
        if pnl_pct > st["peak"]:
            st["peak"] = pnl_pct
        draw = pnl_pct - st["peak"]
        if draw <= MAE_PCT:
            _STATE.pop(pos_id, None)
            return True, "نزيف مبكّر %.1f%% من الذروة خلال %.0fث" % (draw, age)
        if pnl_pct <= HARD_PCT and st["peak"] < PEAK_MIN:
            _STATE.pop(pos_id, None)
            return True, ("خسارة %.1f%% بلا ارتفاع خلال %.0fث (ذروة %.1f%%)"
                          % (pnl_pct, age, st["peak"]))
    except Exception as e:
        log.debug("early_bleed: %s", e)
    return False, ""


def forget(pos_id):
    _STATE.pop(pos_id, None)
