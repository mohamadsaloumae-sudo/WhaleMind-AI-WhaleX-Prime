"""
🐸 رادار الميم كوينز — معزول نهائياً عن الفيوتشر والسبوت.
المرحلة 1: رصد DexScreener + البوابة 0 (الأساسيات). إشارات فقط، لا تداول.
"""
import asyncio
import time
import logging
import httpx
import sqlite3
import os

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


MEME_DB = os.path.join(os.path.dirname(__file__), "..", "..", "db", "memecoin.db")
MEME_CHANNEL = "-1003918596088"
SIGNAL_THRESHOLD = 60


def _init_meme_db():
    os.makedirs(os.path.dirname(MEME_DB), exist_ok=True)
    conn = sqlite3.connect(MEME_DB)
    conn.execute("CREATE TABLE IF NOT EXISTS meme_signals(id INTEGER PRIMARY KEY, symbol TEXT, address TEXT UNIQUE, chain TEXT, score INTEGER, liq REAL, vol REAL, url TEXT, ts INTEGER, active INTEGER DEFAULT 1)")
    for _col, _def in (("entry_price", "REAL"), ("status", "TEXT DEFAULT 'open'"), ("exit_price", "REAL"),
                       ("pnl_pct", "REAL"), ("peak_price", "REAL"), ("closed_ts", "INTEGER"), ("buys_ratio", "REAL")):
        try: conn.execute(f"ALTER TABLE meme_signals ADD COLUMN {_col} {_def}")
        except Exception: pass
    conn.commit(); conn.close()


def _meme_seen(addr):
    try:
        conn = sqlite3.connect(MEME_DB)
        r = conn.execute("SELECT 1 FROM meme_signals WHERE address=?", (addr,)).fetchone()
        conn.close(); return bool(r)
    except Exception:
        return False


def _meme_save(p, sc):
    b = p.get("baseToken") or {}
    try:
        conn = sqlite3.connect(MEME_DB)
        _t = (p.get("txns") or {}).get("h24") or {}
        _tt = (_t.get("buys", 0) or 0) + (_t.get("sells", 0) or 0)
        _ratio = ((_t.get("buys", 0) or 0) / _tt) if _tt else 0
        _px = float(p.get("priceUsd") or 0)
        conn.execute("INSERT OR IGNORE INTO meme_signals(symbol,address,chain,score,liq,vol,url,ts,entry_price,status,peak_price,buys_ratio) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                     (b.get("symbol", "?"), b.get("address", ""), p.get("chainId"), sc,
                      (p.get("liquidity") or {}).get("usd", 0), (p.get("volume") or {}).get("h24", 0),
                      p.get("url", ""), int(time.time()), _px, "open", _px, _ratio))
        conn.commit(); conn.close()
    except Exception as e:
        log.warning("meme save: %s", e)


async def _meme_broadcast(p, sc):
    b = p.get("baseToken") or {}
    liq = (p.get("liquidity") or {}).get("usd", 0)
    vol = (p.get("volume") or {}).get("h24", 0)
    msg = ("\U0001F438 <b>\u0625\u0634\u0627\u0631\u0629 \u0645\u064a\u0645 \u0643\u0648\u064a\u0646</b>\n\n"
           f"<b>{b.get('symbol','?')}</b>  ({p.get('chainId')})\n"
           f"\U0001F4A7 \u0627\u0644\u0633\u064a\u0648\u0644\u0629: ${liq:,.0f}\n"
           f"\U0001F4CA \u0627\u0644\u062d\u062c\u0645 24\u0633: ${vol:,.0f}\n"
           f"\U0001F3AF \u0627\u0644\u0646\u0642\u0627\u0637: <b>{sc}/100</b>\n"
           "\u2705 \u0627\u062c\u062a\u0627\u0632 \u0643\u0644 \u0627\u0644\u0641\u064a\u062a\u0648\u0647\u0627\u062a\n"
           f"\U0001F517 {p.get('url','')}\n\n"
           "\U0001F40B <i>WhaleMind Meme Radar</i>")
    try:
        from services.telegram import send_message
        await send_message(MEME_CHANNEL, msg)
    except Exception as e:
        log.warning("meme broadcast: %s", e)


def _meme_close(sid, px, pnl):
    try:
        conn = sqlite3.connect(MEME_DB)
        conn.execute("UPDATE meme_signals SET status='closed', active=0, exit_price=?, pnl_pct=?, closed_ts=? WHERE id=?",
                     (px, pnl, int(time.time()), sid))
        conn.commit(); conn.close()
    except Exception as e:
        log.warning("meme close: %s", e)


