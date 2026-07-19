"""
🐸 رادار الميم كوينز — معزول نهائياً عن الفيوتشر والسبوت.
المرحلة 1: رصد DexScreener + البوابة 0 (الأساسيات). إشارات فقط، لا تداول.
"""
import asyncio
import time
import logging
import httpx

log = logging.getLogger("meme_scout")

CHAINS = ("solana", "bsc", "ethereum")
MIN_LIQ = 50_000        # سيولة دنيا بالدولار
MIN_VOL_24 = 20_000     # حجم 24 ساعة دنيا
AGE_MIN_MIN = 5         # أصغر عمر بالدقائق
AGE_MAX_MIN = 72 * 60   # أكبر عمر بالدقائق
MIN_TXNS_24 = 50        # معاملات 24 ساعة دنيا

PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"
TOKENS_URL = "https://api.dexscreener.com/latest/dex/tokens/{addr}"


async def _fetch_profiles(c):
    try:
        r = await c.get(PROFILES_URL, timeout=15)
        j = r.json()
        return j if isinstance(j, list) else []
    except Exception as e:
        log.warning("profiles: %s", e)
        return []


async def _fetch_pairs(c, addr):
    try:
        r = await c.get(TOKENS_URL.format(addr=addr), timeout=15)
        return r.json().get("pairs") or []
    except Exception:
        return []


def _gate0(p):
    """البوابة 0: الأساسيات بلا أي API خارجي. فشل = رفض فوري."""
    if p.get("chainId") not in CHAINS:
        return False
    liq = (p.get("liquidity") or {}).get("usd", 0) or 0
    if liq < MIN_LIQ:
        return False
    vol = (p.get("volume") or {}).get("h24", 0) or 0
    if vol < MIN_VOL_24:
        return False
    created = (p.get("pairCreatedAt") or 0) / 1000
    if created:
        age = (time.time() - created) / 60
        if age < AGE_MIN_MIN or age > AGE_MAX_MIN:
            return False
    t = (p.get("txns") or {}).get("h24") or {}
    if (t.get("buys", 0) + t.get("sells", 0)) < MIN_TXNS_24:
        return False
    return True


async def scan():
    """يرصد العملات الجديدة، يمرّرها على البوابة 0 (متوازياً)، يرجع الناجين."""
    async with httpx.AsyncClient() as c:
        profiles = await _fetch_profiles(c)
        cands = [(p.get("chainId"), p.get("tokenAddress"))
                 for p in profiles
                 if p.get("chainId") in CHAINS and p.get("tokenAddress")]

        async def _check(chain, addr):
            pairs = await _fetch_pairs(c, addr)
            if not pairs:
                return None
            best = max(pairs, key=lambda x: (x.get("liquidity") or {}).get("usd", 0) or 0)
            return best if _gate0(best) else None

        res = await asyncio.gather(*[_check(ch, a) for ch, a in cands])
        return [r for r in res if r]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    survivors = asyncio.run(scan())
    print(f"\n🐸 ناجون من البوابة 0: {len(survivors)}\n")
    for p in survivors:
        b = p.get("baseToken") or {}
        liq = (p.get("liquidity") or {}).get("usd", 0)
        vol = (p.get("volume") or {}).get("h24", 0)
        t = (p.get("txns") or {}).get("h24") or {}
        print(f"  {b.get('symbol','?'):10} | {p.get('chainId'):8} | سيولة ${liq:>12,.0f} | حجم ${vol:>12,.0f} | شراء {t.get('buys',0)}/بيع {t.get('sells',0)}")
