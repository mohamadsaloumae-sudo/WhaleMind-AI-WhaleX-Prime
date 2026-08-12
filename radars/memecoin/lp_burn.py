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


async def lp_is_burned(cc, pair_address: str) -> tuple:
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
        return False, "خطأ قراءة البركة"

    if len(raw) < LP_MINT_OFFSET + 32:
        return False, f"بنية غير مدعومة ({len(raw)} بايت)"

    try:
        import base58
        mint = base58.b58encode(raw[LP_MINT_OFFSET:LP_MINT_OFFSET + 32]).decode()
        r2 = await cc.post(url, json={
            "jsonrpc": "2.0", "id": 1, "method": "getTokenSupply",
            "params": [mint]}, timeout=15)
        v = ((r2.json() or {}).get("result") or {}).get("value")
        if not v:
            return False, "lpMint غير صالح"
        amt = float(v.get("uiAmount") or 0)
    except Exception as e:
        log.debug("lp supply: %s", e)
        return False, "خطأ قراءة lpMint"

    if amt < BURN_MAX_SUPPLY:
        return True, f"🔥 محروقة (LP={amt:.2f})"
    return False, f"🔓 مفتوحة (LP={amt:,.0f}) — قابلة للسحب"
