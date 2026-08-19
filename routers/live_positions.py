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


async def _get_price(symbol: str) -> float:
    """سعر حيّ من Binance Futures (عام، بلا مفاتيح) — كاش ثانية واحدة."""
    # 🌊 الستريم أولاً — صفر REST للعملات المبثوثة (كل الصفقات المفتوحة مبثوثة)
    try:
        from quant_engine.ob_stream import get_price as _wsp
        _wp = _wsp(symbol)
        if _wp and _wp > 0:
            _price_cache[symbol] = _wp; _price_ts[symbol] = time.time()
            return _wp
    except Exception:
        pass
    now = time.time()
    if symbol in _price_cache and (now - _price_ts.get(symbol, 0)) < 30.0:
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
                                "radar": "WhaleX Spot 🪙", "entry": s.entry, "current": px,
                                "pnl_pct": round(pnl, 2),
                                "opened_at": int(s.created_at.timestamp()) if s.created_at else 0})
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

    # ⚡ نجلب كل الأسعار معاً — بالتسلسل كانت 11 صفقة تستغرق 5 ثوانٍ
    _parsed = []
    for (data,) in rows:
        try:
            _d = json.loads(data)
            if _d.get("symbol") and float(_d.get("entry", 0)) > 0:
                _parsed.append(_d)
        except Exception:
            continue
    _prices = {}
    if _parsed:
        _syms = list({x["symbol"] for x in _parsed})
        _res = await asyncio.gather(*[_get_price(s) for s in _syms],
                                    return_exceptions=True)
        for _s, _p in zip(_syms, _res):
            _prices[_s] = _p if isinstance(_p, (int, float)) else 0.0

    for d in _parsed:
        try:
            symbol = d.get("symbol")
            entry = float(d.get("entry", 0))
            direction = d.get("direction", "")
            leverage = float(d.get("leverage", 1))
            cur = _prices.get(symbol) or 0.0
            if cur <= 0:
                continue
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
            })
        except Exception as e:
            log.debug("radar parse: %s", e)
            continue
    return {"positions": out}


@router.get("/binance-positions")
async def binance_positions(user=Depends(get_current_user)):
    """صفقات Binance الحقيقية — حيّة + قابلة للإغلاق."""
    from services.binance_trader import get_credentials, get_open_positions
    uid = user["sub"]
    if not get_credentials(uid):
        try:
            import sqlite3
            cx = sqlite3.connect("/opt/whalex/db/whalex.db")
            r = cx.execute("SELECT user_id FROM user_binance_credentials LIMIT 1").fetchone()
            cx.close()
            if r and r[0]: uid = r[0]
        except Exception: pass
    if not get_credentials(uid):
        return {"positions": [], "connected": False}
    out = []
    for p in get_open_positions(uid):
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
