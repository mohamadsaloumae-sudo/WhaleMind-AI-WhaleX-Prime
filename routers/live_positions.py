"""
WhaleMind — Live Positions Router
مسارات العرض الحيّ للصفقات المفتوحة:
  GET /api/live/radar-positions   — صفقات الرادارات (مشاهدة فقط، سعر حيّ + PnL)
  GET /api/live/binance-positions — صفقات Binance الحقيقية (حيّة + قابلة للإغلاق)
"""
from fastapi import APIRouter, Depends
import sqlite3, json, logging, time
import httpx

from routers.auth import get_current_user

log = logging.getLogger("live_positions")
router = APIRouter(prefix="/api/live", tags=["Live Positions"])

POS_DB = "/opt/whalex/positions.db"
_price_cache = {}
_price_ts = {}


def _sym_ex(symbol: str) -> str:
    """منصّة العملة — للشارت. الحصرية على منصّاتها والباقي باينانس."""
    try:
        from services.binance_trader import symbol_exchange
        return symbol_exchange(symbol)
    except Exception:
        return "binance"


async def _get_price(symbol: str) -> float:
    """سعر حيّ من Binance Futures (عام، بلا مفاتيح) — كاش ثانية واحدة."""
    # 🌐 منصّة الصفقة أولاً — قبل بثّ باينانس.
    #    دليل OPENAIUSDT: بثّ باينانس يُرجع 1240 (عقد آخر) وGate 1167.
    #    فلو سألنا البثّ أولاً لرجع سعر صحيح لعقد خاطئ.
    try:
        _ex0 = _sym_ex(symbol)
        if _ex0 and str(_ex0).lower() != "binance":
            from radars.futures.position_manager import get_price as _mxp0
            _p0 = await _mxp0(symbol)
            if _p0 and _p0 > 0:
                _price_cache[symbol] = float(_p0)
                _price_ts[symbol] = time.time()
                return float(_p0)
    except Exception as _e0:
        log.debug("🌐 منصّة %s: %s", symbol, _e0)

    # 🌊 الستريم — لعملات باينانس فقط
    try:
        from quant_engine.ob_stream import get_price as _wsp
        _wp = _wsp(symbol)
        if _wp and _wp > 0:
            _price_cache[symbol] = _wp; _price_ts[symbol] = time.time()
            return _wp
    except Exception:
        pass
    now = time.time()
    # ⚡ 3 ثوانٍ فقط — 30 كانت تُظهر سعراً عمره نصف دقيقة (هذه أموال)
    if symbol in _price_cache and (now - _price_ts.get(symbol, 0)) < 3.0:
        return _price_cache[symbol]

    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}")
            price = float(r.json().get("price", 0))
        # 🌐 عملة حصرية على منصّة أخرى؟ سعرها من منصّتها لا من باينانس.
        #    درس NESAUSDT: باينانس ترجع Invalid symbol → 0 → ±500% وهمية في الواجهة.
        if price <= 0:
            try:
                from radars.futures.position_manager import get_price as _mxp
                _p = await _mxp(symbol)
                if _p and _p > 0:
                    price = float(_p)
            except Exception as _e:
                log.debug("🌐 سعر %s: %s", symbol, _e)
        if price > 0:
            _price_cache[symbol] = price; _price_ts[symbol] = now
            return price
    except Exception:
        pass
    return _price_cache.get(symbol, 0.0)  # آخر سعر معروف — لا صفر أبداً


_SPOT_EX_CACHE = {"map": {}, "ts": 0.0}


def _spot_ex(symbol: str) -> str:
    """🌐 منصّة عملة السبوت — لا باينانس دائماً."""
    import sqlite3 as _sq, time as _t
    if _t.time() - _SPOT_EX_CACHE["ts"] > 300:
        try:
            c = _sq.connect("/opt/whalex/spot_universe.db")
            _SPOT_EX_CACHE["map"] = {r[0]: r[1] for r in
                                     c.execute("SELECT symbol,exchange FROM spot_universe")}
            c.close()
            _SPOT_EX_CACHE["ts"] = _t.time()
        except Exception:
            pass
    return _SPOT_EX_CACHE["map"].get(symbol, "binance")


@router.get("/price-bench")
async def price_bench():
    """⏱️ قياس زمن جلب السعر لكل صفقة — من داخل الخدمة."""
    import json, sqlite3, time
    from radars.futures.position_manager import get_price as _gp
    out = []
    cn = sqlite3.connect("/opt/whalex/positions.db")
    for (d,) in cn.execute("SELECT data FROM active_positions WHERE status!='closed'"):
        try:
            sym = json.loads(d).get("symbol")
        except Exception:
            continue
        if not sym:
            continue
        t0 = time.time()
        p = await _gp(sym)
        out.append({"symbol": sym, "ms": round((time.time() - t0) * 1000, 1), "price": p})
    cn.close()
    out.sort(key=lambda x: -x["ms"])
    return {"total_ms": round(sum(x["ms"] for x in out), 1), "slowest": out[:8]}


