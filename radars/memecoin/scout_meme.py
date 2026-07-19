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


async def _gate1_solana(c, addr):
    # فيتوهات سولانا عبر RugCheck
    try:
        r = await c.get(f"https://api.rugcheck.xyz/v1/tokens/{addr}/report/summary", timeout=12)
        if r.status_code != 200:
            return False, "لا بيانات RugCheck (احترازي)"
        j = r.json()
    except Exception:
        return False, "خطأ RugCheck"
    lp = j.get("lpLockedPct", 0) or 0
    if lp < 80:
        return False, f"سيولة مقفلة {lp:.0f}% فقط"
    for rk in (j.get("risks") or []):
        if (rk.get("level") or "").lower() in ("danger", "high"):
            return False, rk.get("name", "خطر عالٍ")
    if (j.get("score_normalised", 0) or 0) > 50:
        return False, "نقاط خطر عالية"
    return True, "نجح"


async def _gate1_evm(c, addr, chain):
    # فيتوهات BSC/Ethereum عبر GoPlus
    cid = "56" if chain == "bsc" else "1"
    try:
        r = await c.get(f"https://api.gopluslabs.io/api/v1/token_security/{cid}?contract_addresses={addr}", timeout=12)
        d = (r.json().get("result") or {}).get(addr.lower(), {})
    except Exception:
        return False, "خطأ GoPlus"
    if not d:
        return False, "غير مفهرس (احترازي)"
    checks = [("is_honeypot", "1", "honeypot"), ("is_proxy", "1", "proxy"),
              ("is_mintable", "1", "mintable"), ("is_open_source", "0", "كود مغلق"),
              ("cannot_sell_all", "1", "منع بيع الكل"), ("hidden_owner", "1", "مالك مخفي"),
              ("can_take_back_ownership", "1", "استرجاع ملكية")]
    for field, bad, name in checks:
        if str(d.get(field)) == bad:
            return False, name
    bt = float(d.get("buy_tax") or 0)
    st = float(d.get("sell_tax") or 0)
    if bt > 0.10 or st > 0.10:
        return False, f"ضرائب {bt*100:.0f}/{st*100:.0f}%"
    return True, "نجح"


async def _gate1(c, chain, addr):
    if chain == "solana":
        return await _gate1_solana(c, addr)
    return await _gate1_evm(c, addr, chain)


def _score(p):
    # البوابة 3: تنقيط 0-100 من بيانات DexScreener (بلا API إضافي)
    pts = 0.0
    t = (p.get("txns") or {}).get("h24") or {}
    buys = t.get("buys", 0) or 0
    sells = t.get("sells", 0) or 0
    tot = buys + sells
    if tot > 0:
        pts += min(30.0, (buys / tot) * 45)        # زخم الشراء (حتى 30)
    liq = (p.get("liquidity") or {}).get("usd", 0) or 0
    pts += min(25.0, liq / 20000 * 25)             # عمق السيولة (حتى 25)
    vol = (p.get("volume") or {}).get("h24", 0) or 0
    if liq > 0:
        pts += min(25.0, (vol / liq) * 8)          # نشاط الحجم/السيولة (حتى 25)
    mc = p.get("marketCap") or p.get("fdv") or 0
    if liq > 0 and mc > 0:
        ml = mc / liq                              # نسبة القيمة/السيولة (منخفض أأمن)
        if ml < 10:
            pts += 20
        elif ml < 30:
            pts += 10
    return round(pts)


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
            if not _gate0(best):
                return None
            ok, reason = await _gate1(c, chain, addr)
            if not ok:
                log.info("🐸🚫 %s (%s) بوابة1: %s", (best.get("baseToken") or {}).get("symbol", "?"), chain, reason)
                return None
            return best

        res = await asyncio.gather(*[_check(ch, a) for ch, a in cands])
        return [r for r in res if r]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    survivors = asyncio.run(scan())
    print(f"\n🐸 ناجون من البوابة 0: {len(survivors)}\n")
    for p in survivors:
        b = p.get("baseToken") or {}
        liq = (p.get("liquidity") or {}).get("usd", 0)
        sc = _score(p)
        flag = "✅ إشارة (≥60)" if sc >= 60 else "دون العتبة"
        print(f"  {b.get('symbol','?'):10} | {p.get('chainId'):8} | سيولة ${liq:>11,.0f} | نقاط {sc:>3}/100 | {flag}")
