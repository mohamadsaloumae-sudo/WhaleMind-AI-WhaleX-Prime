"""🚨 حارس السحب اللحظي — الاستماع للبلوك مباشرةً

المشكلة: سحب البركة يقع في بلوك واحد (~400ms) ونبضتنا 20 ثانية.
  فحين نرى الانخفاض تكون الخسارة تحقّقت:
  TINCAT -99.2% · PUMPDOG -99.7% · Bro -99.3% (17 صفقة = -1,085.4%)

الآلية: accountSubscribe على خزائن البركة عبر Helius.
  الخزينة حساب توكن يحمل السيولة — رصيدها ينخفض لحظة السحب.
  فنُغلق في نفس اللحظة بدل انتظار النبضة.

الأثر المتوقّع: بدل -99% تصير الخسارة -10% إلى -20%.
"""
import asyncio
import json
import logging
import os
import time

log = logging.getLogger("drain_watch")

DRAIN_PCT = 20.0
CHECK_MIN_SEC = 2

_watched: dict = {}
_baseline: dict = {}
_fired: dict = {}
_sub_map: dict = {}
_ws = None
_counter = [100]
_retry = [0]

DRAIN_STATS: dict = {"watching": 0, "drains": 0, "updates": 0}


def _env(k: str, d: str = "") -> str:
    v = os.environ.get(k)
    if v:
        return v
    p = "/opt/whalex/.env"
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith(f"{k}="):
                    return line.split("=", 1)[1].strip()
    return d


async def _rpc(method: str, params: list):
    import httpx
    url = _env("SOL_RPC")
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(url, json={"jsonrpc": "2.0", "id": 1,
                                        "method": method, "params": params})
            return (r.json() or {}).get("result")
    except Exception as e:
        log.debug("rpc %s: %s", method, e)
        return None


async def _pool_vaults(pair: str) -> list:
    import base64
    try:
        import base58
    except Exception:
        return []
    res = await _rpc("getAccountInfo", [pair, {"encoding": "base64"}])
    val = (res or {}).get("value")
    if not val:
        return []
    raw = base64.b64decode(val["data"][0])
    offs = {752: [336, 368], 637: [72, 104], 904: [168, 200]}.get(
        len(raw), [336, 368, 72, 104])
    out = []
    for off in offs:
        if off + 32 > len(raw):
            continue
        cand = base58.b58encode(raw[off:off + 32]).decode()
        if cand.startswith("11"):
            continue
        bal = await _rpc("getTokenAccountBalance", [cand])
        if bal and (bal.get("value") or {}).get("amount"):
            out.append((cand, float(bal["value"].get("uiAmount") or 0)))
    return out


async def watch_pool(pair: str, addr: str, symbol: str) -> bool:
    if not _ws or not pair:
        return False
    vaults = await _pool_vaults(pair)
    if not vaults:
        log.debug("🚨 %s: لا خزائن معروفة", symbol)
        return False
    for vault, bal in vaults:
        if vault in _watched:
            continue
        _counter[0] += 1
        _cid = _counter[0]
        try:
            await _ws.send(json.dumps({
                "jsonrpc": "2.0", "id": _cid, "method": "accountSubscribe",
                "params": [vault, {"encoding": "jsonParsed",
                                   "commitment": "processed"}],
            }))
        except Exception as e:
            log.debug("subscribe %s: %s", vault[:8], e)
            continue
        _watched[vault] = {"addr": addr, "symbol": symbol,
                           "pair": pair, "req_id": _cid}
        _baseline[vault] = bal
        log.info("🚨👁️ مراقبة لحظية: %s خزينة %s (رصيد %.2f)",
                 symbol, vault[:8], bal)
    DRAIN_STATS["watching"] = len(_watched)
    return True


def unwatch_pool(addr: str):
    for v in [k for k, x in _watched.items() if x.get("addr") == addr]:
        _watched.pop(v, None)
        _baseline.pop(v, None)
        _fired.pop(v, None)
        for s, vv in list(_sub_map.items()):
            if vv == v:
                _sub_map.pop(s, None)
    DRAIN_STATS["watching"] = len(_watched)


async def _on_update(vault: str, ui_amount: float):
    DRAIN_STATS["updates"] += 1
    info = _watched.get(vault)
    if not info:
        return
    base = _baseline.get(vault) or 0
    if base <= 0 or ui_amount > base:
        _baseline[vault] = ui_amount
        return
    drop = (base - ui_amount) / base * 100
    if drop < DRAIN_PCT:
        return
    if time.time() - _fired.get(vault, 0) < CHECK_MIN_SEC:
        return
    _fired[vault] = time.time()
    DRAIN_STATS["drains"] += 1
    log.warning("🚨🔴 سحب لحظي: %s | الخزينة %.2f ← %.2f (-%.0f%%) — إغلاق فوري",
                info["symbol"], base, ui_amount, drop)
    try:
        from radars.memecoin.scout_meme import force_close_by_address
        await force_close_by_address(info["addr"], f"🚨 سحب لحظي -{drop:.0f}%")
    except Exception as e:
        log.error("🚨 فشل الإغلاق اللحظي %s: %s", info["symbol"], e)
    unwatch_pool(info["addr"])


async def drain_watch_loop():
    global _ws
    import websockets
    ws_url = _env("SOL_WS")
    if not ws_url:
        log.warning("🚨 SOL_WS غير مضبوط — الحارس اللحظي معطّل")
        return
    log.info("🚨 حارس السحب اللحظي بدأ (عتبة %.0f%% في البلوك)", DRAIN_PCT)
    while True:
        try:
            async with websockets.connect(ws_url, ping_interval=20,
                                          ping_timeout=20,
                                          max_size=4_000_000) as ws:
                _ws = ws
                _sub_map.clear()
                log.info("🚨🔌 متّصل — %d خزينة مُراقَبة", len(_watched))
                for v, x in list(_watched.items()):
                    _counter[0] += 1
                    x["req_id"] = _counter[0]
                    await ws.send(json.dumps({
                        "jsonrpc": "2.0", "id": _counter[0],
                        "method": "accountSubscribe",
                        "params": [v, {"encoding": "jsonParsed",
                                       "commitment": "processed"}],
                    }))
                async for msg in ws:
                    try:
                        d = json.loads(msg)
                    except Exception:
                        continue
                    # ربط رقم الاشتراك بالخزينة من ردّ التأكيد
                    if "result" in d and isinstance(d.get("result"), int):
                        for v, x in _watched.items():
                            if x.get("req_id") == d.get("id"):
                                _sub_map[d["result"]] = v
                                break
                        continue
                    if d.get("method") != "accountNotification":
                        continue
                    p = d.get("params") or {}
                    vault = _sub_map.get(p.get("subscription"))
                    if not vault:
                        continue
                    val = ((p.get("result") or {}).get("value") or {})
                    parsed = (((val.get("data") or {}).get("parsed") or {}).get("info") or {})
                    ui = (parsed.get("tokenAmount") or {}).get("uiAmount")
                    if ui is None:
                        continue
                    await _on_update(vault, float(ui))
        except Exception as e:
            _ws = None
            # ⏳ تراجع تدريجي: المحاولات المتسارعة تحرق حدّ Helius فيصير 429 دائماً
            _wait = min(300, 15 * (2 ** min(_retry[0], 4)))
            _retry[0] += 1
            if _retry[0] <= 3 or _retry[0] % 10 == 0:
                log.warning("🚨 drain ws: %s — إعادة بعد %dث (محاولة %d)",
                            str(e)[:60], _wait, _retry[0])
            await asyncio.sleep(_wait)
        else:
            _retry[0] = 0
