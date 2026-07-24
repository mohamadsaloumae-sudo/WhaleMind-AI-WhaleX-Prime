"""⚡🐸 رادار الميم اللحظي — PumpPortal WebSocket.
الحدث يصلنا لحظة وقوعه (إطلاق / ترحيل / صفقة) بدل انتظار دورة مسح."""
import asyncio
import json
import time
import logging

log = logging.getLogger("meme_live")

WS_URL = "wss://pumpportal.fun/api/data"
_seen: dict = {}          # mint -> آخر فحص
_watch_trades: set = set()  # عملات نتتبّع صفقاتها لحظياً
_last_px: dict = {}       # mint -> (price_usd, ts)
_sol_usd = 0.0
_ws_ref = {"ws": None}


def get_live_price(mint: str, max_age: float = 30.0):
    """سعر لحظي من تيار الصفقات — None إن لا بثّ."""
    v = _last_px.get(mint)
    if v and (time.time() - v[1]) <= max_age:
        return v[0]
    return None


async def watch_token(mint: str):
    """اشتراك لحظي بصفقات عملة (للصفقات المفتوحة)."""
    _watch_trades.add(mint)
    ws = _ws_ref.get("ws")
    if ws:
        try:
            await ws.send(json.dumps({"method": "subscribeTokenTrade", "keys": [mint]}))
        except Exception:
            pass


async def unwatch_token(mint: str):
    _watch_trades.discard(mint)
    ws = _ws_ref.get("ws")
    if ws:
        try:
            await ws.send(json.dumps({"method": "unsubscribeTokenTrade", "keys": [mint]}))
        except Exception:
            pass


async def _sol_price():
    global _sol_usd
    while True:
        try:
            import httpx
            async with httpx.AsyncClient() as c:
                r = await c.get("https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT", timeout=10)
                _sol_usd = float(r.json().get("price") or 0)
        except Exception:
            pass
        await asyncio.sleep(120)


async def _evaluate(mint: str, source: str):
    """يفحص العملة بالبوابات فور وصول حدثها."""
    now = time.time()
    if mint in _seen and now - _seen[mint] < 1800:
        return
    _seen[mint] = now
    if len(_seen) > 3000:
        for k in [k for k, v in _seen.items() if now - v > 7200]:
            _seen.pop(k, None)

    import httpx
    from radars.memecoin.scout_meme import (
        _fetch_pairs, _gate0, _gate1, _gate2_solana, _gate25_onchain,
        _score, _meme_seen, _meme_save, _meme_broadcast, SIGNAL_THRESHOLD,
    )
    async with httpx.AsyncClient() as c:
        pair = None
        # العملة قد تحتاج ثوانٍ لتظهر في مصدر البيانات
        for attempt in range(4):
            pairs = await _fetch_pairs(c, mint)
            if pairs:
                pair = max(pairs, key=lambda x: (x.get("liquidity") or {}).get("usd", 0) or 0)
                break
            await asyncio.sleep(6)
        if not pair or not _gate0(pair):
            return
        ok1, r1 = await _gate1(c, "solana", mint)
        if not ok1:
            log.info("⚡🐸🚫 %s بوابة1: %s", (pair.get("baseToken") or {}).get("symbol", "?"), r1)
            return
        ok2, r2 = await _gate2_solana(c, mint)
        if not ok2:
            log.info("⚡🐸🚫 %s بوابة2: %s", (pair.get("baseToken") or {}).get("symbol", "?"), r2)
            return
        ok25, r25 = await _gate25_onchain(c, mint)
        if not ok25:
            log.info("⚡🐸🚫 %s بوابة2.5: %s", (pair.get("baseToken") or {}).get("symbol", "?"), r25)
            return
        sc = _score(pair)
        if sc < SIGNAL_THRESHOLD:
            return
        if _meme_seen(mint):
            return
        _meme_save(pair, sc)
        await _meme_broadcast(pair, sc)
        await watch_token(mint)
        log.info("⚡🐸 إشارة لحظية (%s): %s score %d",
                 source, (pair.get("baseToken") or {}).get("symbol", "?"), sc)


def _extract_price(d):
    """سعر الدولار من حدث صفقة."""
    try:
        vs = float(d.get("vSolInBondingCurve") or 0)
        vt = float(d.get("vTokensInBondingCurve") or 0)
        if vs > 0 and vt > 0 and _sol_usd > 0:
            return (vs / vt) * _sol_usd
    except Exception:
        pass
    return None


async def live_loop():
    asyncio.create_task(_sol_price())
    structure_logged = {"new": False, "mig": False, "trade": False}
    while True:
        try:
            import websockets
            async with websockets.connect(WS_URL, ping_interval=20, close_timeout=5) as ws:
                _ws_ref["ws"] = ws
                await ws.send(json.dumps({"method": "subscribeMigration"}))
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                if _watch_trades:
                    await ws.send(json.dumps({"method": "subscribeTokenTrade", "keys": list(_watch_trades)}))
                log.info("⚡🐸 Meme live stream connected")
                async for msg in ws:
                    try:
                        d = json.loads(msg)
                        if not isinstance(d, dict) or d.get("message"):
                            continue
                        mint = d.get("mint") or d.get("ca")
                        tx = (d.get("txType") or "").lower()
                        if not mint:
                            continue
                        # سعر لحظي للعملات المتتبّعة
                        if mint in _watch_trades:
                            px = _extract_price(d)
                            if px:
                                _last_px[mint] = (px, time.time())
                            if not structure_logged["trade"]:
                                structure_logged["trade"] = True
                                log.info("⚡🐸 بنية صفقة: %s", str(d)[:230])
                        if tx in ("migrate", "migration"):
                            if not structure_logged["mig"]:
                                structure_logged["mig"] = True
                                log.info("⚡🐸 بنية ترحيل: %s", str(d)[:230])
                            asyncio.create_task(_evaluate(mint, "ترحيل"))
                        elif tx in ("create", "created"):
                            if not structure_logged["new"]:
                                structure_logged["new"] = True
                                log.info("⚡🐸 بنية إطلاق: %s", str(d)[:230])
                    except Exception as e:
                        log.debug("msg: %s", e)
        except Exception as e:
            log.warning("⚡🐸 live drop: %s", e)
        _ws_ref["ws"] = None
        await asyncio.sleep(5)
