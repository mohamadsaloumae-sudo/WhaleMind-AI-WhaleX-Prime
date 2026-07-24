"""⚡ تيار أسعار الفيوتشر الحي — WebSocket فقط، صفر REST، صفر حظر."""
import asyncio
import json
import time
import logging

log = logging.getLogger("price_stream")

WS_URL = "wss://fstream.binance.com/ws/!ticker@arr"
_TICK: dict = {}   # symbol -> (price, change_pct_24h, quote_vol_24h, ts)


async def price_stream_loop():
    while True:
        try:
            import websockets
            async with websockets.connect(WS_URL, ping_interval=20, close_timeout=5) as ws:
                log.info("⚡🔌 Futures price WS connected")
                async for msg in ws:
                    try:
                        data = json.loads(msg)
                        now = time.time()
                        for t in (data if isinstance(data, list) else [data]):
                            s = t.get("s")
                            c = t.get("c")
                            if s and c:
                                _TICK[s] = (float(c), float(t.get("P") or 0), float(t.get("q") or 0), now)
                    except Exception:
                        pass
        except Exception as e:
            log.warning("⚡🔌 Futures WS drop: %s", e)
        await asyncio.sleep(5)


def get_price(symbol: str, max_age: float = 15.0):
    """سعر حيّ فقط — لا كاش قديم."""
    v = _TICK.get(symbol)
    if v and (time.time() - v[3]) <= max_age:
        return v[0]
    return None


def get_all_tickers(max_age: float = 60.0):
    """كل الأزواج بصيغة ticker/24hr — للفرز بلا REST."""
    now = time.time()
    return [{"symbol": s, "lastPrice": str(v[0]), "priceChangePercent": str(v[1]), "quoteVolume": str(v[2])}
            for s, v in _TICK.items() if (now - v[3]) <= max_age]


def stream_size() -> int:
    return len(_TICK)