@router.get("/mem-diag")
async def mem_diag():
    """🔬 تشخيص الذاكرة — أكثر الكائنات عدداً في العمليّة الحيّة."""
    import gc
    from collections import Counter
    gc.collect()
    objs = gc.get_objects()
    c = Counter(type(o).__name__ for o in objs)
    big = []
    for o in objs:
        try:
            if isinstance(o, dict) and len(o) > 2000:
                big.append(("dict", len(o)))
            elif isinstance(o, (list, set)) and len(o) > 5000:
                big.append((type(o).__name__, len(o)))
        except Exception:
            pass
    big.sort(key=lambda x: -x[1])
    import resource
    return {
        "rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
        "objects": len(objs),
        "top_types": c.most_common(14),
        "big_containers": big[:14],
    }


@router.get("/stream-health")
async def stream_health():
    """⚡ صحّة بثّ الأسعار — من داخل عملية الخدمة."""
    try:
        from radars.multi.price_stream import stream_health as _sh
        return _sh()
    except Exception as e:
        return {"error": str(e)}


@router.get("/radar-positions")
async def radar_positions(market: str = "futures"):
    if market == "meme":
        import sqlite3 as _sq, os as _os, time as _tm
        _mdb = _os.path.join(_os.path.dirname(__file__), "..", "db", "memecoin.db")
        try:
            _mc = _sq.connect(_mdb); _mc.row_factory = _sq.Row
            _rows = _mc.execute("SELECT id,symbol,chain,score,entry_price,last_price,peak_price,ts,url FROM meme_signals WHERE status='open' AND entry_price>0 ORDER BY ts DESC").fetchall()
            _mc.close()
            _out = []
            for _r in _rows:
                _d = dict(_r)
                _e = _d.get("entry_price") or 0
                _l = _d.get("last_price") or _e
                _pk = _d.get("peak_price") or _e
                _d["pnl_pct"] = round((_l - _e) / _e * 100, 2) if _e else 0
                _d["peak_pnl"] = round((_pk - _e) / _e * 100, 2) if _e else 0
                _d["age_min"] = int((_tm.time() - (_d.get("ts") or 0)) / 60)
                _out.append(_d)
            return {"positions": _out}
        except Exception:
            return {"positions": []}
    if market == "spot":
        try:
            from db.database import get_session, Signal
            from radars.spot.scout_spot import _prices
            db = get_session()
            try:
                sigs = db.query(Signal).filter(Signal.radar_type == "spot",
                                               Signal.is_active == True).order_by(Signal.created_at.desc()).all()
                out = []
                for s in sigs:
                    px = _prices.get(s.symbol) or s.entry or 0
                    pnl = (px - s.entry) / s.entry * 100 if s.entry else 0.0
                    out.append({"symbol": s.symbol, "direction": "LONG", "leverage": 1,
                                # 📊 الشارت يحتاجها: سبوت بلا لاحقة .P · والمستويات
                                "radar_type": "spot", "tier": "SPOT", "exchange": _spot_ex(s.symbol),
                                "sl": getattr(s, "sl", None), "tp1": getattr(s, "tp1", None),
                                "tp2": getattr(s, "tp2", None), "tp3": getattr(s, "tp3", None),
                                "radar": "WhaleX Spot 🪙", "entry": s.entry, "current": px,
                                "pnl_pct": round(pnl, 2),
                                "opened_at": int(s.created_at.timestamp()) if s.created_at else 0})
                # 🕐 الأقدم أعلى — ترتيب زمنيّ موحَّد في كل الصفحات
                try:
                    out.sort(key=lambda x: float(
                        x.get("opened_at") or x.get("ts") or 0), reverse=True)
                except Exception:
                    pass
                return {"positions": out}
            finally:
                db.close()
        except Exception:
            return {"positions": []}
    """صفقات الرادارات المفتوحة — للمشاهدة فقط."""
    out = []
    try:
        conn = sqlite3.connect(POS_DB)
        rows = conn.execute("SELECT data FROM active_positions WHERE status='open'").fetchall()
        conn.close()
    except Exception as e:
        log.debug("radar db: %s", e)
        return {"positions": []}

    # ⚡ نُسخّن الأسعار معاً أولاً — الحلقة تبقى كما هي بلا تغيير سلوكي
    _prices = {}
    try:
        _syms = []
        for (_dd,) in rows:
            try:
                _j = json.loads(_dd)
                if _j.get("symbol"):
                    _syms.append(_j["symbol"])
            except Exception:
                pass
        _syms = list(dict.fromkeys(_syms))
        if _syms:
            _rr = await asyncio.gather(*[_get_price(s) for s in _syms],
                                       return_exceptions=True)
            for _s, _p in zip(_syms, _rr):
                if isinstance(_p, (int, float)) and _p > 0:
                    _prices[_s] = _p
    except Exception as _e:
        log.debug("تسخين الأسعار: %s", _e)

    for (data,) in rows:
        try:
            d = json.loads(data)
            symbol = d.get("symbol")
            entry = float(d.get("entry", 0))
            direction = d.get("direction", "")
            leverage = float(d.get("leverage", 1))
            if not symbol or entry <= 0:
                continue
            cur = _prices.get(symbol) or await _get_price(symbol)
            if direction == "LONG":
                pnl = (cur - entry) / entry * 100 * leverage
            else:
                pnl = (entry - cur) / entry * 100 * leverage
            out.append({
                "symbol": symbol, "direction": direction,
                "entry": entry, "current": cur,
                "pnl_pct": round(pnl, 2), "leverage": leverage,
                "tp1_hit": d.get("tp1_hit", False),
                "opened_at": d.get("opened_at", 0),
                "radar_type": d.get("radar_type", "futures"),
                "tier": d.get("tier", ""),
                # 📊 منصّة العملة — يحتاجها الشارت لبناء رمز TradingView الصحيح
                "exchange": _sym_ex(symbol),
                # 📊 المستويات — يعرضها الشارت أسفله
                "sl": d.get("sl"), "tp1": d.get("tp1"),
                "tp2": d.get("tp2"), "tp3": d.get("tp3"),
            })
        except Exception as e:
            log.debug("radar parse: %s", e)
            continue
    # 🕐 الأقدم أعلى — ترتيب زمنيّ موحَّد في كل الصفحات
    try:
        out.sort(key=lambda x: float(
            x.get("opened_at") or x.get("ts") or 0), reverse=True)
    except Exception:
        pass
    return {"positions": out}


