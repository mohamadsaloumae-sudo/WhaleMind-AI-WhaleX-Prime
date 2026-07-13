"""
🚨 Watchdog — حارس الحلقات. كل حلقة حرجة تنبض؛ إن صمتت > عتبتها → إنذار تيليجرام.
يمنع الأعطال الصامتة (مثل انقطاع ob_stream دون علم أحد).
"""
import asyncio, time, logging
log = logging.getLogger("watchdog")

_HB: dict = {}        # name -> آخر نبضة
_ALERTED: dict = {}   # name -> هل أُنذر (منعاً للتكرار)

def beat(name: str):
    _HB[name] = time.time()

# عتبة الصمت المسموح (ثانية) لكل حلقة — أطول من دورتها الطبيعية بهامش
_THRESHOLDS = {
    "ob_stream": 120,
    "predator":  180,
    "manager":   90,
    "scout":     400,
    "scout_long": 500,
}

async def watchdog_loop(interval: int = 60):
    from services.telegram import send_message
    from core.config import get_settings
    await asyncio.sleep(150)   # مهلة إقلاع قبل بدء المراقبة
    log.info("🚨 Watchdog يعمل — يراقب %d حلقات", len(_THRESHOLDS))
    while True:
        try:
            ch = get_settings().telegram_admin_chat_id
            now = time.time()
            for name, thr in _THRESHOLDS.items():
                last = _HB.get(name, 0)
                if last == 0:
                    continue   # لم تنبض بعد (حلقة غير مفعّلة)
                silent = now - last
                if silent > thr and not _ALERTED.get(name):
                    _ALERTED[name] = True
                    log.error("🚨 حلقة %s صامتة %.0fs (عتبة %ds)", name, silent, thr)
                    if ch:
                        await send_message(ch, f"🚨 <b>تحذير النظام</b>\n"
                            f"حلقة <code>{name}</code> صامتة منذ {silent:.0f} ثانية — قد تكون معلّقة.")
                elif silent <= thr and _ALERTED.get(name):
                    _ALERTED[name] = False
                    log.info("✅ حلقة %s تعافت", name)
                    if ch:
                        await send_message(ch, f"✅ حلقة <code>{name}</code> عادت للعمل.")
        except Exception as e:
            log.error("watchdog: %s", e)
        await asyncio.sleep(interval)
