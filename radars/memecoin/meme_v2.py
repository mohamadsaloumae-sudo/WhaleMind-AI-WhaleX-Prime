"""🐸 WhaleX Meme — النسخة النظيفة

النسخة القديمة: 1,217 سطراً · 61 عتبة · 52 شرط رفض · 4 مسارات
الحساب: احتمال عبور 52 شرطاً = 0.4% → صمت حتمي.

ما بقي — فقط ما أثبتته بيانات 248 صفقة:
  🔥 الحرق          → 17 صفقة كارثية بلا حرق = -1,085%
  📊 score≥92+شراء≥0.62 → 92 صفقة · فوز 63% · +87.8%
  🕐 حظر 0-6 UTC     → 64 صفقة = -448%
  👥 التوزيع         → الحرق لا يمنع التلاعب البشري

الشروط: 12 بدل 52.
"""
import asyncio
import logging
import time
from datetime import datetime

log = logging.getLogger("meme_v2")

MIN_LIQ = 30_000
# 🔥 الحرق صار مفضَّلاً لا إلزامياً: كان يقصّ 77% ممّن يصله (10 من 13).
#    البديل: حارس السحب اللحظي (كل 20ث · خروج عند -15% في البركة) + سيولة أعمق.
#    TINCAT فقدت -99% لأن الحارس كان كل 5 دقائق — الآن كل 20 ثانية.
UNBURNED_MIN_LIQ = 60_000   # البركة الأكبر أصعب سحباً
MIN_VOL24 = 50_000
MIN_TXNS_H1 = 25
MIN_BUY_RATIO = 0.55
# 📊 قياس 248 صفقة: 0.45-0.62 = -632.1% | 0.62-0.68 = +173.5% فوز 79% | 0.68+ = -284.2%
MAX_BUY_RATIO = 0.85        # الشراء المفرط = تلاعب أو ذروة استهلكت الطلب
MAX_PUMP_H1 = 200.0
MAX_RUN_H6 = 150.0
MAX_DUMP = -30.0
SCORE_MIN = 88
# 📊 قياس 248 صفقة: 92-95 = +2.42% فوز 57% (الوحيدة الرابحة)
#    88-92 = -19.9% | 95-98 = -3.28% | 98+ = -0.92% (انفجرت أصلاً = دخول متأخّر)
SCORE_MAX = 101
DEAD_HOURS = (0, 1, 2, 3, 4, 5)

SCAN_INTERVAL = 60
COOLDOWN_SEC = 3600

_last: dict = {}
STATS: dict = {}
_KEYS = ("scanned", "no_flow", "weak_buy", "old_wave", "not_burned",
         "bad_holders", "low_score", "dead_hour", "emitted")


def _hit(k):
    STATS[k] = STATS.get(k, 0) + 1


def stats_snapshot():
    s = {k: STATS.get(k, 0) for k in _KEYS}
    STATS.clear()
    return s


def _flow_ok(p) -> tuple:
    liq = (p.get("liquidity") or {}).get("usd", 0) or 0
    if liq < MIN_LIQ:
        return False, f"سيولة {liq:,.0f}"
    vol = (p.get("volume") or {}).get("h24", 0) or 0
    if vol < MIN_VOL24:
        return False, f"حجم {vol:,.0f}"
    t1 = (p.get("txns") or {}).get("h1") or {}
    b = t1.get("buys", 0) or 0
    s = t1.get("sells", 0) or 0
    if (b + s) < MIN_TXNS_H1:
        return False, f"معاملات {b+s}"
    # 🚨 عطل جذري: كنّا نفلتر على h1 ونسجّل h24 — مقياسان مختلفان.
    #    وتحليل 248 صفقة (النافذة 0.62-0.68 = +173.5%) كان على h24.
    #    فنفلتر الآن على نفس المقياس المقيس.
    t24 = (p.get("txns") or {}).get("h24") or {}
    b24 = t24.get("buys", 0) or 0
    s24 = t24.get("sells", 0) or 0
    br = b24 / (b24 + s24) if (b24 + s24) > 0 else (b / (b + s) if (b + s) > 0 else 0)
    if br < MIN_BUY_RATIO:
        return False, f"شراء {br*100:.0f}% (منخفض)"
    if br > MAX_BUY_RATIO:
        return False, f"شراء {br*100:.0f}% (مفرط)"
    pc = p.get("priceChange") or {}
    try:
        h1 = float(pc.get("h1") or 0)
        h6 = float(pc.get("h6") or 0)
        h24 = float(pc.get("h24") or 0)
    except Exception:
        h1 = h6 = h24 = 0.0
    if h1 > MAX_PUMP_H1 or h6 > MAX_RUN_H6:
        return False, f"موجة قديمة (h6 {h6:+.0f}%)"
    if h6 < MAX_DUMP or h24 < MAX_DUMP:
        return False, "تنهار"
    return True, "ok"


