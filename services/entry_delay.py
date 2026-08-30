"""⏳ قائمة انتظار الإشارات المشبوهة — لا تمنع، بل تتأنّى.

المشكلة المقيسة: إشارة شورت تُفتَح عند قمّة النطاق بينما دفتر الأوامر
ما زال ضغطُه شراءً والتدفّق صاعد — فتنفجر العملة صعوداً خلال دقائق
ويُضرب الوقف. ومثلها لونج عند قاع والدفتر بيع والتدفّق هابط.

وهذه الحالة نادرة: 37 من 500 صفقة (7%). والباقي يمرّ فوراً بلا تأخير.

والقياس على 37 صفقة بسعر الدخول الحقيقيّ بعد الانتظار:
  انتظار 2د حدّ -0.5% → +18.3 نقطة (النصفان +14.8 و +3.5)
  انتظار 3د حدّ -0.5% → +15.3 نقطة (النصفان +12.0 و +3.3)
  انتظار 5د            → +10.1 (وينقلب سالباً في النصف الثاني)
  انتظار 7د            →  +4.9 (ينقلب أيضاً)
فاخترنا 3 دقائق — موجب في النصفين، وأطول من ذلك يُفوّت الرابحة.

⚠️ معزول تماماً: أي خطأ هنا يُمرّر الإشارة فوراً كما لو لم يوجد.
"""
import asyncio
import logging
import os
import time

log = logging.getLogger("entry_delay")

WAIT_SEC = 180            # 3 دقائق
ADVERSE_PCT = 0.5         # تحرّكت ضدّنا بهذا القدر → نتركها
OFF_FLAG = "/opt/whalex/db/entry_delay.off"

_stats = {"seen": 0, "waited": 0, "dropped": 0, "passed": 0}


def is_suspect(sig) -> bool:
    """هل الإشارة من الحالة النادرة الخطرة؟"""
    try:
        d = str(getattr(sig, "direction", "") or "").upper()
        rp = float(getattr(sig, "range_pos", 0) or 0)
        ob = float(getattr(sig, "ob_pressure", 0) or 0)
        cv = str(getattr(sig, "cvd_flow", "") or "")
        if d == "SHORT":
            return rp >= 0.90 and ob > 0.05 and cv == "up"
        if d == "LONG":
            return rp <= 0.10 and ob < -0.05 and cv == "down"
    except Exception as e:
        log.debug("فحص الاشتباه: %s", e)
    return False


async def _price(symbol: str) -> float:
    """سعر السوق الحاليّ من باينانس."""
    import httpx
    url = "https://fapi.binance.com/fapi/v1/ticker/price"
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(url, params={"symbol": symbol})
        return float(r.json().get("price") or 0)


async def should_enter(sig) -> tuple:
    """يُعيد (ندخل؟، السبب). الإشارة العادية تمرّ فوراً."""
    _stats["seen"] += 1
    if os.path.exists(OFF_FLAG):
        _stats["passed"] += 1
        return True, ""
    if not is_suspect(sig):
        _stats["passed"] += 1
        return True, ""

    sym = str(getattr(sig, "symbol", ""))
    d = str(getattr(sig, "direction", "")).upper()
    entry = float(getattr(sig, "entry", 0) or 0)
    if not sym or entry <= 0:
        _stats["passed"] += 1
        return True, ""

    _stats["waited"] += 1
    log.info("⏳ %s %s مشبوهة — ننتظر %ds قبل القرار", sym, d, WAIT_SEC)
    try:
        await asyncio.sleep(WAIT_SEC)
        px = await _price(sym)
        if px <= 0:
            _stats["passed"] += 1
            return True, "تعذّر السعر — نمرّ"
        sign = 1.0 if d == "LONG" else -1.0
        move = (px - entry) / entry * 100.0 * sign
        if move <= -ADVERSE_PCT:
            _stats["dropped"] += 1
            log.warning("⏳🚫 %s %s تُركت — تحرّكت %.2f%% ضدّنا خلال %ds",
                        sym, d, move, WAIT_SEC)
            return False, f"تحرّكت {move:.2f}% ضدّنا خلال الانتظار"
        _stats["passed"] += 1
        log.info("⏳✅ %s %s صمدت (%.2f%%) — ندخل", sym, d, move)
        return True, f"صمدت {move:+.2f}%"
    except Exception as e:
        # أي خطأ = نمرّ كما لو لم توجد هذه الوحدة
        log.error("⏳ خطأ في الانتظار %s: %s — نمرّ", sym, e)
        _stats["passed"] += 1
        return True, "خطأ — نمرّ"


def stats() -> dict:
    return dict(_stats)
