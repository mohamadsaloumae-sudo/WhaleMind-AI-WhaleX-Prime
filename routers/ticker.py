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
    """أقوى 50 عملة بالقيمة السوقية — الترتيب من CoinPaprika
    والسعر الحيّ من باينانس (أدقّ وأسرع تحديثاً)."""
    v, ts = _cache["p"]
    if v and time.time() - ts < PRICE_TTL:
        return v
    out = []
    try:
        rank = _cache.get("rank", (None, 0.0))
        syms = rank[0]
        if not syms or time.time() - rank[1] > 3600:
            async with httpx.AsyncClient(
                    timeout=20, headers={"User-Agent": "Mozilla/5.0"}) as c:
                rr = await c.get(
                    "https://api.coinpaprika.com/v1/tickers?limit=60")
                paprika = rr.json()
            syms = [x["symbol"] for x in paprika
                    if x.get("symbol") and x["symbol"] not in
                    ("USDT", "USDC", "DAI", "BUSD", "TUSD", "FDUSD")][:50]
            _cache["rank"] = (syms, time.time())
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://api.binance.com/api/v3/ticker/24hr")
            data = r.json()
        m = {x["symbol"]: x for x in data}
        for sy in syms:
            x = m.get(f"{sy}USDT")
            if not x:
                continue
            px = float(x.get("lastPrice") or 0)
            ch = float(x.get("priceChangePercent") or 0)
            if px <= 0:
                continue
            out.append({"symbol": sy,
                        "price": round(px, 6 if px < 1 else 2),
                        "change": round(ch, 2), "up": ch >= 0})
        if out:
            _cache["p"] = (out, time.time())
    except Exception as e:
        log.debug("ticker prices: %s", e)
        return v or []
    return out


async def _top() -> list:
    """🏆 أعلى عملات نظامنا ربحاً — دليل حيّ على الأداء."""
    v, ts = _cache.get("t", (None, 0.0))
    if v and time.time() - ts < 900:
        return v
    out = []
    try:
        import sqlite3
        cn = sqlite3.connect("/opt/whalex/ml_training.db")
        cut = int(time.time()) - 86400 * 7
        for sym, net, n in cn.execute(
                "SELECT symbol, ROUND(SUM(pnl_pct),1), COUNT(*) "
                "FROM training_signals WHERE closed_at>? AND pnl_pct IS NOT NULL "
                "AND result IN ('win','loss') GROUP BY symbol "
                "HAVING COUNT(*)>=3 ORDER BY SUM(pnl_pct) DESC LIMIT 8", (cut,)):
            out.append({"symbol": str(sym).replace("USDT", ""),
                        "net": float(net or 0), "trades": int(n)})
        cn.close()
        if out:
            _cache["t"] = (out, time.time())
    except Exception as e:
        log.debug("ticker top: %s", e)
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


# 🌐 ترجمة العناوين — MyMemory رسميّ ومجانيّ (338ms مقيس).
#    وGoogle غير الرسميّ يُعطي 429 تحت الضغط فلا نعتمده.
#    ونُخزّن كل عنوان مترجَماً إلى الأبد: العناوين تتكرّر بين
#    التحديثات، فبلا تخزين نستهلك الحصّة اليومية في ساعات.
_tr_cache = {}
_TR_MAX = 600


async def _translate(text: str) -> str:
    if text in _tr_cache:
        return _tr_cache[text]
    try:
        async with httpx.AsyncClient(
                timeout=12, headers={"User-Agent": "Mozilla/5.0"}) as c:
            r = await c.get("https://api.mymemory.translated.net/get",
                            params={"q": text[:480], "langpair": "en|ar"})
            d = r.json()
        out = ((d.get("responseData") or {}).get("translatedText") or "").strip()
        # نرفض ما لا يحوي حروفاً عربية — فالمصدر يُرجع الأصل عند الفشل
        if out and any("\u0600" <= ch <= "\u06ff" for ch in out):
            if len(_tr_cache) > _TR_MAX:
                _tr_cache.clear()
            _tr_cache[text] = out
            return out
    except Exception as e:
        log.debug("translate: %s", e)
    return text


@router.get("/ticker")
async def ticker(lang: str = "ar"):
    """أسعار حيّة + عناوين — للشريط المتحرّك."""
    news = await _news()
    if lang == "ar" and news:
        out = []
        for it in news:
            out.append({"title": await _translate(it["title"]),
                        "en": it["title"]})
        news = out
    return {"prices": await _prices(), "news": news, "top": await _top()}
