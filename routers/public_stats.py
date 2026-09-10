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
    _ALL = []
    best = None
    try:
        from radars.futures.position_manager import get_price
        cn = sqlite3.connect("/opt/whalex/positions.db")
        rows = list(cn.execute(
            # 🛡️ نفس شرط صفحة الصفقات حرفياً — كان status!='closed'
            #    فيعرض اي صفّ بحالة ثالثة (فارغة/pending) كصفقة شبحية
            #    لا وجود لها في صفحة المفتوحة. وقيد اليوم يمنع العوالق.
            "SELECT data FROM active_positions WHERE status='open' "
            # ⚠️ CAST ضروريّ: opened_at رقم وstrftime نصّ،
            #    وSQLite يرتّب INTEGER < TEXT دائماً فلا يتحقّق الشرط.
            "AND json_extract(data,'$.opened_at') > "
            "CAST(strftime('%s','now','-24 hours') AS INTEGER)"))
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
            if True:
                try:
                    from services.binance_trader import symbol_exchange
                    ex = symbol_exchange(sym)
                except Exception:
                    ex = "binance"
                _ALL.append({"system": "Futures", "system_icon": "⚡",
                        "symbol": sym, "direction": j.get("direction"),
                        "entry": ent, "current": px, "pnl_pct": pnl,
                        "leverage": lev, "exchange": ex,
                        "tp1": j.get("tp1"), "sl": j.get("sl"),
                        "opened_at": j.get("opened_at")})
    except Exception as e:
        log.debug("showcase: %s", e)

    # 🪙 السبوت — كانت الشاشة تعرض الفيوتشر وحده، فتختفي كلّياً
    #    حين لا توجد صفقة فيوتشر مفتوحة رغم وجود صفقات في نظامين
    #    آخرين. وكل مصدر داخل try مستقلّ فلا يُسقط أحدهما الباقي.
    try:
        from radars.futures.position_manager import get_price as _gp
        cs = sqlite3.connect("/opt/whalex/db/whalex.db")
        cs.row_factory = sqlite3.Row
        _sp = [dict(x) for x in cs.execute(
            # 🪙 المصدر الحيّ هو signals — وspot_positions_multi
            #    متوقّف منذ 1 سبتمبر فلا يعرض السبوت ابداً.
            "SELECT symbol, entry FROM signals "
            "WHERE radar_type='spot' AND is_active=1 AND entry>0 "
            "AND created_at > CAST(strftime('%s','now','-24 hours') AS INTEGER) "
            "LIMIT 12")]
        cs.close()
        _seen = set()
        for _r in _sp:
            _sy = _r["symbol"]
            if _sy in _seen:
                continue
            _seen.add(_sy)
            _e = float(_r["entry"] or 0)
            _px = await _gp(_sy)
            if not _px or _px <= 0 or _e <= 0:
                continue
            _p = round((_px - _e) / _e * 100, 2)
            if True:
                _ALL.append({"system": "Spot", "system_icon": "🪙",
                        "symbol": _sy, "direction": "LONG",
                        "entry": _e, "current": _px, "pnl_pct": _p,
                        "leverage": 1.0, "exchange": "binance",
                        "tp1": None, "sl": None, "opened_at": None})
    except Exception as e:
        log.debug("showcase spot: %s", e)

    # 🐸 الميم — الجدول يحمل pnl_pct محسوباً فلا نحتاج سعراً حياً
    try:
        cm = sqlite3.connect("/opt/whalex/db/memecoin.db")
        cm.row_factory = sqlite3.Row
        _mm = [dict(x) for x in cm.execute(
            "SELECT symbol, entry_price, last_price, pnl_pct, ts "
            "FROM meme_signals WHERE status='open' "
            "ORDER BY pnl_pct DESC LIMIT 5")]
        cm.close()
        for _r in _mm:
            _p = _r["pnl_pct"]
            if _p is None:
                _e0 = float(_r["entry_price"] or 0)
                _l0 = float(_r["last_price"] or 0)
                if _e0 <= 0 or _l0 <= 0:
                    continue
                _p = (_l0 - _e0) / _e0 * 100
            _p = round(float(_p), 2)
            if True:
                _ALL.append({"system": "Meme", "system_icon": "🐸",
                        "symbol": _r["symbol"], "direction": "LONG",
                        "entry": _r["entry_price"],
                        "current": _r["last_price"], "pnl_pct": _p,
                        "leverage": 1.0, "exchange": "dex",
                        "tp1": None, "sl": None, "opened_at": _r["ts"]})
    except Exception as e:
        log.debug("showcase meme: %s", e)

    # 🎬 كل المفتوحة الحيّة من الانظمة الثلاثة مرتّبة بالاعلى ربحاً.
    #    بلا احتياط وبلا مغلقة — الواجهة تتنقّل بينها كل 8 ثوانٍ،
    #    وتختفي البطاقة اذا لم توجد صفقة مفتوحة اطلاقاً.
    _ALL.sort(key=lambda z: float(z.get("pnl_pct") or 0), reverse=True)
    out = dict(_ALL[0]) if _ALL else {}
    out["positions"] = _ALL
    _CACHE["w"] = (out, time.time())
    return out
