"""📊 أرقام عامّة لصفحة المقدّمة — بلا مصادقة، بلا بيانات مستخدمين."""
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

router = APIRouter(prefix="/api/public", tags=["public"])
log = logging.getLogger("public_stats")

_CACHE: dict = {}
TTL = 60.0


def _month_start() -> int:
    now = datetime.now(timezone(timedelta(hours=4)))
    return int(now.replace(day=1, hour=0, minute=0, second=0,
                           microsecond=0).timestamp())


@router.get("/stats")
async def stats():
    """صافي الشهر · عدد الصفقات · حجم التغطية."""
    c = _CACHE.get("s")
    if c and time.time() - c[1] < TTL:
        return c[0]
    out = {"net_month": 0.0, "trades_month": 0, "coins": 0,
           "exchanges": 7, "live_positions": 0}
    try:
        # 🎯 نفس استعلام صفحة الصفقات حرفياً — رقمان مختلفان يهدمان الثقة.
        #    الفرق كان: result IN ('win','loss') يستثني غير المكتملة.
        # 📊 من المصدر الموحَّد — لا استعلام محلّيّ
        from services.stats_core import summary as _sm
        _s = _sm('futures', 'month')
        # 🔢 العدد من total_trades لا من طول القائمة — كانت
        #    v = [net_pct] فيعطي len(v)=1 دائماً مهما بلغ العدد.
        #    مقيس 5 سبتمبر: 78 صفقة اليوم والعدّاد يعرض 1.
        if _s.get('total_trades'):
            out["net_month"] = round(float(_s['net_pct']), 1)
            out["trades_month"] = int(_s['total_trades'])
    except Exception as e:
        log.debug("stats month: %s", e)
    try:
        a = sqlite3.connect("/opt/whalex/coin_profiles.db").execute(
            "SELECT COUNT(*) FROM coin_profiles").fetchone()[0]
        b = sqlite3.connect("/opt/whalex/multi_universe.db").execute(
            "SELECT COUNT(*) FROM universe").fetchone()[0]
        out["coins"] = int(a) + int(b)
    except Exception as e:
        log.debug("stats coins: %s", e)
    try:
        out["live_positions"] = sqlite3.connect(
            "/opt/whalex/positions.db").execute(
            "SELECT COUNT(*) FROM active_positions "
            "WHERE status!='closed'").fetchone()[0]
    except Exception as e:
        log.debug("stats live: %s", e)
    # 📊 الأنظمة الثلاثة — إضافة لا تمسّ الحقول القديمة.
    #    كانت الصفحة تعرض الفيوتشر وحده فلا يرى الزائر السبوت والميم.
    try:
        from services.stats_core import summary as _sm2
        _sys = {}
        for _k, _nm in (("futures", "Futures"), ("spot", "Spot"),
                        ("meme", "Meme")):
            _d = _sm2(_k, "month")
            _sys[_k] = {
                "name": _nm,
                "trades": int(_d.get("total_trades") or 0),
                "wins": int(_d.get("wins_count") or 0),
                "losses": int(_d.get("losses_count") or 0),
                "win_rate": float(_d.get("win_rate") or 0.0),
                "net_pct": round(float(_d.get("net_pct") or 0.0), 1),
            }
        out["systems"] = _sys
    except Exception as e:
        log.debug("stats systems: %s", e)
    _CACHE["s"] = (out, time.time())
    return out


@router.get("/showcase")
async def showcase():
    """أفضل صفقة مفتوحة الآن — دليل حيّ لا نموذج مزيّف."""
    c = _CACHE.get("w")
    if c and time.time() - c[1] < 6:
        return c[0]
    best = None
    try:
        from radars.futures.position_manager import get_price
        cn = sqlite3.connect("/opt/whalex/positions.db")
        rows = list(cn.execute(
            "SELECT data FROM active_positions WHERE status!='closed'"))
        cn.close()
        for (d,) in rows:
            try:
                j = json.loads(d)
            except Exception:
                continue
            sym, ent = j.get("symbol"), float(j.get("entry") or 0)
            if not sym or ent <= 0:
                continue
            px = await get_price(sym)
            if not px or px <= 0:
                continue
            lev = float(j.get("leverage") or 1)
            mv = ((px - ent) / ent) if j.get("direction") == "LONG" \
                else ((ent - px) / ent)
            pnl = round(mv * 100 * lev, 2)
            if best is None or pnl > best["pnl_pct"]:
                try:
                    from services.binance_trader import symbol_exchange
                    ex = symbol_exchange(sym)
                except Exception:
                    ex = "binance"
                best = {"symbol": sym, "direction": j.get("direction"),
                        "entry": ent, "current": px, "pnl_pct": pnl,
                        "leverage": lev, "exchange": ex,
                        "tp1": j.get("tp1"), "sl": j.get("sl"),
                        "opened_at": j.get("opened_at")}
    except Exception as e:
        log.debug("showcase: %s", e)
    out = best or {}
    _CACHE["w"] = (out, time.time())
    return out
