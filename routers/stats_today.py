"""📊 مصدر واحد لكل الشاشات — من التنفيذ الحقيقي وحده.

المشكلة: الرئيسية تعرض +25.5% والصفقات +20.2% ونفس اليوم، لان كل
شاشة تحسب من مصدر مختلف وبعضها يجمع نسبا في الواجهة.

والاخطر: مجموع النسب لا يساوي المال. صفقة +10% على 25$ = +2.5$
وصفقة -10% على 50$ = -5$. فالمجموع 0% بالنسبة و -2.5$ بالمال.
والمشترك يرى "ربح" ورصيده ينقص.

القاعدة: user_trades وحده — مطابق 100% لباينانس (قيس 10/10 بالسنت).
والعرض بالدولار اولا، والنسبة ثانوية.
"""
import time
import sqlite3
import logging
from fastapi import APIRouter, Depends
from routers.auth import get_current_user

log = logging.getLogger("stats_today")
router = APIRouter(prefix="/api/stats", tags=["stats"])
DB = "/opt/whalex/db/whalex.db"
TZ = 4 * 3600


def _day_start(offset_days=0):
    now = time.time()
    t0 = int(now - ((now + TZ) % 86400)) - offset_days * 86400
    return t0


def _calc(rows):
    if not rows:
        return {"trades": 0, "net_usd": 0.0, "gross_usd": 0.0, "fees_usd": 0.0,
                "win_rate": 0.0, "profit_factor": 0.0, "avg_pct": 0.0,
                "wins": 0, "losses": 0}
    nets = [float(r.get("net_usdt") or 0) for r in rows]
    pcts = [float(r.get("pnl_pct") or 0) for r in rows]
    w = [x for x in nets if x > 0]
    l = [x for x in nets if x <= 0]
    gp, gl = sum(w), abs(sum(l))
    return {
        "trades": len(rows),
        "net_usd": round(sum(nets), 2),
        "gross_usd": round(sum(float(r.get("pnl_usdt") or 0) for r in rows), 2),
        "fees_usd": round(sum(float(r.get("commission") or 0) for r in rows), 2),
        "win_rate": round(len(w) * 100 / len(rows), 1),
        "profit_factor": round(gp / gl, 2) if gl > 0 else (999.0 if gp > 0 else 0.0),
        "avg_pct": round(sum(pcts) / len(pcts), 2),
        "wins": len(w),
        "losses": len(l),
    }


def _with_return(d, capital):
    """العائد الحقيقي على راس المال — لا نسبة عدد الصفقات.

    مقيس 13 سبتمبر: الشاشة تقول "فوز 55.9%" والمشترك خسر 6.56$.
    فنسبة الفوز تعد الصفقات ولا تقيس المال. والمشترك يقرأها ربحا.
    """
    cap = float(capital or 0)
    d["capital"] = round(cap, 2)
    d["return_pct"] = round(d["net_usd"] / cap * 100, 2) if cap > 0 else None
    d["fees_pct"] = round(d["fees_usd"] / cap * 100, 2) if cap > 0 else None
    return d


def _capital_of(user_id):
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        r = c.execute("SELECT trading_capital FROM user_binance_credentials "
                      "WHERE user_id=? LIMIT 1", (user_id,)).fetchone()
        c.close()
        if r and r[0]:
            return float(r[0])
    except Exception:
        pass
    try:
        import sys
        sys.path.insert(0, "/opt/whalex")
        from services.binance_trader import usdt_futures_balance
        v, _ = usdt_futures_balance(user_id)
        return v
    except Exception:
        return 0.0


def _fetch_spot(user_id, since):
    """السبوت في جدول منفصل — spot_positions_multi."""
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM spot_positions_multi WHERE user_id=? "
            "AND closed_ts >= ? AND status='closed'", (user_id, since))]
        c.close()
        out = []
        for r in rows:
            spend = float(r.get("spend") or 0)
            pct = float(r.get("pnl_pct") or 0)
            rn = r.get("real_net")
            if rn is not None:
                buy = float(r.get("real_buy") or 0)
                out.append({
                    "pnl_pct": round(float(rn)/buy*100, 3) if buy > 0 else pct,
                    "pnl_usdt": float(r.get("real_sell") or 0) - buy,
                    "commission": float(r.get("real_fee") or 0),
                    "net_usdt": float(rn)})
            else:
                out.append({"pnl_pct": pct,
                            "pnl_usdt": spend * pct / 100,
                            "commission": spend * 0.002,
                            "net_usdt": spend * pct / 100 - spend * 0.002})
        return out
    except Exception as e:
        log.debug("spot fetch: %s", e)
        return []


def _fetch(user_id, since, market="futures"):
    if market == "spot":
        return _fetch_spot(user_id, since)
    c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    c.row_factory = sqlite3.Row
    q = ("SELECT * FROM user_trades WHERE user_id=? AND closed_at >= ? "
         "AND closed_at IS NOT NULL")
    a = [user_id, since]
    if market:
        q += " AND market=?"
        a.append(market)
    rows = [dict(r) for r in c.execute(q, a)]
    c.close()
    return rows


@router.get("/today")
async def today(market: str = "futures", user=Depends(get_current_user)):
    user_id = user["sub"]
    """اليوم — بالدولار من التنفيذ الحقيقي."""
    d = _calc(_fetch(user_id, _day_start(), market))
    return {**_with_return(d, _capital_of(user_id)),
            "market": market, "period": "today"}


@router.get("/summary")
async def summary(market: str = "futures", user=Depends(get_current_user)):
    user_id = user["sub"]
    """اليوم · أمس · 7 ايام · 30 يوما — كلها من مصدر واحد."""
    out = {}
    for key, since in (("today", _day_start()),
                       ("week", int(time.time()) - 7 * 86400),
                       ("month", int(time.time()) - 30 * 86400)):
        out[key] = _calc(_fetch(user_id, since, market))
    y0 = _day_start(1)
    c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    c.row_factory = sqlite3.Row
    q = ("SELECT * FROM user_trades WHERE user_id=? AND closed_at >= ? "
         "AND closed_at < ?")
    a = [user_id, y0, _day_start()]
    if market:
        q += " AND market=?"
        a.append(market)
    out["yesterday"] = _calc([dict(r) for r in c.execute(q, a)])
    c.close()
    cap = _capital_of(user_id)
    for k in ("today", "yesterday", "week", "month"):
        if k in out:
            out[k] = _with_return(out[k], cap)
    out["market"] = market
    out["capital"] = round(cap, 2)
    return out
