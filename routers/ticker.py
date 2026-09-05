"""📈 شريط الأسعار والأخبار — مصادر حقيقية مجانية.

الأسعار من باينانس، والأخبار من Cointelegraph RSS. وكلاهما مجانيّ
بلا مفتاح. ونُخزّن النتيجة: الأسعار 30 ثانية والأخبار 10 دقائق —
فلا نُرهق المصدر ولا خادمنا مهما زار الصفحة ألف شخص.
"""
import html
import logging
import re
import time

import httpx
from fastapi import APIRouter

log = logging.getLogger("ticker")
router = APIRouter(prefix="/api/public", tags=["ticker"])

COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
         "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "TRXUSDT",
         "DOTUSDT", "MATICUSDT"]
NEWS_URL = "https://cointelegraph.com/rss"
PRICE_TTL = 30
NEWS_TTL = 600

_cache = {"p": (None, 0.0), "n": (None, 0.0)}


async def _prices() -> list:
    v, ts = _cache["p"]
    if v and time.time() - ts < PRICE_TTL:
        return v
    out = []
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://api.binance.com/api/v3/ticker/24hr")
            data = r.json()
        m = {x["symbol"]: x for x in data if x.get("symbol") in COINS}
        for s in COINS:
            x = m.get(s)
            if not x:
                continue
            px = float(x.get("lastPrice") or 0)
            ch = float(x.get("priceChangePercent") or 0)
            if px <= 0:
                continue
            out.append({
                "symbol": s.replace("USDT", ""),
                "price": round(px, 6 if px < 1 else 2),
                "change": round(ch, 2),
                "up": ch >= 0,
            })
        if out:
            _cache["p"] = (out, time.time())
    except Exception as e:
        log.debug("ticker prices: %s", e)
        return v or []
    return out


async def _news() -> list:
    v, ts = _cache["n"]
    if v and time.time() - ts < NEWS_TTL:
        return v
    out = []
    try:
        async with httpx.AsyncClient(
                timeout=15, headers={"User-Agent": "Mozilla/5.0"}) as c:
            r = await c.get(NEWS_URL)
            s = r.text
        for it in re.findall(r"<item>(.*?)</item>", s, re.S)[:14]:
            m = re.search(
                r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.S)
            if not m:
                continue
            t = html.unescape(m.group(1)).strip()
            if 12 < len(t) < 130:
                out.append({"title": t})
        if out:
            _cache["n"] = (out, time.time())
    except Exception as e:
        log.debug("ticker news: %s", e)
        return v or []
    return out


@router.get("/ticker")
async def ticker():
    """أسعار حيّة + عناوين — للشريط المتحرّك."""
    return {"prices": await _prices(), "news": await _news()}
