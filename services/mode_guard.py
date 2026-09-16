"""🎯 حارس وضع المراكز — يضبط الحسابات على الاتّجاه الواحد.

مقيس 16 سبتمبر: ثلاثة حسابات على وضع الاتّجاهين (Hedge)، فكل
اوامرنا تُرفض بـ-4061. ابوبكر رصيده 100.98$ وصفر صفقات، و55
محاولة فاشلة في 48 ساعة.

ونظامنا يفتح مركزا واحدا للعملة ويغلقه بأمر معاكس — وهذا هو وضع
الاتّجاه الواحد. فنضبط الحساب عليه عند الربط ودوريا، بدل تعقيد
الكود بدعم وضعين.

الاطفاء: touch /opt/whalex/db/mode_guard.off
"""
import os
import time
import sqlite3
import logging

log = logging.getLogger("mode_guard")
DB = "/opt/whalex/db/whalex.db"
OFF = "/opt/whalex/db/mode_guard.off"


def fix_user(user_id, exchange="binance") -> dict:
    """يضبط حساب مشترك واحد."""
    if os.path.exists(OFF):
        return {"skipped": True}
    try:
        from services.exchanges import get as _ga
        from services.binance_trader import get_credentials
        ad = _ga(exchange)
        if not ad or not hasattr(ad, "ensure_oneway"):
            return {"ok": False, "why": "غير مدعوم"}
        cr = get_credentials(user_id)
        if not cr:
            return {"ok": False, "why": "لا مفاتيح"}
        cl = ad.client(cr["api_key"], cr["api_secret"],
                       cr.get("passphrase", ""), futures=True,
                       testnet=bool(cr.get("is_testnet")))
        return ad.ensure_oneway(cl)
    except Exception as e:
        return {"ok": False, "why": str(e)[:60]}


def sweep() -> dict:
    """يمسح كل الحسابات المفعّلة."""
    if os.path.exists(OFF):
        return {"skipped": True}
    out = {"checked": 0, "changed": 0, "pending": 0, "failed": 0}
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        rows = [(r[0], r[1] or "binance") for r in c.execute(
            "SELECT user_id, exchange FROM user_binance_credentials "
            "WHERE auto_trade_enabled=1")]
        c.close()
    except Exception as e:
        return {"error": str(e)[:60]}
    for uid, ex in rows:
        out["checked"] += 1
        r = fix_user(uid, ex)
        if r.get("changed"):
            out["changed"] += 1
            log.warning("🎯 %s: ضُبط على الاتّجاه الواحد", uid[:8])
        elif "مركز مفتوح" in str(r.get("why", "")):
            out["pending"] += 1
        elif not r.get("ok"):
            out["failed"] += 1
        time.sleep(0.4)
    return out


async def loop():
    import asyncio
    await asyncio.sleep(420)
    while True:
        try:
            r = sweep()
            if r.get("changed"):
                log.warning("🎯 حارس الوضع: ضُبط %d حساب", r["changed"])
        except Exception as e:
            log.debug("mode loop: %s", e)
        await asyncio.sleep(3600)
