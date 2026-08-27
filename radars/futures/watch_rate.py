"""⚡ تردّد المراقبة المتكيّف — كل صفقة تُفحَص بما يناسب خطرها.

المشكلة المقيسة: 牛来USDT عاشت 3.2 دقيقة وأُغلقت -13%. والمدير يفحص
كل 10 ثوانٍ ويصمت 90 ثانية بعد الفتح، وكاشف النزيف يحتاج 8 دقائق —
فالصفقة ماتت قبل أن يراها أحد.

والقياس يقول إن الحراسة اللحظية ممكنة:
  عشر صفقات تتابعياً 32.1 ثانية · بالتوازي 0.8 ثانية (40 ضعفاً أسرع)
لكنّ دورة ثابتة 3 ثوانٍ لعشرين صفقة = 400 فحص/دقيقة (ثقيل).

فالتردّد يتبع الحالة: الوليدة والقريبة من الوقف كل 3 ثوانٍ، والساكنة
كل 15 — فنحصل على الحراسة نفسها بنصف الحمل (188 بدل 400).
"""
import logging

log = logging.getLogger("watch_rate")

FAST = 3
MEDIUM = 5
NORMAL = 10
SLOW = 15

NEWBORN_SEC = 300
DANGER_TRAVEL = 0.60
WARN_TRAVEL = 0.35
LOCK_PEAK = 6.0
IDLE_BAND = 1.5


def interval(pnl: float, sl_pnl: float, age_sec: float,
             peak_pnl: float = 0.0) -> tuple:
    """يُعيد (الثواني حتى الفحص التالي، السبب)."""
    travel = (pnl / sl_pnl) if (sl_pnl < 0 and pnl < 0) else 0.0
    if age_sec < NEWBORN_SEC:
        return FAST, f"وليدة {age_sec:.0f}ث"
    if travel >= DANGER_TRAVEL:
        return FAST, f"قطعت {travel*100:.0f}% نحو الوقف"
    if travel >= WARN_TRAVEL:
        return MEDIUM, f"قطعت {travel*100:.0f}%"
    if peak_pnl >= LOCK_PEAK:
        return MEDIUM, "رابحة تحتاج قفلاً"
    if abs(pnl) < IDLE_BAND:
        return SLOW, "ساكنة"
    return NORMAL, "عادية"
