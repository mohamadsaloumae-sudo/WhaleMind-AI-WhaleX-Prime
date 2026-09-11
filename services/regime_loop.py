"""🌐 تحديث خريطة الانظمة — كل 6 ساعات.

الخريطة تُبنى من التاريخ الفعلي، فتتكيف تلقائيا حين يتغير السوق:
رادار كان رابحا في نظام وصار خاسرا يُمنع تلقائيا، والعكس.
"""
import asyncio
import logging

log = logging.getLogger("regime_loop")
EVERY = 6 * 3600


async def regime_loop():
    await asyncio.sleep(90)
    while True:
        try:
            from quant_engine.regime_gate import build_map, current
            m = build_map()
            if m.get("ok"):
                log.info("🌐 الخريطة حُدّثت · النظام الآن %s · %d منع",
                         current(), sum(len(v) for v in m.get("block", {}).values()))
        except Exception as e:
            log.warning("regime_loop: %s", str(e)[:80])
        await asyncio.sleep(EVERY)
