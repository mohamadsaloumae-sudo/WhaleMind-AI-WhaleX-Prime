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
        if price > 0:
            _price_cache[symbol] = price; _price_ts[symbol] = now
            return price
    except Exception:
        pass
    return _price_cache.get(symbol, 0.0)  # آخر سعر معروف — لا صفر أبداً


@router.get("/radar-positions")
async def radar_positions(market: str = "futures"):
    if market == "spot":
        return {"positions": []}  # المرحلة 2: مدير سبوت منفصل
    """صفقات الرادارات المفتوحة — للمشاهدة فقط."""
    out = []
    try:
        conn = sqlite3.connect(POS_DB)
        rows = conn.execute("SELECT data FROM active_positions WHERE status='open'").fetchall()
        conn.close()
    except Exception as e:
        log.debug("radar db: %s", e)
        return {"positions": []}

    for (data,) in rows:
        try:
            d = json.loads(data)
            symbol = d.get("symbol")
            entry = float(d.get("entry", 0))
            direction = d.get("direction", "")
            leverage = float(d.get("leverage", 1))
            if not symbol or entry <= 0:
                continue
            cur = await _get_price(symbol)
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