@router.get("/my-spot-positions")
async def my_spot_positions(user=Depends(get_current_user)):
    """صفقات السبوت الحقيقية لهذا المشترك — من منصّته هو.

    كانت صفحة الصفقات تعرض صفقات النظام الداخلية للجميع، فيرى
    المشترك عملة لا يملكها. ونظامنا حقيقيّ: ما يُعرض هنا هو ما
    اشتراه فعلاً وما زال في محفظته.
    """
    import sqlite3 as _sq
    uid = user["sub"]
    out = []
    try:
        cx = _sq.connect("/opt/whalex/db/whalex.db"); cx.row_factory = _sq.Row
        rows = [dict(r) for r in cx.execute(
            "SELECT * FROM spot_positions_multi WHERE user_id=? AND status='open'",
            (uid,))]
        cx.close()
    except Exception as e:
        log.debug("my spot: %s", e)
        return {"positions": []}
    if not rows:
        return {"positions": []}
    try:
        from radars.spot.scout_spot import _prices as _spx
    except Exception:
        _spx = {}
    for r in rows:
        e = float(r.get("entry") or 0)
        px = float(_spx.get(r.get("symbol")) or 0) or e
        out.append({
            "symbol": r.get("symbol"),
            "direction": "LONG",
            "entry": e,
            "current": px,
            "leverage": 1,
            "size": r.get("qty"),
            "exchange": r.get("exchange"),
            "opened_at": r.get("ts"),
            "radar": "WhaleX Spot",
            "pnl_pct": round((px - e) / e * 100, 2) if e else 0,
        })
    # 🕐 الأقدم أعلى — ترتيب زمنيّ موحَّد في كل الصفحات
    try:
        out.sort(key=lambda x: float(
            x.get("opened_at") or x.get("ts") or 0), reverse=True)
    except Exception:
        pass
    return {"positions": out}


