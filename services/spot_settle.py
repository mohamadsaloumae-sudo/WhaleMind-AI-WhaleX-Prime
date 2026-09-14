"""💰 تسوية السبوت من المنصّة — الرقم الحقيقي لا المقدّر.

مقيس 14 سبتمبر على 8 صفقات: حسابنا يخطئ في كلها.
  POWR حسبنا -0.38$ والحقيقة -2.03$ (خمسة اضعاف)
  BERA حسبنا -0.30$ والحقيقة -2.29$ (سبعة اضعاف)
  ARK  حسبنا +1.07$ والحقيقة -0.22$ (عكس الاشارة)

والسبب اننا نحسب spend × pnl_pct، وهو تقدير من سعرين لا من
التنفيذ الفعلي: لا يرى الانزلاق ولا رسوم الشراء ولا التعبئة الجزئية.

والحل: نقرأ get_my_trades من باينانس بين وقت الفتح والاغلاق،
ونجمع الشراء والبيع والرسوم كما وقعت. ثلاثة ارقام وصافيها:
    الصافي = البيع − الشراء − الرسوم
بلا نسب ولا تقديرات.
"""
import time
import sqlite3
import logging

log = logging.getLogger("spot_settle")
DB = "/opt/whalex/db/whalex.db"


def settle(pos_id: int) -> dict:
    """يقرأ التنفيذ الحقيقي ويملأ real_buy/sell/fee/net."""
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        c.row_factory = sqlite3.Row
        r = c.execute("SELECT * FROM spot_positions_multi WHERE id=?",
                      (pos_id,)).fetchone()
        c.close()
        if not r:
            return {"ok": False, "error": "لا صفقة"}
        d = dict(r)
        from services.exchanges import get as _get_ad
        from services.spot_exec import spot_traders_for
        ex = d.get("exchange") or "binance"
        ad = _get_ad(ex)
        if not ad:
            return {"ok": False, "error": "لا محوّل"}
        creds = {u: (k, sc, pw, tn) for u, k, sc, pw, _a, _m, tn
                 in spot_traders_for(ex)}
        if d["user_id"] not in creds:
            return {"ok": False, "error": "لا مفاتيح"}
        k, sc, pw, tn = creds[d["user_id"]]
        c2 = ad.client(k, sc, pw, futures=False, testnet=tn)

        t0 = int(d.get("ts") or 0)
        t1 = int(d.get("closed_ts") or time.time())
        r2 = ad.settle(c2, d["symbol"], t0, t1, futures=False)
        if not r2.get("ok"):
            return {"ok": False, "error": r2.get("error", "فشل")}
        buy = float(r2["buy"]); sell = float(r2["sell"]); fee = float(r2["fee"])
        net = sell - buy - fee

        w = sqlite3.connect(DB, timeout=10)
        w.execute("UPDATE spot_positions_multi SET real_buy=?, real_sell=?, "
                  "real_fee=?, real_net=? WHERE id=?",
                  (round(buy, 4), round(sell, 4), round(fee, 4),
                   round(net, 4), pos_id))
        w.commit()
        w.close()
        log.info("💰 تسوية %s: شراء %.2f$ · بيع %.2f$ · رسوم %.3f$ · صافي %+.2f$",
                 d["symbol"], buy, sell, fee, net)
        return {"ok": True, "buy": buy, "sell": sell, "fee": fee, "net": net}
    except Exception as e:
        log.debug("settle %s: %s", pos_id, str(e)[:70])
        return {"ok": False, "error": str(e)[:70]}


def settle_pending(limit: int = 30) -> dict:
    """يُسوّي المغلقة التي لم تُسوَّ بعد."""
    done = fail = 0
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        ids = [r[0] for r in c.execute(
            "SELECT id FROM spot_positions_multi WHERE status='closed' "
            "AND real_net IS NULL AND exchange='binance' "
            "ORDER BY closed_ts DESC LIMIT ?", (limit,))]
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
