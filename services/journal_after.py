"""⏱️ المرحلة الرابعة — هل كان الاغلاق صحيحا؟

كل دقيقة نأخذ الصفقات المغلقة قبل 5 و15 و60 دقيقة، ونقيس اين
وصل السعر بعد خروجنا. فنعرف: هل مديرنا يغلق مبكرا ام في وقته.

الاطفاء: touch /opt/whalex/db/journal.off
"""
import time
import asyncio
import sqlite3
import logging

log = logging.getLogger("journal_after")
DB = "/opt/whalex/db/trade_journal.db"
MARKS = (5, 15, 60)


async def _price(symbol: str) -> float:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get("https://fapi.binance.com/fapi/v1/ticker/price",
                            params={"symbol": symbol})
            return float(r.json().get("price") or 0)
    except Exception:
        return 0.0


async def after_loop():
    import os
    from services.trade_journal import after
    log.info("⏱️ سجل ما بعد الاغلاق بدأ")
    await asyncio.sleep(60)
    while True:
        try:
            if os.path.exists("/opt/whalex/db/journal.off"):
                await asyncio.sleep(60)
                continue
            now = int(time.time())
            c = sqlite3.connect(DB, timeout=10)
            for m in MARKS:
                lo, hi = now - m * 60 - 45, now - m * 60 + 45
                rows = c.execute(
                    "SELECT trade_key, symbol, direction, price FROM journal "
                    "WHERE stage IN ('death','blocked') AND ts BETWEEN ? AND ?", (lo, hi)).fetchall()
                for k, sym, d, px in rows:
                    done = c.execute(
                        "SELECT 1 FROM journal WHERE trade_key=? AND stage='after' "
                        "AND data LIKE ?", (k, '%"minutes": %d%%' % m)).fetchone()
                    if done:
                        continue
                    lp = await _price(sym)
                    if lp > 0:
                        after(k, sym, d, float(px), lp, m)
                    await asyncio.sleep(0.15)
            c.close()
        except Exception as e:
            log.warning("after_loop: %s", str(e)[:80])
        await asyncio.sleep(60)
