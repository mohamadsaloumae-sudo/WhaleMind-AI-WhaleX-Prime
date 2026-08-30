"""🧮 حاسبة خطّة التداول — من أرقام النظام الحقيقية.

الثوابت مقيسة على 549 صفقة شهرياً بعد عتبة 6.5 والسقف الساعيّ 3:
  صافي حركة السعر بعد عمولة باينانس: +0.235% لكل صفقة
  التزامن الذي يغطّي 95% من الوقت: 12 مركزاً
  والحدّ الأدنى للصفقة 20$ — أقلّ منه تأكله العمولة.
"""
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/plan", tags=["plan"])

NET_PER_TRADE = 0.002350
TRADES_MONTH = 549
LEVERAGE = 5
MIN_TRADE = 20.0
SLOTS = 12
RESERVE = 0.05
SUBSCRIPTION = 100.0
MIN_CAPITAL = 300.0


@router.get("")
async def make_plan(capital: float = Query(..., ge=1, le=1_000_000)):
    if capital < MIN_CAPITAL:
        return {
            "ok": False,
            "min_capital": MIN_CAPITAL,
            "reason_ar": (
                f"رأس المال أقلّ من الحدّ الأدنى.\n\n"
                f"بـ{capital:.0f}$ سيفتح لك النظام مركزين أو ثلاثة فقط، "
                f"وتفوتك بقيّة الإشارات. والعمولة تأكل ربح الصفقة الصغيرة، "
                f"فلا يغطّي حسابك رسوم المنصّة ولا اشتراك البوت.\n\n"
                f"والحدّ الأدنى المجدي: {MIN_CAPITAL:.0f}$"),
            "reason_en": (
                f"Below the minimum. With ${capital:.0f} only 2-3 positions "
                f"would open and fees would exceed profit. "
                f"Minimum viable: ${MIN_CAPITAL:.0f}"),
        }
    usable = capital * (1 - RESERVE)
    amount = max(MIN_TRADE, round(usable / SLOTS / 5) * 5)
    slots = max(1, min(SLOTS, int(usable // amount)))
    monthly = amount * LEVERAGE * NET_PER_TRADE * TRADES_MONTH * (slots / SLOTS)
    return {
        "ok": True,
        "capital": round(capital, 2),
        "amount": round(amount, 2),
        "slots": slots,
        "leverage": LEVERAGE,
        "grades": "A,S",
        "margin_used": round(amount * slots, 2),
        "reserve": round(capital - amount * slots, 2),
        "monthly": round(monthly, 2),
        "after_subscription": round(monthly - SUBSCRIPTION, 2),
        "trades_month": TRADES_MONTH,
        "note_ar": ("هذه الإعدادات محسوبة على أداء النظام الحقيقيّ "
                    "خلال آخر ثلاثين يوماً. وتغييرها يخرج عن حسابنا، "
                    "ونتيجة التغيير على مسؤوليتك."),
        "note_en": ("Calculated from the system's real 30-day performance. "
                    "Changing these settings is at your own risk."),
    }
