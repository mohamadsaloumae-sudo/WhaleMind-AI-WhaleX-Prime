"""🪙🔭 ماسح السبوت — سبع منصّات.

يقرأ الكون من spot_universe.db ويجلب شموع كل عملة من منصّتها هي
لا من باينانس دائماً. القرار كلّه في logic_spot — هذا نقل بيانات فقط.
"""
import asyncio, logging, time
log = logging.getLogger("spot_scan")
TF = "4h"
LIMIT = 60
CONCURRENCY = 6
_ex_cache = {}

def _client(ex_name: str):
    if ex_name in _ex_cache: return _ex_cache[ex_name]
    import ccxt
    e = getattr(ccxt, ex_name)({"enableRateLimit": True, "timeout": 20000,
                                "options": {"defaultType": "spot"}})
    _ex_cache[ex_name] = e
    return e

def _fetch_sync(ex_name: str, ccxt_symbol: str):
    try:
        e = _client(ex_name)
        ohlcv = e.fetch_ohlcv(ccxt_symbol, timeframe=TF, limit=LIMIT)
        if not ohlcv or len(ohlcv) < 50: return None
        book = {}
        try:
            ob = e.fetch_order_book(ccxt_symbol, limit=50)
            bids = ob.get("bids") or []; asks = ob.get("asks") or []
            if bids and asks:
                bv = sum(p*q for p,q in bids[:20]); av = sum(p*q for p,q in asks[:20])
                if bv+av > 0: book["imb"] = (bv-av)/(bv+av)
                lv = [p*q for p,q in bids[:50]]
                if lv:
                    avg = sum(lv)/len(lv)
                    book["wall"] = bool(avg > 0 and max(lv) >= avg*2.2)
        except Exception:
            pass
        return {"ohlcv": ohlcv, "book": book}
    except Exception as e:
        log.debug("🪙 fetch %s/%s: %s", ex_name, ccxt_symbol, e)
        return None

async def analyse(symbol: str, ex_name: str, ccxt_symbol: str) -> dict:
    from radars.spot.logic_spot import evaluate
    data = await asyncio.to_thread(_fetch_sync, ex_name, ccxt_symbol)
    if not data: return {"ok": False, "reason": "لا بيانات"}
    k = data["ohlcv"]
    closes = [float(x[4]) for x in k]; highs = [float(x[2]) for x in k]
    lows = [float(x[3]) for x in k];   vols  = [float(x[5]) for x in k]
    tbuys = []
    for i, x in enumerate(k):
        hi, lo_, cl = float(x[2]), float(x[3]), float(x[4])
        rngc = hi - lo_
        frac = ((cl-lo_)/rngc) if rngc > 0 else 0.5
        tbuys.append(vols[i]*max(0.15, min(0.85, frac)))
    res = evaluate(closes, highs, lows, vols, tbuys, data["book"])
    res["symbol"] = symbol; res["exchange"] = ex_name; res["ccxt_symbol"] = ccxt_symbol
    return res

async def scan_universe(rows: list, on_signal=None, cooldown: dict = None,
                        cooldown_sec: int = 4*3600) -> dict:
    cooldown = cooldown if cooldown is not None else {}
    now = time.time()
    stats = {"checked":0,"no_data":0,"cooldown":0,"no_path":0,
             "low_score":0,"hot":0,"signals":0}
    by_path = {}
    sem = asyncio.Semaphore(CONCURRENCY)
    async def one(sym, ex, ck):
        if now - cooldown.get(sym, 0) < cooldown_sec:
            stats["cooldown"] += 1; return
        async with sem:
            r = await analyse(sym, ex, ck)
        stats["checked"] += 1
        if r.get("ok"):
            stats["signals"] += 1
            p = r.get("path","?"); by_path[p] = by_path.get(p,0)+1
            cooldown[sym] = time.time()
            if on_signal:
                try: await on_signal(r)
                except Exception as e: log.error("🪙 on_signal %s: %s", sym, e)
            return
        why = str(r.get("reason",""))
        if "لا بيانات" in why: stats["no_data"] += 1
        elif "محموم" in why: stats["hot"] += 1
        elif "نقاط" in why: stats["low_score"] += 1
        else: stats["no_path"] += 1
    await asyncio.gather(*[one(s,e,c) for s,e,c,_v in rows])
    log.info("🪙🔎 فُحص %d | بلا داتا %d | تبريد %d | لا مسار %d | نقاط %d | محموم %d | إشارات %d %s",
             stats["checked"], stats["no_data"], stats["cooldown"], stats["no_path"],
             stats["low_score"], stats["hot"], stats["signals"], by_path or "")
    return stats
