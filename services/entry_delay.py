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
    """هل الإشارة من الحالة النادرة الخطرة؟

    ⚠️ ob_pressure و cvd_flow ليسا على كائن الإشارة — يُجلبان من
    live_context كما يفعل ml_recorder تماماً. وكانت الوحدة تقرؤهما
    من sig فتجدهما صفراً دائماً، فلا تلتقط شيئاً أبداً.
    """
    try:
        d = str(getattr(sig, "direction", "") or "").upper()
        rp = float(getattr(sig, "range_pos", 0) or 0)
        ob, cv = 0.0, ""
        try:
            from quant_engine.ml_brain import live_context
            _lc = live_context(str(getattr(sig, "symbol", "")))
            ob = float(_lc.get("ob_pressure") or 0)
            cv = str(_lc.get("cvd_flow") or "")
        except Exception as _le:
            log.debug("سياق حيّ: %s", _le)
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


AGAINST_FLOW_OFF = "/opt/whalex/db/against_flow.off"


def against_flow(sig) -> bool:
    """شورت مع تيّار صاعد أو لونج مع تيّار هابط — MX فقط.

    مقيس على 1433 صفقة MX/باينانس:
      SHORT + cvd=down/flat  →  +0.43%  (+171 اجمالاً)
      SHORT + cvd=up         →  -0.70%  (-151)
      LONG  + cvd=down       →  -0.39%  (-178)
    والنمط يصمد في 5 ايام من 6. ورفض الخانتين يرفع
    الصافي من -228% الى +101%.
    """
    try:
        if os.path.exists(AGAINST_FLOW_OFF):
            return False
        if (str(getattr(sig, "tier", "") or "")).upper() != "MX":
            return False
        d = str(getattr(sig, "direction", "") or "").upper()
        from quant_engine.ml_brain import live_context
        cv = str(live_context(str(getattr(sig, "symbol", ""))).get(
            "cvd_flow") or "").lower()
        return (d == "SHORT" and cv == "up") or (d == "LONG" and cv == "down")
    except Exception as e:
        log.debug("against_flow: %s", e)
        return False


async def should_enter(sig) -> tuple:
    """يُعيد (ندخل؟، السبب). الإشارة العادية تمرّ فوراً."""
    _stats["seen"] += 1
    if os.path.exists(OFF_FLAG):
        _stats["passed"] += 1
        return True, ""
    # 🌊 ضد التيّار — رفض فوريّ بلا انتظار، فالانتظار لا يعكس التيّار
    if against_flow(sig):
        _stats["dropped"] += 1
        return False, "ضد تيّار التدفّق"
    # 🕯️ تأكيد شمعة الدقيقة — للمستنفَدة فقط (استنفاد 200%+).
    #    معيار freqtrade: الاشارة من إطار 5د والتأكيد من إغلاق 1د.
    #    مقيس: الخبيثة تدخل عند استنفاد 300% والسليمة 130%.
    try:
        from services.candle_confirm import should_enter_candle as _cc
        _ok, _cw = await _cc(str(getattr(sig, "symbol", "")),
                             str(getattr(sig, "direction", "")))
        if not _ok:
            _stats["dropped"] += 1
            return False, _cw
    except Exception as _ce:
        log.debug("بوابة الشمعة: %s", _ce)
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
