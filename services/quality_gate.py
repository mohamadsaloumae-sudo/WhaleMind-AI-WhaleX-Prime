"""🎯 بوّابة الجودة — الشورت وحده، بضغط دفتر موجب وتدفّق غير صاعد.

مقيس 15 سبتمبر على 1024 صفقة شورت (21 يوماً):
  الكل      1024 صفقة · +0.01%
  التركيبة   254 صفقة · +1.48% · فوز 61%
  الباقي     770 صفقة · -0.47%

واختبار خارج التدريب (آخر 7 ايام لم تدخل القياس):
  الكل 95 صفقة +1.73% · التركيبة 34 صفقة +2.30%

البيانات الناقصة لا تمنع — لا نعاقب اشارة لم نقس سياقها.
الاطفاء: touch /opt/whalex/db/quality_gate.off
"""
import os

OFF = "/opt/whalex/db/quality_gate.off"
OB_MIN = 0.02
OK_CVD = ("flat", "down")


def gate(direction, ob, cvd):
    """يُعيد (يُسمح، السبب)."""
    if os.path.exists(OFF):
        return True, ""
    if str(direction or "").upper() != "SHORT":
        return True, ""
    try:
        o = float(ob) if ob is not None else None
    except Exception:
        o = None
    c = str(cvd or "").lower()
    if o is None or c == "":
        return True, ""
    if o <= OB_MIN:
        return False, "ضغط الدفتر %.3f دون %.2f" % (o, OB_MIN)
    if c not in OK_CVD:
        return False, "تدفّق %s صاعد" % c
    return True, ""
