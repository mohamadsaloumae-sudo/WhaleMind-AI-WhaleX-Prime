"""💵 عمولة كل صفقة من باينانس — لا تقدير.

مقيس: مشترك خسر 2.53$ في يوم، منها 2.31$ عمولات (91%) و0.22$
خسارة تداول. ولم يكن يرى الفرق في سجلّه.
"""
import asyncio, logging, os, sqlite3, time
from collections import defaultdict, Counter

log = logging.getLogger("commission_sync")
DB = "/opt/whalex/db/whalex.db"
EVERY = 900
OFF = "/opt/whalex/db/commission_sync.off"


def sync_user(uid, creds, hours=48):
    from services.binance_trader import decrypt
    from binance.client import Client
    cl = Client(decrypt(creds["api_key_encrypted"]),
                decrypt(creds["api_secret_encrypted"]))
    # 📊 مقيس 11 سبتمبر: كان يجمع رسوم 48 ساعة لكل عملة ثم يقسمها على
    #    الصفقات غير المحدثة وحدها، فالصفقة الجديدة تأخذ رسوم القديمة
    #    معها. باينانس 3.15$ ونحن سجلنا 7.04$ — ضعف ونصف.
    #    والاصلاح: نطابق كل رسم بصفقته بالوقت لا بالعملة.
    t0 = int((time.time() - hours * 3600) * 1000)
    events = []
    for x in cl.futures_income_history(startTime=t0, limit=1000):
        if x.get("incomeType") == "COMMISSION":
            events.append((int(x.get("time") or 0) // 1000,
                           str(x.get("symbol") or ""),
                           abs(float(x.get("income") or 0))))
    if not events:
        return 0
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute(
        "SELECT id, symbol, pnl_usdt, opened_at, closed_at FROM user_trades "
        "WHERE user_id=? AND status='closed' AND closed_at>? "
        "AND COALESCE(commission,0)=0",
        (uid, int(time.time() - hours * 3600)))]
    n = 0
    for r in rows:
        o = int(r.get("opened_at") or 0)
        cl_ = int(r.get("closed_at") or 0)
        if o <= 0 or cl_ <= 0:
            continue
        # كل رسم وقع بين الفتح والاغلاق (بهامش 90 ثانية للطرفين)
        share = round(sum(v for t, sym, v in events
                          if sym == r["symbol"] and o - 90 <= t <= cl_ + 90), 6)
        net = round((r.get("pnl_usdt") or 0) - share, 6)
        c.execute("UPDATE user_trades SET commission=?, net_usdt=? WHERE id=?",
                  (share, net, r["id"]))
        n += 1
    c.commit(); c.close()
    return n


async def sync_loop():
    await asyncio.sleep(120)
    while True:
        try:
            if not os.path.exists(OFF):
                c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
                rows = [dict(r) for r in c.execute(
                    "SELECT * FROM user_binance_credentials "
                    "WHERE auto_trade_enabled=1")]
                c.close()
                tot = 0
                for d in rows:
                    try:
                        tot += await asyncio.to_thread(sync_user, d["user_id"], d)
                    except Exception as e:
                        log.debug("عمولة %s: %s", d["user_id"][:8], str(e)[:40])
                if tot:
                    log.info("💵 عمولات: حُدِّثت %d صفقة", tot)
        except Exception as e:
            log.error("مزامنة العمولات: %s", e)
        await asyncio.sleep(EVERY)
