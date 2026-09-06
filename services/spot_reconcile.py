"""🪙 مصالحة صفقات السبوت العالقة.

المشكلة المقيسة: الرادار يُغلق الصفقة ويكتب النتيجة في spot_results،
ولا يُحدّث spot_positions_multi. فتبقى status='open' إلى الأبد.

وأثرها: SOMIUSDT بقيت "مفتوحة" 139 ساعة بعد إغلاقها فعلياً
(-2.04% ob_reversal)، وشاشة العرض تحسب ربحها بسعر اليوم فتُظهرها
رابحة. والمشترك يبحث عنها في الصفقات المفتوحة فلا يجدها — فيظنّ
النظام معطوباً أو الأرقام مزوّرة.

والحارس: كل عشر دقائق يبحث عن الصفقات المفتوحة التي لها نتيجة
لاحقة في spot_results، ويُغلقها.
"""
import asyncio
import logging
import os
import sqlite3
import time

log = logging.getLogger("spot_reconcile")
DB = "/opt/whalex/db/whalex.db"
EVERY = 600
OFF_FLAG = "/opt/whalex/db/spot_reconcile.off"


def reconcile() -> int:
    fixed = 0
    try:
        c = sqlite3.connect(DB)
        c.row_factory = sqlite3.Row
        rows = [dict(x) for x in c.execute(
            "SELECT id, symbol, ts FROM spot_positions_multi "
            "WHERE status='open'")]
        for r in rows:
            hit = c.execute(
                "SELECT pnl_pct, reason FROM spot_results "
                "WHERE symbol=? AND ts > ? ORDER BY ts LIMIT 1",
                (r["symbol"], r["ts"] or 0)).fetchone()
            if hit:
                c.execute(
                    "UPDATE spot_positions_multi SET status='closed' "
                    "WHERE id=?", (r["id"],))
                log.info("🪙 صُوّيت %s — أُغلقت بالرادار (%s %.2f%%)",
                         r["symbol"], hit["reason"], hit["pnl_pct"] or 0)
                fixed += 1
        c.commit()
        c.close()
    except Exception as e:
        log.error("مصالحة السبوت: %s", e)
    return fixed


async def reconcile_loop():
    await asyncio.sleep(240)
    while True:
        try:
            if not os.path.exists(OFF_FLAG):
                n = await asyncio.to_thread(reconcile)
                if n:
                    log.info("🪙 مصالحة السبوت: %d صفقة عالقة أُغلقت", n)
        except Exception as e:
            log.error("حلقة مصالحة السبوت: %s", e)
        await asyncio.sleep(EVERY)
