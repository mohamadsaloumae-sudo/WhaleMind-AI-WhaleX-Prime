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
                # 🛡️ لا نزوّر الاغلاق — نبيع فعلا.
                #    مقيس 16 سبتمبر: HIVE و ALT سُجّلتا closed هنا بلا
                #    بيع، فبقي 3923 HIVE و 35840 ALT في حساب المشترك
                #    (424$) ونحن نظنها بيعت. فلا USDT حر، وتُرفض
                #    الاشارات الرابحة (STRAX +9% · XCN +6.66%).
                try:
                    from services.spot_exec import sell_all as _sell
                    _res = _sell(r.get("exchange") or "binance", r["symbol"],
                                 float(hit["pnl_pct"] or 0) and 0.0 or 0.0)
                    _ok = any(x.get("ok") for x in (_res or []))
                except Exception as _se:
                    log.warning("🪙 بيع المصالحة %s: %s", r["symbol"], _se)
                    _ok = False
                if _ok:
                    log.info("🪙 صُوّيت %s — بيع فعليّ (%s %.2f%%)",
                             r["symbol"], hit["reason"], hit["pnl_pct"] or 0)
                    fixed += 1
                else:
                    log.warning("🪙⚠️ %s: الرادار أغلق ولم ينجح البيع — "
                                "نترك المركز مفتوحاً", r["symbol"])
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
