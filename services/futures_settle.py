"""💰 تسوية الفيوتشر من المنصّة — لكل المنصّات السبع.

الفيوتشر ثبت مطابقا 8/8 بفرق 0.0013$ (قيس 14 سبتمبر)، لكن حسابه
مبني على منطقنا لا على المنصّة. وعند دخول مشتركين من غير باينانس
قد يختلف — فنقرأ realizedPnl من المنصّة نفسها عبر ccxt.

يستعمل adapter.settle الموحّد في base.py — فيعمل لباينانس وبايبت
ومكسي وأوكي إكس وبيتجت وجيت وبينج إكس بلا كود خاص.
"""
import time
import sqlite3
import logging

log = logging.getLogger("futures_settle")
DB = "/opt/whalex/db/whalex.db"


def settle(trade_id: int) -> dict:
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        c.row_factory = sqlite3.Row
        r = c.execute("SELECT * FROM user_trades WHERE id=?",
                      (trade_id,)).fetchone()
        c.close()
        if not r:
            return {"ok": False, "error": "لا صفقة"}
        d = dict(r)
        if not d.get("closed_at"):
            return {"ok": False, "error": "لم تُغلق"}

        from services.exchanges import get as _get_ad
        from services.binance_trader import get_credentials
        ex = (d.get("exchange") or "binance").lower()
        ad = _get_ad(ex)
        if not ad:
            return {"ok": False, "error": "لا محوّل"}
        cr = get_credentials(d["user_id"])
        if not cr:
            return {"ok": False, "error": "لا مفاتيح"}
        cl = ad.client(cr["api_key"], cr["api_secret"],
                       cr.get("passphrase", ""), futures=True,
                       testnet=bool(cr.get("is_testnet")))

        res = ad.settle(cl, d["symbol"], int(d["opened_at"]),
                        int(d["closed_at"]), futures=True)
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error", "فشل")}

        w = sqlite3.connect(DB, timeout=10)
        w.execute("UPDATE user_trades SET real_fee=?, real_net=? WHERE id=?",
                  (res["fee"], res["net"], trade_id))
        w.commit()
        w.close()
        return {"ok": True, **res}
    except Exception as e:
        log.debug("settle %s: %s", trade_id, str(e)[:70])
        return {"ok": False, "error": str(e)[:70]}


def settle_pending(limit: int = 30) -> dict:
    done = fail = 0
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        ids = [r[0] for r in c.execute(
            "SELECT id FROM user_trades WHERE closed_at IS NOT NULL "
            "AND real_net IS NULL AND market='futures' "
            "ORDER BY closed_at DESC LIMIT ?", (limit,))]
        c.close()
    except Exception as e:
        return {"error": str(e)[:60]}
    for i in ids:
        if settle(i).get("ok"):
            done += 1
        else:
            fail += 1
        time.sleep(0.35)
    return {"done": done, "failed": fail, "total": len(ids)}
