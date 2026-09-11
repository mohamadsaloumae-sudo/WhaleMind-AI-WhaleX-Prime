"""📒 دفتر الحسابات الموحّد — مصدر واحد لكل الشاشات.

المشكلة: الادمن وصفقاتي والعدادات تقرأ من جداول مختلفة فتختلف
الارقام، وتُعرض صفقات لم تُفتح على المنصة اصلا.

القاعدة: user_trades وحده — التنفيذ الحقيقي. ما لم يُفتح لا يُعرض.
والترتيب closed_at DESC دائما، مجمّعا بالايام (توقيت الامارات).

المقاييس معيارية: صافي · معامل الربح · التوقع · اقصى تراجع · فوز.
"""
import time
import sqlite3
import logging
from fastapi import APIRouter

log = logging.getLogger("admin_ledger")
router = APIRouter(prefix="/api/admin", tags=["admin-ledger"])
DB = "/opt/whalex/db/whalex.db"
TZ = 4 * 3600


def _day_key(ts):
    return time.strftime("%Y-%m-%d", time.gmtime(int(ts) + TZ))


def _metrics(rows):
    if not rows:
        return {"n": 0, "net": 0.0, "gross": 0.0, "fees": 0.0, "win_rate": 0.0,
                "profit_factor": 0.0, "expectancy": 0.0, "max_dd": 0.0,
                "avg_win": 0.0, "avg_loss": 0.0, "best": 0.0, "worst": 0.0}
    nets = [float(r.get("net_usdt") or 0) for r in rows]
    w = [x for x in nets if x > 0]
    l = [x for x in nets if x <= 0]
    gp, gl = sum(w), abs(sum(l))
    peak = run = dd = 0.0
    for x in nets:
        run += x
        peak = max(peak, run)
        dd = min(dd, run - peak)
    return {
        "n": len(rows),
        "net": round(sum(nets), 2),
        "gross": round(sum(float(r.get("pnl_usdt") or 0) for r in rows), 2),
        "fees": round(sum(float(r.get("commission") or 0) for r in rows), 2),
        "win_rate": round(len(w) * 100 / len(rows), 1),
        "profit_factor": round(gp / gl, 2) if gl > 0 else (999.0 if gp > 0 else 0.0),
        "expectancy": round(sum(nets) / len(rows), 3),
        "max_dd": round(dd, 2),
        "avg_win": round(gp / len(w), 2) if w else 0.0,
        "avg_loss": round(-gl / len(l), 2) if l else 0.0,
        "best": round(max(nets), 2),
        "worst": round(min(nets), 2),
    }


def _slim(r, is_open=False):
    d = {"id": r.get("id"), "symbol": r.get("symbol"),
         "direction": (r.get("direction") or "").upper(),
         "market": r.get("market"), "entry": r.get("entry"),
         "qty": r.get("qty"), "leverage": r.get("leverage"),
         "opened_at": r.get("opened_at"), "order_id": r.get("order_id")}
    if not is_open:
        d.update({
            "exit_price": r.get("exit_price"), "closed_at": r.get("closed_at"),
            "pnl_pct": r.get("pnl_pct"), "pnl_usdt": r.get("pnl_usdt"),
            "commission": r.get("commission"), "net_usdt": r.get("net_usdt"),
            "close_reason": r.get("close_reason"),
            "duration_min": (round(((r.get("closed_at") or 0) - (r.get("opened_at") or 0)) / 60, 1)
                             if r.get("closed_at") and r.get("opened_at") else None)})
    return d


def _enabled(user_id):
    """اي سوق فعّله المشترك — فنفتح دفتره وحده."""
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        c.row_factory = sqlite3.Row
        r = c.execute("SELECT auto_trade_enabled, spot_auto_enabled "
                      "FROM user_binance_credentials WHERE user_id=?",
                      (user_id,)).fetchone()
        c.close()
        if not r:
            return []
        out = []
        if r["auto_trade_enabled"]:
            out.append("futures")
        if r["spot_auto_enabled"]:
            out.append("spot")
        return out
    except Exception:
        return []


def _live_prices(syms):
    """اسعار لحظية للمراكز المفتوحة."""
    if not syms:
        return {}
    import json as _j
    import urllib.request as _u
    out = {}
    try:
        d = _j.load(_u.urlopen(
            "https://fapi.binance.com/fapi/v1/ticker/price", timeout=8))
        want = set(syms)
        for x in d:
            if x.get("symbol") in want:
                out[x["symbol"]] = float(x.get("price") or 0)
    except Exception as e:
        log.debug("live prices: %s", e)
    return out


def ledger(user_id, days=30, market=""):
    since = int(time.time()) - days * 86400
    c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    c.row_factory = sqlite3.Row
    q = "SELECT * FROM user_trades WHERE user_id=? AND opened_at >= ?"
    a = [user_id, since]
    if market:
        q += " AND market=?"
        a.append(market)
    rows = [dict(r) for r in c.execute(q, a)]
    c.close()
    open_ = sorted([r for r in rows if not r.get("closed_at")],
                   key=lambda x: -(x.get("opened_at") or 0))
    closed = sorted([r for r in rows if r.get("closed_at")],
                    key=lambda x: -(x.get("closed_at") or 0))
    dm = {}
    for r in closed:
        dm.setdefault(_day_key(r["closed_at"]), []).append(r)
    out_days = [{"date": k, "metrics": _metrics(dm[k]),
                 "trades": [_slim(x) for x in dm[k]]}
                for k in sorted(dm, reverse=True)]
    # 📡 السعر الحيّ للمفتوحة + الربح اللحظي
    live = _live_prices([r["symbol"] for r in open_])
    op = []
    for r in open_:
        d = _slim(r, True)
        px = live.get(r["symbol"])
        if px and float(r.get("entry") or 0) > 0:
            e = float(r["entry"])
            lev = float(r.get("leverage") or 1)
            sg = 1.0 if str(r.get("direction", "")).upper() == "LONG" else -1.0
            d["live_price"] = px
            d["live_pnl_pct"] = round((px - e) / e * 100 * lev * sg, 2)
            d["live_pnl_usdt"] = round((px - e) * float(r.get("qty") or 0) * sg, 2)
        op.append(d)

    return {"user_id": user_id, "overall": _metrics(closed),
            "open": op, "days": out_days,
            "markets_enabled": _enabled(user_id),
            "generated_at": int(time.time())}


@router.get("/user/{user_id}/ledger")
async def user_ledger(user_id: str, days: int = 30, market: str = ""):
    try:
        return ledger(user_id, days, market)
    except Exception as e:
        log.error("ledger %s: %s", user_id, e)
        return {"error": str(e)[:120], "overall": {}, "open": [], "days": []}
