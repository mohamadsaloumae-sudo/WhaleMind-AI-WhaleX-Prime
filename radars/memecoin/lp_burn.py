"""🔥 فحص حرق سيولة LP — المعيار اليقيني ضدّ rug pull

الآلية: عند إضافة السيولة تُصدَر توكنات lpMint. ومن يريد سحب السيولة
يحتاجها. فإن أُحرقت (supply≈0) فالسيولة مقفلة داخل البركة للأبد.

مثبَت بالقياس:
  Fartcoin  LP=8.97      🔥 (سيولة $5.9M آمنة)
  BOME      LP=591M      🔓 (سيولة $12M لكن قابلة للسحب!)
  TINCAT    PumpSwap     ❌ لا lpMint أصلاً → سُحبت -99.2%

بنية Raydium AMM v4 (752 بايت): lpMint في الإزاحة 464.
PumpSwap (301 بايت) لا يصدر LP tokens → يُرفض دائماً.
"""
import base64
import logging
import os

log = logging.getLogger("lp_burn")

LP_MINT_OFFSET = 464          # 📊 مقيس على Fartcoin/ALON/arc
RAYDIUM_V4_SIZE = 752
BURN_MAX_SUPPLY = 1000.0      # LP تحت هذا = محروقة عملياً


def _rpc_url() -> str:
    v = os.environ.get("SOL_RPC", "")
    if v:
        return v
    p = "/opt/whalex/.env"
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("SOL_RPC="):
                    return line.split("=", 1)[1].strip()
    return ""


# 💾 ذاكرة دائمة: نتيجة الحرق لا تتغيّر أبداً (المحروق يبقى محروقاً).
#    كنّا نفحص نفس العملة 1,440 مرّة يومياً = ~720,000 نداء/شهر → "max usage reached"
_BURN_CACHE: dict = {}
_CACHE_DB = "/opt/whalex/db/lp_burn_cache.db"


def _cache_init():
    import sqlite3
    try:
        cn = sqlite3.connect(_CACHE_DB)
        cn.execute("CREATE TABLE IF NOT EXISTS burn_cache("
                   "pair TEXT PRIMARY KEY, burned INTEGER, why TEXT, ts INTEGER)")
        cn.commit()
        for p, b, w in cn.execute("SELECT pair,burned,why FROM burn_cache"):
            _BURN_CACHE[p] = (bool(b), w)
        cn.close()
    except Exception as e:
        log.debug("cache init: %s", e)


def _cache_put(pair: str, burned: bool, why: str):
    import sqlite3, time as _t
    _BURN_CACHE[pair] = (burned, why)
    try:
        cn = sqlite3.connect(_CACHE_DB)
        cn.execute("INSERT OR REPLACE INTO burn_cache(pair,burned,why,ts) VALUES(?,?,?,?)",
                   (pair, 1 if burned else 0, why, int(_t.time())))
        cn.commit(); cn.close()
    except Exception:
        pass


_cache_init()


async def lp_is_burned(cc, pair_address: str, base_mint: str = "", quote_mint: str = "") -> tuple:
    """(محروقة؟, السبب) — الفحص اليقيني قبل أي دخول."""
    # 💾 الذاكرة أولاً — لا نعيد فحص ما فحصناه
    _c = _BURN_CACHE.get(pair_address or "")
    if _c is not None:
        return _c[0], _c[1]
    url = _rpc_url()
    if not url or not pair_address:
        return False, "لا RPC/بركة"
    try:
        r = await cc.post(url, json={
            "jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
            "params": [pair_address, {"encoding": "base64"}]}, timeout=15)
        val = ((r.json() or {}).get("result") or {}).get("value")
        if not val:
            return False, "لا حساب بركة"
        raw = base64.b64decode(val["data"][0])
    except Exception as e:
        log.debug("lp acc %s: %s", pair_address[:10], e)
        # 🔁 محاولة ثانية — انقطاعات RPC اللحظية لا يجب أن تُرفض عملة آمنة
        try:
            import asyncio
            await asyncio.sleep(1.5)
            r = await cc.post(url, json={
                "jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
                "params": [pair_address, {"encoding": "base64"}]}, timeout=20)
            val = ((r.json() or {}).get("result") or {}).get("value")
            if not val:
                return False, "لا حساب بركة"
            raw = base64.b64decode(val["data"][0])
        except Exception:
            return False, "خطأ قراءة البركة (محاولتان)"

    # 📊 إزاحة lpMint تختلف بنوع البركة (مقيسة على السلسلة):
    #    Raydium AMM v4 (752 بايت) → 464 | Raydium CPMM (637) → 136
    #    PumpSwap (301) → لا lpMint إطلاقاً (يُرفض)
    if len(raw) < 200:
        return False, f"بنية بلا LP ({len(raw)} بايت — PumpSwap)"
    # 📊 نجرّب الإزاحات المعروفة أولاً ثم نمسح الباقي (البنى تختلف: 752/637/653/1544)
    # 📊 إزاحة lpMint مقيسة لكل بنية — نجرّبها أولاً ولا نمسح عشوائياً
    #    (المسح الأعمى كان يلتقط عملة الأساس: ALON قُرئت 997M بدل 0.197)
    _exact = {752: [464], 637: [136], 904: [136, 168], 653: [136, 168]}
    _offsets = _exact.get(len(raw))
    if _offsets:
        _offsets = [o for o in _offsets if o + 32 <= len(raw)]
    else:
        _offsets = [o for o in (464, 136, 400, 432) if o + 32 <= len(raw)]

    import base58
    _amt = None
    for off in _offsets:
        if off + 32 > len(raw):
            continue
        try:
            mint = base58.b58encode(raw[off:off + 32]).decode()
            if mint.startswith("11") or mint.startswith("So111"):
                continue
            if mint in (base_mint, quote_mint):
                continue
            r2 = await cc.post(url, json={
                "jsonrpc": "2.0", "id": 1, "method": "getTokenSupply",
                "params": [mint]}, timeout=15)
            v = ((r2.json() or {}).get("result") or {}).get("value")
            if not v:
                continue
            # 🔍 lpMint = أي mint في البركة ليس العملة نفسها ولا العملة المقابلة
            #    (decimals لا يصلح مميّزاً: BOME lpMint=6 و Fartcoin=9)
            _amt = float(v.get("uiAmount") or 0)
            break
        except Exception as e:
            log.debug("lp off %d: %s", off, e)
            continue
    if _amt is None:
        return False, f"lpMint غير موجود ({len(raw)} بايت)"
    amt = _amt

    if amt < BURN_MAX_SUPPLY:
        _w = f"🔥 محروقة (LP={amt:.2f})"
        _cache_put(pair_address, True, _w)
        return True, _w
    _w = f"🔓 مفتوحة (LP={amt:,.0f}) — قابلة للسحب"
    _cache_put(pair_address, False, _w)
    return False, _w
