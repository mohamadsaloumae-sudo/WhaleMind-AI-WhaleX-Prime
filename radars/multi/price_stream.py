"""⚡ بثّ الأسعار اللحظي — WebSocket لكل منصّة

المشكلة: get_price كان يجلب سعر كل عملة بطلب HTTP منفصل.
  27 صفقة على 6 منصّات = 11 ثانية. والتخزين المؤقّت يُخفي البطء لا يحلّه.

الحل: اتصال WebSocket دائم لكل منصّة عبر ccxt.pro.
  كل تحديث يُكتب في الذاكرة فوراً → القراءة 0.000 ثانية.

الحمايات: إعادة اتصال بتراجع تدريجي · احتياطي HTTP عند التقادم · لوج صحّة.
"""
import asyncio
import logging
import time

log = logging.getLogger("price_stream")

# 🔌 السبع كلها — باينانس ضمنها (صفقاتها كانت تُقرأ عبر HTTP)
EXCHANGES = ("binance", "bybit", "mexc", "bingx", "bitget", "gate", "okx")
STALE_SEC = 15.0
RECONNECT_BASE = 5.0
RECONNECT_MAX = 120.0

_PX: dict = {}
_CLIENTS: dict = {}
STATS: dict = {"updates": 0, "reconnects": 0}
_ALIVE: dict = {}


def get_price(ccxt_symbol: str):
    """السعر اللحظي من الذاكرة — None إن لم يصل أو تقادم."""
    p = _PX.get(ccxt_symbol)
    if not p:
        return None
    if (time.time() - p[1]) > STALE_SEC:
        return None
    return p[0]


def stream_health() -> dict:
    now = time.time()
    return {
        "symbols": len(_PX),
        "updates": STATS["updates"],
        "reconnects": STATS["reconnects"],
        "exchanges": {k: round(now - v, 1) for k, v in _ALIVE.items()},
    }


def _universe_by_exchange() -> dict:
    """عملات كوننا موزّعة على منصّاتها + صفقات باينانس المفتوحة."""
    import sqlite3, json
    out = {}
    try:
        cn = sqlite3.connect("/opt/whalex/multi_universe.db")
        for sym, ex, ck in cn.execute(
                "SELECT symbol, exchange, ccxt_symbol FROM universe"):
            out.setdefault(ex, []).append(ck)
        cn.close()
    except Exception as e:
        log.warning("⚡ قراءة الكون: %s", e)
    # 🔌 باينانس: نتابع رموز صفقاتها المفتوحة (ليست في كون المنصّات)
    try:
        _mx = {c for lst in out.values() for c in lst}
        _pc = sqlite3.connect("/opt/whalex/positions.db")
        _bn = []
        for (_d,) in _pc.execute(
                "SELECT data FROM active_positions WHERE status!='closed'"):
            try:
                _s = (json.loads(_d).get("symbol") or "").upper()
            except Exception:
                continue
            if not _s.endswith("USDT"):
                continue
            _ck = f"{_s[:-4]}/USDT:USDT"
            if _ck not in _mx and _ck not in _bn:
                _bn.append(_ck)
        _pc.close()
        if _bn:
            out["binance"] = _bn
    except Exception as e:
        log.debug("⚡ رموز باينانس: %s", e)
    return out


async def _stream_one(ex: str):
    import ccxt.pro as ccxtpro
    delay = RECONNECT_BASE
    while True:
        client = None
        try:
            syms = _universe_by_exchange().get(ex, [])
            if not syms:
                await asyncio.sleep(60)
                continue
            client = getattr(ccxtpro, ex)({
                "enableRateLimit": True,
                "options": {"defaultType": "swap"},
            })
            _CLIENTS[ex] = client
            # 🚫 منصّات لا تدعم watchTickers — نتركها للاحتياطي (بينج إكس)
            if not client.has.get("watchTickers"):
                log.warning("⚡ %s: لا يدعم watchTickers — احتياطي HTTP", ex)
                try:
                    await client.close()
                except Exception:
                    pass
                return
            log.info("⚡🔌 %s: بثّ لحظي على %d عملة", ex, len(syms))
            delay = RECONNECT_BASE
            while True:
                tk = await client.watch_tickers(syms)
                now = time.time()
                _ALIVE[ex] = now
                for k, v in (tk or {}).items():
                    p = v.get("last") or v.get("close")
                    if p:
                        _PX[k] = (float(p), now)
                        STATS["updates"] += 1
        except Exception as e:
            STATS["reconnects"] += 1
            log.warning("⚡ %s انقطع: %s — إعادة بعد %.0fث", ex, str(e)[:60], delay)
            try:
                if client:
                    await client.close()
            except Exception:
                pass
            _CLIENTS.pop(ex, None)
            await asyncio.sleep(delay)
            delay = min(RECONNECT_MAX, delay * 2)


async def price_stream_loop():
    log.info("⚡ بثّ الأسعار اللحظي بدأ — %d منصّة", len(EXCHANGES))
    for e in EXCHANGES:
        asyncio.create_task(_stream_one(e))
    while True:
        await asyncio.sleep(300)
        h = stream_health()
        log.info("⚡ البثّ: %d عملة | %d تحديث | %d إعادة | %s",
                 h["symbols"], h["updates"], h["reconnects"], h["exchanges"])
