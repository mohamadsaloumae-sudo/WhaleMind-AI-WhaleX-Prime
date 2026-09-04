"""🧠 مصالحة صفوف التدريب المعلّقة.

المشكلة المقيسة: 21 إشارة بلا إغلاق في يوم واحد، 20 منها ليست
في أي سجلّ مراكز — وكلّها tier=SP. فمتتبّع السبوت يكتب نتائجه في
spot_results ولا يُحدّث ml_training، فتبقى outcome فارغة للأبد.

وهذا يُفسّر أن 52% من صفوف التدريب بلا نتيجة — فالنموذج يتدرّب
على نصف بياناته.

والحارس: كل نصف ساعة يبحث عن الصفوف المعلّقة، ويجد نتيجتها في
spot_results إن وُجدت، وإلّا يُغلقها بعد ست ساعات كمنتهية.
"""
import asyncio
import logging
import os
import sqlite3
import time

log = logging.getLogger("ml_reconcile")
ML = "/opt/whalex/ml_training.db"
WX = "/opt/whalex/db/whalex.db"
EVERY = 1800
STALE_HOURS = 6.0
OFF_FLAG = "/opt/whalex/db/ml_reconcile.off"


def reconcile() -> dict:
    fixed = expired = 0
    try:
        m = sqlite3.connect(ML); m.row_factory = sqlite3.Row
        cut = int(time.time()) - 86400 * 60
        rows = [dict(x) for x in m.execute(
            "SELECT id, symbol, direction, entry, timestamp, tier "
            "FROM training_signals WHERE (closed_at IS NULL OR closed_at=0) "
            "AND timestamp>?", (cut,))]
        if not rows:
            m.close()
            return {"fixed": 0, "expired": 0, "pending": 0}
        w = sqlite3.connect(WX); w.row_factory = sqlite3.Row
        for r in rows:
            age_h = (time.time() - (r["timestamp"] or 0)) / 3600.0
            # ① نبحث عن النتيجة في نتائج السبوت
            hit = None
            if str(r.get("tier") or "") == "SP":
                hit = w.execute(
                    "SELECT pnl_pct, ts, reason FROM spot_results "
                    "WHERE symbol=? AND ts>? ORDER BY ts LIMIT 1",
                    (r["symbol"], r["timestamp"] or 0)).fetchone()
            if hit:
                m.execute(
                    "UPDATE training_signals SET pnl_pct=?, closed_at=?, "
                    "outcome=?, close_reason=COALESCE(close_reason,?), "
                    "result=? WHERE id=?",
                    (hit["pnl_pct"], int(hit["ts"]),
                     1 if (hit["pnl_pct"] or 0) > 0 else 0,
                     hit["reason"], "closed", r["id"]))
                fixed += 1
            elif age_h >= STALE_HOURS:
                # ② لم تُفتح أصلاً — نُغلقها بلا نتيجة تداول
                m.execute(
                    "UPDATE training_signals SET closed_at=?, pnl_pct=0, "
                    "outcome=NULL, close_reason='never_executed', "
                    "result='void' WHERE id=?",
                    (int(time.time()), r["id"]))
                expired += 1
        m.commit()
        pending = len(rows) - fixed - expired
        m.close(); w.close()
        return {"fixed": fixed, "expired": expired, "pending": pending}
    except Exception as e:
        log.error("مصالحة التدريب: %s", e)
        return {"fixed": 0, "expired": 0, "pending": 0}


async def reconcile_loop():
    await asyncio.sleep(180)
    while True:
        try:
            if not os.path.exists(OFF_FLAG):
                r = await asyncio.to_thread(reconcile)
                if r["fixed"] or r["expired"]:
                    log.info("🧠 مصالحة: صُحّح %d | أُغلق %d | معلّق %d",
                             r["fixed"], r["expired"], r["pending"])
        except Exception as e:
            log.error("حلقة المصالحة: %s", e)
        await asyncio.sleep(EVERY)