@router.get("/binance-positions")
async def binance_positions(user=Depends(get_current_user)):
    """صفقات Binance الحقيقية — حيّة + قابلة للإغلاق."""
    from services.binance_trader import get_credentials, get_open_positions
    uid = user["sub"]
    # 🔒 كان هنا: من ليس مربوطاً يُعطى user_id أوّل مشترك في القاعدة،
    #    فيرى صفقات غيره ورصيده. تسريب بيانات صريح — أُزيل.
    #    غير المربوط لا يرى شيئاً، وهذا الصواب.
    if not get_credentials(uid):
        return {"positions": [], "connected": False}
    out = []
    # 🛡️ الدالة ترمي عند فشل الاتّصال — الصفحة تعرض فارغاً لا تنكسر
    try:
        _pos_safe = get_open_positions(uid)
    except Exception:
        return {"positions": [], "connected": True, "error": "تعذّر الجلب"}
    # 📅 وقت الفتح من سجلّ المشترك — الصفحة تعرضه
    _opened = {}
    try:
        import sqlite3 as _sq3
        _cq = _sq3.connect("/opt/whalex/db/whalex.db")
        for _r in _cq.execute("SELECT symbol, opened_at FROM user_trades "
                              "WHERE user_id=? AND status='open'", (uid,)):
            _opened[_r[0]] = _r[1]
        _cq.close()
    except Exception:
        pass
    _enrich_open = _opened
    for p in _pos_safe:
        entry = p.get("entry_price", 0)
        mark = p.get("mark_price", 0)
        lev = p.get("leverage", 1)
        direction = p.get("direction", "")
        if entry > 0:
            if direction == "LONG":
                pnl = (mark - entry) / entry * 100 * lev
            else:
                pnl = (entry - mark) / entry * 100 * lev
        else:
            pnl = 0
        out.append({
            "symbol": p.get("symbol"), "direction": direction,
            "entry": entry, "current": mark,
            "pnl_pct": round(pnl, 2),
            "unrealized_pnl": p.get("unrealized_pnl", 0),
            "leverage": lev, "size": p.get("size", 0),
        })
    return {"positions": out, "connected": True}


# ═══════════════════════════════════════════════════════════════
# Subscriber's OWN positions - priced from THEIR fill, not radar
# ═══════════════════════════════════════════════════════════════
# Measured: entry slip 0.045% + exit slip 0.056% raw = 0.43% leveraged.
# On a trade near breakeven that flips +0.2% into -0.23%, so the app
# showed a win while Binance showed a loss. user_trades already holds
# each subscriber's real fill; nothing was reading it for display.
# Read-only. Does not touch radar-positions or any execution path.
@router.get("/my-positions")
async def my_positions(user=Depends(get_current_user)):
    import asyncio as _aio
    uid = user["sub"]
    out = []
    try:
        cx = sqlite3.connect("/opt/whalex/db/whalex.db")
        cx.row_factory = sqlite3.Row
        rows = [dict(r) for r in cx.execute(
            "SELECT symbol, direction, entry, qty, leverage, order_id, opened_at "
            "FROM user_trades WHERE user_id=? AND status='open' "
            "AND market='futures'", (uid,))]
        cx.close()
    except Exception as e:
        log.warning("my-positions db: %s", e)
        return {"positions": []}
    if not rows:
        return {"positions": []}
    _levels = {}
    try:
        cn = sqlite3.connect(POS_DB)
        for (data,) in cn.execute(
                "SELECT data FROM active_positions WHERE status='open'"):
            try:
                d = json.loads(data)
                if d.get("symbol"):
                    _levels[d["symbol"]] = d
            except Exception:
                pass
        cn.close()
    except Exception as e:
        log.debug("my-positions levels: %s", e)
    _syms = list(dict.fromkeys([r["symbol"] for r in rows if r.get("symbol")]))
    _prices = {}
    try:
        _rr = await _aio.gather(*[_get_price(s) for s in _syms],
                               return_exceptions=True)
        for _s, _p in zip(_syms, _rr):
            if isinstance(_p, (int, float)) and _p > 0:
                _prices[_s] = _p
    except Exception as e:
        log.debug("my-positions prices: %s", e)
    for r in rows:
        try:
            symbol = r.get("symbol")
            entry = float(r.get("entry") or 0)
            if not symbol or entry <= 0:
                continue
            direction = str(r.get("direction") or "").upper()
            lev = float(r.get("leverage") or 1)
            cur = float(_prices.get(symbol) or 0)
            if cur <= 0:
                cur = entry
            if direction == "LONG":
                pnl = (cur - entry) / entry * 100 * lev
            else:
                pnl = (entry - cur) / entry * 100 * lev
            _lv = _levels.get(symbol, {})
            out.append({
                "symbol": symbol, "direction": direction,
                "entry": entry, "current": cur,
                "pnl_pct": round(pnl, 2), "leverage": lev,
                "size": r.get("qty"), "order_id": r.get("order_id"),
                "opened_at": r.get("opened_at") or 0,
                "radar_type": _lv.get("radar_type", "futures"),
                "tier": _lv.get("tier", ""), "exchange": _sym_ex(symbol),
                "sl": _lv.get("sl"), "tp1": _lv.get("tp1"),
                "tp2": _lv.get("tp2"), "tp3": _lv.get("tp3"),
                "tp1_hit": _lv.get("tp1_hit", False),
            })
        except Exception as e:
            log.debug("my-positions row: %s", e)
            continue
    try:
        out.sort(key=lambda x: float(x.get("opened_at") or 0), reverse=True)
    except Exception:
        pass
    return {"positions": out}