def _meme_peak(sid, peak):
    try:
        conn = sqlite3.connect(MEME_DB)
        conn.execute("UPDATE meme_signals SET peak_price=? WHERE id=?", (peak, sid))
        conn.commit(); conn.close()
    except Exception:
        pass


async def _meme_close_broadcast(r, px, pnl, reason):
    emoji = "\u2705" if pnl >= 0 else "\u274C"
    msg = (f"{emoji} <b>\u0625\u063a\u0644\u0627\u0642 \u0635\u0641\u0642\u0629 \u0645\u064a\u0645</b>\n\n"
           f"<b>{r.get('symbol','?')}</b>  ({r.get('chain')})\n"
           f"\u0627\u0644\u0646\u062a\u064a\u062c\u0629: <b>{pnl:+.1f}%</b>\n"
           f"\u0627\u0644\u0633\u0628\u0628: {reason}\n\n"
           "\U0001F40B <i>WhaleMind Meme Radar</i>")
    try:
        from services.telegram import send_message
        await send_message(MEME_CHANNEL, msg)
    except Exception as e:
        log.warning("meme close bc: %s", e)


async def _meme_track_one(cc, r):
    pairs = await _fetch_pairs(cc, r["address"])
    if not pairs:
        return
    best = max(pairs, key=lambda x: (x.get("liquidity") or {}).get("usd", 0) or 0)
    px = float(best.get("priceUsd") or 0)
    entry = float(r.get("entry_price") or 0)
    if px <= 0 or entry <= 0:
        return
    pnl = (px - entry) / entry * 100
    peak = max(float(r.get("peak_price") or entry), px)
    if peak > float(r.get("peak_price") or 0):
        _meme_peak(r["id"], peak)
    peak_pnl = (peak - entry) / entry * 100
    reason = None
    if pnl >= 50:
        reason = "\U0001F3AF \u0627\u0644\u0647\u062f\u0641 +50%"
    elif pnl <= -25:
        reason = "\U0001F6D1 \u0627\u0644\u0648\u0642\u0641 -25%"
    elif peak_pnl >= 35 and pnl <= 20:
        reason = "\U0001F512 \u0642\u0641\u0644 \u0631\u0628\u062d +20%"
    elif peak_pnl >= 20 and pnl <= 10:
        reason = "\U0001F512 \u0642\u0641\u0644 \u0631\u0628\u062d +10%"
    elif time.time() - (r.get("ts") or 0) > 24 * 3600:
        reason = "\u23F1 \u0627\u0646\u062a\u0647\u0627\u0621 24\u0633"
    if reason:
        _meme_close(r["id"], px, pnl)
        await _meme_close_broadcast(r, px, pnl, reason)
        log.info("\U0001F438 closed %s %+.1f%% (%s)", r.get("symbol"), pnl, reason)


async def meme_tracker_loop():
    log.info("\U0001F438\U0001F4E1 Meme paper-tracker started")
    while True:
        try:
            conn = sqlite3.connect(MEME_DB); conn.row_factory = sqlite3.Row
            rows = [dict(x) for x in conn.execute("SELECT * FROM meme_signals WHERE status='open' AND entry_price > 0").fetchall()]
            conn.close()
            if rows:
                async with httpx.AsyncClient() as cc:
                    for r in rows:
                        try:
                            await _meme_track_one(cc, r)
                        except Exception as _e:
                            log.debug("track one: %s", _e)
        except Exception as e:
            log.warning("meme tracker: %s", e)
        await asyncio.sleep(60)


async def meme_loop():
    _init_meme_db()
    asyncio.create_task(meme_tracker_loop())
    log.info("\U0001F438 Meme radar loop started")
    while True:
        try:
            survivors = await scan()
            for p in survivors:
                sc = _score(p)
                if sc < SIGNAL_THRESHOLD:
                    continue
                addr = (p.get("baseToken") or {}).get("address") or ""
                if not addr or _meme_seen(addr):
                    continue
                _meme_save(p, sc)
                await _meme_broadcast(p, sc)
                log.info("\U0001F438 signal: %s (%s) score %d",
                         (p.get("baseToken") or {}).get("symbol", "?"), p.get("chainId"), sc)
        except Exception as e:
            log.warning("meme loop: %s", e)
        await asyncio.sleep(180)


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
