"""🪙👁️ عيون السبوت — تقرأ من منصّة كل عملة لا من باينانس.

مقيس: COREUSDT على أوكي إكس تُرجع None من باينانس (لا قرار)،
وFILUSDT: باينانس 0.535 «أبقِ» بينما أوكي إكس 0.209 «اقطع» — قراران متضادّان.
والسبوت كان بلا بوّابة انقلاب أصلاً (الفيوتشر عنده دفتر 100 مستوى).
"""
import asyncio, logging, sqlite3, time
log = logging.getLogger("spot_eyes")
UNIVERSE_DB = "/opt/whalex/spot_universe.db"
_CLIENTS = {}; _EX_MAP = {"map": {}, "ts": 0.0}
_FLOW_CACHE = {}; _OB_CACHE = {}; _WARN = {}
FLOW_TTL = 45.0
OB_TTL = 20.0

def exchange_of(symbol: str) -> str:
    if time.time() - _EX_MAP["ts"] > 300:
        try:
            c = sqlite3.connect(UNIVERSE_DB)
            _EX_MAP["map"] = {r[0]: (r[1], r[2]) for r in c.execute(
                "SELECT symbol,exchange,ccxt_symbol FROM spot_universe")}
            c.close(); _EX_MAP["ts"] = time.time()
        except Exception as e:
            log.debug("ex map: %s", e)
    return (_EX_MAP["map"].get(symbol) or ("binance", None))[0]

def _pair(symbol: str):
    exchange_of(symbol)
    hit = _EX_MAP["map"].get(symbol)
    if hit and hit[1]: return hit[0], hit[1]
    base = symbol[:-4] if symbol.upper().endswith("USDT") else symbol
    return (hit[0] if hit else "binance"), f"{base}/USDT"

def _client(ex: str):
    c = _CLIENTS.get(ex)
    if c is None:
        import ccxt
        opts = {"defaultType": "spot"}
        if ex == "okx": opts["fetchMarkets"] = ["spot"]
        c = getattr(ccxt, ex)({"enableRateLimit": True, "timeout": 20000, "options": opts})
        _CLIENTS[ex] = c
    return c

def _flow_sync(ex: str, sym: str) -> float:
    tr = _client(ex).fetch_trades(sym, limit=500) or []
    if len(tr) < 30: return -1.0
    buy = tot = 0.0
    for t in tr:
        a = float(t.get("amount") or 0)
        if a <= 0: continue
        tot += a
        if (t.get("side") or "").lower() == "buy": buy += a
    return (buy / tot) if tot > 0 else -1.0

async def taker_flow(symbol: str):
    ex, sym = _pair(symbol); k = f"{ex}:{sym}"
    c = _FLOW_CACHE.get(k)
    if c and time.time() - c[0] < FLOW_TTL: return c[1]
    try:
        v = await asyncio.to_thread(_flow_sync, ex, sym)
        v = None if v < 0 else v
        _FLOW_CACHE[k] = (time.time(), v)
        return v
    except Exception as e:
        log.debug("flow %s/%s: %s", ex, sym, e); return None

def _ob_sync(ex: str, sym: str, limit: int = 100):
    ob = _client(ex).fetch_order_book(sym, limit=limit)
    return {"bids": ob.get("bids") or [], "asks": ob.get("asks") or []}

async def order_book(symbol: str):
    ex, sym = _pair(symbol); k = f"{ex}:{sym}"
    c = _OB_CACHE.get(k)
    if c and time.time() - c[0] < OB_TTL: return c[1]
    try:
        ob = await asyncio.to_thread(_ob_sync, ex, sym, 100)
        if not ob["bids"] or not ob["asks"]: return None
        _OB_CACHE[k] = (time.time(), ob); return ob
    except Exception as e:
        log.debug("ob %s/%s: %s", ex, sym, e); return None

def _analyse(ob: dict) -> dict:
    bids, asks = ob["bids"], ob["asks"]
    mid = (float(bids[0][0]) + float(asks[0][0])) / 2 if bids and asks else 0
    if mid <= 0: return {}
    # 🛡️ أوكي إكس تُرجع [سعر, كمية, تصفيات] وباي بيت [سعر, كمية] —
    #    ففكّ عنصرين ينهار عليها. نأخذ أول اثنين مهما كان الطول.
    def _lv(rows):
        return [(float(r[0]), float(r[1])) for r in rows if len(r) >= 2]
    _b, _a = _lv(bids), _lv(asks)
    nb = sum(p * q for p, q in _b[:10])
    na = sum(p * q for p, q in _a[:10])
    db = sum(p * q for p, q in _b)
    da = sum(p * q for p, q in _a)
    near = ((nb-na)/(nb+na)) if (nb+na) else 0
    deep = ((db-da)/(db+da)) if (db+da) else 0
    av = [p * q for p, q in _a[:40]]
    aavg = (sum(av)/len(av)) if av else 0
    wall = (max(av)/aavg) if aavg > 0 else 0
    return {"near_imb": near, "deep_imb": deep, "sell_wall": wall, "mid": mid}

async def is_reversal(symbol: str, pnl_pct: float = 0.0):
    """انقلاب بنيويّ ضدّ الشراء — لا خروج للتذبذب، تأكيد بقراءتين."""
    ob = await order_book(symbol)
    if not ob: return False, ""
    a = _analyse(ob)
    if not a: return False, ""
    near, deep, wall = a["near_imb"], a["deep_imb"], a["sell_wall"]
    thr = -0.30 if pnl_pct < 0 else -0.22
    hit = near <= thr and deep <= -0.10
    strong = near <= thr - 0.15 or wall >= 6.0
    k = f"sp:{symbol}"
    if hit:
        if strong or _WARN.pop(k, None):
            why = (f"انقلاب دفتر: قرب {near*100:+.0f}% · عمق {deep*100:+.0f}%"
                   + (f" · جدار بيع x{wall:.1f}" if wall >= 4 else ""))
            return True, why
        _WARN[k] = time.time(); return False, ""
    _WARN.pop(k, None)
    return False, ""
