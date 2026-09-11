import asyncio, logging
import httpx
from core.config import get_settings

log = logging.getLogger("prices")
PRICES = {}

async def fetch_all_symbols():
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://fapi.binance.com/fapi/v1/ticker/24hr")
            data = r.json()
            top = sorted(data, key=lambda x: float(x.get("quoteVolume",0)), reverse=True)
            return [x["symbol"] for x in top if x["symbol"].endswith("USDT")][:50]
    except:
        return ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","AVAXUSDT","ARBUSDT","DOGEUSDT","XRPUSDT","ADAUSDT","DOTUSDT"]

async def start_price_stream():
    symbols = await fetch_all_symbols()
    log.info("Fetching prices for %d symbols", len(symbols))
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get("https://fapi.binance.com/fapi/v1/ticker/24hr")
                for t in r.json():
                    if t["symbol"].endswith("USDT"):
                        PRICES[t["symbol"]] = {
                            "price": float(t["lastPrice"]),
                            "change": float(t["priceChangePercent"]),
                            "volume": float(t["quoteVolume"]),
                            "high": float(t["highPrice"]),
                            "low": float(t["lowPrice"]),
                        }
        except Exception as e:
            log.error("Price fetch error: %s", e)
        await asyncio.sleep(10)

def get_price(symbol):
    return PRICES.get(symbol.upper().replace("/","").replace("-",""), {})

def get_all_prices():
    """📡 البثّ اللحظي يطغى على REST.

    مقيس 11 سبتمبر: هذا الملف يجلب كل الاسعار عبر REST كل 10 ثوان،
    بينما radars/futures/price_stream يبث لحظيا عبر websocket ولا
    يصل الواجهة. فالمستخدم يرى سعرا عمره حتى 10 ثوان والنظام يبدو
    بطيئا، والسعر اللحظي موجود عندنا ومهمل.

    الان: اللحظي اولا (عمره <= 15ث)، و REST يكمل الناقص.
    """
    try:
        from radars.futures.price_stream import _TICK
        import time as _t
        if not _TICK:
            return PRICES
        out = dict(PRICES)
        now = _t.time()
        for sym, v in list(_TICK.items()):
            if not v or (now - v[3]) > 15.0:
                continue
            b = dict(out.get(sym) or {})
            b["price"] = v[0]
            if v[1]:
                b["change"] = v[1]
            if v[2]:
                b["volume"] = v[2]
            b["live"] = True
            out[sym] = b
        return out
    except Exception as e:
        log.debug("live merge: %s", e)
        return PRICES