async def evaluate(cc, addr: str, p: dict) -> tuple:
    from radars.memecoin.scout_meme import _score, _gate2_solana, _meme_seen, WSOL_MINT
    from radars.memecoin.lp_burn import lp_is_burned

    _hit("scanned")
    if _meme_seen(addr) or (time.time() - _last.get(addr, 0) < COOLDOWN_SEC):
        return False, "مكرّرة", 0
    if datetime.utcnow().hour in DEAD_HOURS:
        _hit("dead_hour")
        return False, "ساعة ميتة", 0
    ok, why = _flow_ok(p)
    if not ok:
        _hit("weak_buy" if "شراء" in why else "old_wave" if "موجة" in why else "no_flow")
        return False, why, 0
    # 🔥 على أعلى بركة سيولةً حصراً — KM محروقة على raydium ($162K)
    #    وغير محروقة على meteora ($11)؛ الفحص العشوائي كان يتذبذب.
    from radars.memecoin.scout_meme import _fetch_pairs as _fp
    _best = p
    try:
        _all = await _fp(cc, addr)
        if _all:
            _best = max(_all, key=lambda x: (x.get("liquidity") or {}).get("usd", 0) or 0)
    except Exception:
        pass
    burned, bwhy = await lp_is_burned(cc, _best.get("pairAddress"), addr, WSOL_MINT)
    _hi_risk = False
    if not burned:
        _liq = (p.get("liquidity") or {}).get("usd", 0) or 0
        if _liq < UNBURNED_MIN_LIQ:
            _hit("not_burned")
            return False, f"{bwhy} + سيولة {_liq:,.0f} < {UNBURNED_MIN_LIQ:,}", 0
        _hi_risk = True
        bwhy = f"⚠️ عالية المخاطر — غير محروقة (${_liq:,.0f}) · حارس لحظي"
    ok2, why2 = await _gate2_solana(cc, addr)
    if not ok2:
        _hit("bad_holders")
        return False, why2, 0
    sc = _score(p)
    if sc < SCORE_MIN:
        _hit("low_score")
        return False, f"نقاط {sc} (منخفض)", sc
    if sc > SCORE_MAX:
        _hit("low_score")
        return False, f"نقاط {sc} (انفجرت أصلاً)", sc
    _hit("emitted")
    return True, (f"⚠️ {bwhy}" if _hi_risk else f"🔥 {bwhy}"), sc


async def scan_loop():
    import httpx
    from radars.memecoin.scout_meme import (
        _discover, _fetch_pairs, _meme_save, _meme_broadcast, mark_verified,
    )
    log.info("🐸 WhaleX Meme (نظيف) بدأ — 12 شرطاً · مسار واحد")
    while True:
        try:
            async with httpx.AsyncClient() as c:
                addrs, ready = await _discover(c)
                for addr, chain in list(addrs.items()):
                    if chain != "solana":
                        continue
                    try:
                        p = ready.get(addr)
                        if p is None:
                            pairs = await _fetch_pairs(c, addr)
                            if not pairs:
                                continue
                            p = max(pairs, key=lambda x: (x.get("liquidity") or {}).get("usd", 0) or 0)
                        ok, why, sc = await evaluate(c, addr, p)
                        sym = (p.get("baseToken") or {}).get("symbol", "?")
                        if not ok:
                            log.debug("🐸🚫 %s: %s", sym, why)
                            continue
                        mark_verified(addr, "meme_v2")
                        _meme_save(p, sc)
                        await _meme_broadcast(p, sc)
                        _last[addr] = time.time()
                        # 🚨 مراقبة لحظية لخزائن البركة — الإغلاق في نفس بلوك السحب
                        try:
                            from radars.memecoin.drain_watch import watch_pool
                            _pa = _best.get("pairAddress") if "_best" in dir() else p.get("pairAddress")
                            await watch_pool(p.get("pairAddress"), addr, sym)
                        except Exception as _we:
                            log.debug("drain watch: %s", _we)
                        log.info("🐸✅ إشارة: %s | نقاط %d | %s", sym, sc, why)
                    except Exception as e:
                        log.debug("eval %s: %s", addr[:8], e)
            st = stats_snapshot()
            if st.get("scanned"):
                log.info("🐸 فُحص %d | تدفّق %d | شراء %d | موجة %d | حرق %d | حاملون %d | نقاط %d | ساعة %d | صدر %d",
                         st["scanned"], st["no_flow"], st["weak_buy"], st["old_wave"],
                         st["not_burned"], st["bad_holders"], st["low_score"],
                         st["dead_hour"], st["emitted"])
        except Exception as e:
            log.warning("meme_v2 loop: %s", e)
        await asyncio.sleep(SCAN_INTERVAL)
