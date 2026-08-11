"""👁️🔭 قائمة الترقّب — العملة النظيفة تُراقَب لا تُرفَض

لا نبحث عن الانفجار اللحظي فقط، بل عن العملة النظيفة القابلة للانفجار،
فنراقبها وننتظر علامات الانطلاق ثم ندخل. (طلب Mohamad)
"""
import asyncio
import logging
import time

log = logging.getLogger("watchlist")

WATCH_MIN_LIQ = 25_000
WATCH_MIN_TXNS_H1 = 15
WATCH_MAX_H6 = 60.0
WATCH_MAX_H24 = 150.0
WATCH_TTL = 6 * 3600
WATCH_MAX = 40
CHECK_INTERVAL = 60

SIG_VOL_ACCEL = 1.8
SIG_BUY_RATIO = 0.60
SIG_TXN_ACCEL = 1.5
SIG_LIQ_GROWTH = 1.10
SIG_NEEDED = 3

WATCHLIST: dict = {}
WATCH_STATS: dict = {}
_WK = ("added", "expired", "launched", "checked", "too_late")


def _hit(k):
    WATCH_STATS[k] = WATCH_STATS.get(k, 0) + 1


def watch_stats_snapshot():
    s = {k: WATCH_STATS.get(k, 0) for k in _WK}
    s["watching"] = len(WATCHLIST)
    WATCH_STATS.clear()
    return s


def _snap(p: dict) -> dict:
    liq = (p.get("liquidity") or {}).get("usd", 0) or 0
    v1 = (p.get("volume") or {}).get("h1", 0) or 0
    v24 = (p.get("volume") or {}).get("h24", 0) or 0
    t1 = (p.get("txns") or {}).get("h1") or {}
    b = t1.get("buys", 0) or 0
    s = t1.get("sells", 0) or 0
    pc = p.get("priceChange") or {}
    try:
        price = float(p.get("priceUsd") or 0)
    except Exception:
        price = 0.0
    return {"liq": liq, "v1": v1, "v24": v24, "txns": b + s,
            "buy_ratio": (b / (b + s)) if (b + s) > 0 else 0.0,
            "price": price, "h1": float(pc.get("h1") or 0),
            "h6": float(pc.get("h6") or 0), "h24": float(pc.get("h24") or 0),
            "ts": time.time()}


def qualifies_for_watch(p: dict) -> tuple:
    s = _snap(p)
    if s["liq"] < WATCH_MIN_LIQ:
        return False, f"سيولة {s['liq']:,.0f}"
    if s["txns"] < WATCH_MIN_TXNS_H1:
        return False, f"معاملات {s['txns']}"
    if s["h6"] > WATCH_MAX_H6 or s["h24"] > WATCH_MAX_H24:
        return False, f"الموجة قديمة (h6 {s['h6']:+.0f}%)"
    if s["h6"] < -40 or s["h1"] < -15:
        return False, "تنهار"
    return True, "مؤهّلة"


def add_to_watch(addr: str, symbol: str, p: dict) -> bool:
    if not addr or addr in WATCHLIST:
        return False
    if len(WATCHLIST) >= WATCH_MAX:
        return False
    ok, why = qualifies_for_watch(p)
    if not ok:
        if "قديمة" in why:
            _hit("too_late")
        return False
    s = _snap(p)
    WATCHLIST[addr] = {"symbol": symbol or "?", "added": time.time(),
                       "base": s, "peak_price": s["price"]}
    _hit("added")
    log.info("👁️ ترقّب: %s (سيولة $%.0f · h6 %+.0f%%) — المراقَبون %d",
             symbol, s["liq"], s["h6"], len(WATCHLIST))
    return True


def launch_signals(base: dict, now: dict) -> tuple:
    sigs = []
    avg_h = (now["v24"] / 24) if now["v24"] > 0 else 0
    if avg_h > 0 and now["v1"] >= avg_h * SIG_VOL_ACCEL:
        sigs.append(f"حجم×{now['v1']/avg_h:.1f}")
    if now["buy_ratio"] >= SIG_BUY_RATIO:
        sigs.append(f"شراء {now['buy_ratio']*100:.0f}%")
    if base["price"] > 0 and now["price"] > base["price"] * 1.05:
        sigs.append(f"سعر +{(now['price']/base['price']-1)*100:.0f}%")
    if base["txns"] > 0 and now["txns"] >= base["txns"] * SIG_TXN_ACCEL:
        sigs.append(f"معاملات×{now['txns']/base['txns']:.1f}")
    if base["liq"] > 0 and now["liq"] >= base["liq"] * SIG_LIQ_GROWTH:
        sigs.append(f"سيولة +{(now['liq']/base['liq']-1)*100:.0f}%")
    return len(sigs), sigs


async def watch_loop():
    import httpx
    from radars.memecoin.scout_meme import (
        _fetch_pairs, _score, _meme_seen, _meme_save, _meme_broadcast)
    log.info("👁️🔭 قائمة الترقّب بدأت")
    while True:
        try:
            now_t = time.time()
            if WATCHLIST:
                async with httpx.AsyncClient() as cc:
                    for addr in list(WATCHLIST.keys()):
                        info = WATCHLIST.get(addr) or {}
                        sym = info.get("symbol", "?")
                        if now_t - info.get("added", 0) > WATCH_TTL:
                            WATCHLIST.pop(addr, None)
                            _hit("expired")
                            log.info("👁️ انتهت مهلة الترقّب: %s", sym)
                            continue
                        try:
                            pairs = await _fetch_pairs(cc, addr)
                        except Exception:
                            continue
                        if not pairs:
                            continue
                        p = max(pairs, key=lambda x: (x.get("liquidity") or {}).get("usd", 0) or 0)
                        cur = _snap(p)
                        _hit("checked")
                        if cur["h6"] > 120:
                            WATCHLIST.pop(addr, None)
                            _hit("too_late")
                            log.info("👁️⏰ %s فات الوقت (h6 %+.0f%%)", sym, cur["h6"])
                            continue
                        n, sigs = launch_signals(info["base"], cur)
                        if n >= SIG_NEEDED:
                            if _meme_seen(addr):
                                WATCHLIST.pop(addr, None)
                                continue
                            sc = _score(p)
                            _meme_save(p, sc)
                            await _meme_broadcast(p, sc)
                            WATCHLIST.pop(addr, None)
                            _hit("launched")
                            log.info("🚀👁️ انطلاق مؤكَّد: %s | %d علامات: %s | score %d",
                                     sym, n, " · ".join(sigs), sc)
        except Exception as e:
            log.warning("watch loop: %s", e)
        await asyncio.sleep(CHECK_INTERVAL)
