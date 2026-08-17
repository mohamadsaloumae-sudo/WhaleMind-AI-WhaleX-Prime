"""🌊 مصدر راديوم اللحظي — إضافة بجانب pump.fun (لا بديل عنه)

DexScreener لا يعطي إطلاقات راديوم الجديدة (البحث يُرجع الأشهر، أصغرها 14 ساعة).
الحل: اشتراك logsSubscribe على برنامج راديوم عبر Helius، والتقاط إنشاء البِرَك
لحظياً → تمرير العملة لنفس _evaluate التي يستخدمها pump.fun.
"""
import asyncio
import json
import logging
import os
import time

log = logging.getLogger("raydium_live")

RAYDIUM_AMM = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_CLMM = "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK"

WSOL = "So11111111111111111111111111111111111111112"
_SKIP_MINTS = {
    WSOL,
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
}

_seen_sigs: dict = {}
RAYDIUM_ENABLED = False  # 🛑 مُطفأ: صفر بِرَك جديدة في يومين (الإطلاقات في pump.fun)
#    والاتصال مُنح لحارس السحب اللحظي الذي يمنع -1,085%


def _env(key: str) -> str:
    v = os.environ.get(key, "")
    if v:
        return v
    p = "/opt/whalex/.env"
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    return ""


async def _mints_from_sig(sig: str) -> list:
    import httpx
    url = _env("SOL_RPC")
    if not url:
        return []
    body = {"jsonrpc": "2.0", "id": 1, "method": "getTransaction",
            "params": [sig, {"encoding": "jsonParsed",
                             "maxSupportedTransactionVersion": 0}]}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            j = (await c.post(url, json=body)).json()
    except Exception as e:
        log.debug("getTransaction %s: %s", sig[:12], e)
        return []
    meta = ((j or {}).get("result") or {}).get("meta") or {}
    out = []
    for key in ("preTokenBalances", "postTokenBalances"):
        for b in (meta.get(key) or []):
            m = b.get("mint")
            if m and m not in _SKIP_MINTS and m not in out:
                out.append(m)
    return out


async def raydium_loop():
    """🌊 يستمع لإنشاء بِرَك راديوم ويمرّرها لخط الفحص القائم."""
    import websockets
    from radars.memecoin.live_stream import _evaluate

    ws_url = _env("SOL_WS")
    if not ws_url:
        log.warning("🌊 راديوم: SOL_WS غير مضبوط — المصدر معطّل")
        return
    log.info("🌊 مصدر راديوم اللحظي بدأ")

    while RAYDIUM_ENABLED:
        try:
            async with websockets.connect(ws_url, ping_interval=20,
                                          close_timeout=5,
                                          max_size=8_000_000) as ws:
                for i, prog in enumerate((RAYDIUM_AMM, RAYDIUM_CLMM), start=1):
                    await ws.send(json.dumps({
                        "jsonrpc": "2.0", "id": i, "method": "logsSubscribe",
                        "params": [{"mentions": [prog]},
                                   {"commitment": "confirmed"}]}))
                log.info("🌊 راديوم: مشترك على AMM و CLMM")

                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    val = (((msg.get("params") or {}).get("result") or {})
                           .get("value") or {})
                    logs = val.get("logs") or []
                    sig = val.get("signature")
                    if not sig or val.get("err"):
                        continue
                    txt = " ".join(logs)
                    if ("initialize2" not in txt
                            and "InitializeInstruction2" not in txt
                            and "CreatePool" not in txt):
                        continue
                    now = time.time()
                    if sig in _seen_sigs and now - _seen_sigs[sig] < 3600:
                        continue
                    _seen_sigs[sig] = now
                    if len(_seen_sigs) > 2000:
                        for k in [k for k, v in _seen_sigs.items() if now - v > 7200]:
                            _seen_sigs.pop(k, None)
                    mints = await _mints_from_sig(sig)
                    for m in mints[:2]:
                        log.info("🌊🆕 بركة راديوم جديدة: %s", m[:12])
                        asyncio.create_task(_evaluate(m, "راديوم"))
        except Exception as e:
            log.warning("🌊 راديوم انقطع: %s — إعادة اتصال بعد 15ث", e)
            await asyncio.sleep(15)
