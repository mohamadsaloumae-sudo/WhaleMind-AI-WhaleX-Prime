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


async def lp_is_burned(cc, pair_address: str, base_mint: str = "", quote_mint: str = "") -> tuple:
    """(محروقة؟, السبب) — الفحص اليقيني قبل أي دخول."""
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
    _known = [464, 136, 400, 432, 264, 168, 200, 232, 296, 328, 360, 496, 528]
    _offsets = [o for o in _known if o + 32 <= len(raw)]
    _offsets += [o for o in range(8, len(raw) - 32, 8) if o not in _offsets]

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
        return True, f"🔥 محروقة (LP={amt:.2f})"
    return False, f"🔓 مفتوحة (LP={amt:,.0f}) — قابلة للسحب"
