"""
🐸 رادار الميم كوينز — معزول نهائياً عن الفيوتشر والسبوت.
المرحلة 1: رصد DexScreener + البوابة 0 (الأساسيات). إشارات فقط، لا تداول.
"""
import asyncio
import time
import logging
from datetime import datetime
import httpx
import sqlite3
import os

log = logging.getLogger("meme_scout")

WSOL_MINT = "So11111111111111111111111111111111111111112"
CHAINS = ("solana", "bsc", "ethereum")
MIN_LIQ = 30_000        # سيولة دنيا — عملات راديوم المُرحّلة تجمع 20-40k (إشارتا 22k ربحتا +28% و+1.3%)
# 🚫 كاش الرفض: عملة رُفضت لسبب بنيوي (توزيع/عقد) لا تُعاد كل دقيقة
_REJECT_CACHE: dict = {}
_REJECT_TTL = 1800   # نصف ساعة


def _is_rejected(addr: str) -> bool:
    import time as _t
    v = _REJECT_CACHE.get(addr)
    if v and (_t.time() - v) < _REJECT_TTL:
        return True
    if v:
        _REJECT_CACHE.pop(addr, None)
    return False


def _mark_rejected(addr: str):
    import time as _t
    _REJECT_CACHE[addr] = _t.time()
    if len(_REJECT_CACHE) > 800:
        _now = _t.time()
        for k in [k for k, t in _REJECT_CACHE.items() if _now - t > _REJECT_TTL]:
            _REJECT_CACHE.pop(k, None)

MIN_VOL_24 = 8_000      # 🚀 الطازجة بلا تاريخ 24س
AGE_MIN_MIN = 20        # 🚀 صيد الصاروخ: 20د بدل 60
MAX_PUMP_H1 = 200.0     # 🚀 لا نرفض الصاروخ نفسه
MAX_DUMP = -30.0        # تحتها = العملة تنهار أصلاً
MIN_TXNS_H1 = 30        # حياة الآن: معاملات آخر ساعة
# 📊 قياس 240 صفقة: 0.55-0.62 = -391.8% (أسوأ منطقة) | 0.62+ = -9.7% فوز 61%
MIN_BUY_RATIO_H1 = 0.62 # زخم شراء مسيطر فعلاً — 0.55 كانت تُدخل أسوأ منطقة
MIN_AVG_TRADE = 30.0    # متوسط الصفقة بالدولار — أقل = سبام بوتات
WASH_SYMMETRY = 0.03    # تطابق شراء/بيع مريب = تدوير وهمي
MAX_VOL_LIQ_H1 = 20.0   # حجم الساعة مقابل السيولة — فوقه مستحيل طبيعياً
VOL_ACCEL = 1.3         # 🚀 بداية الموجة: تسارع مبكر يكفي (2.0 كان يتحقّق بعد الانفجار)
BASE_TOKENS = {"WBNB", "BNB", "WETH", "ETH", "USDT", "USDC", "BUSD", "DAI",
               "WSOL", "SOL", "CAKE", "FDUSD", "TUSD", "USDE", "STETH"}
MIN_TXNS_24 = 20        # 🚀 خُفّض للطازجة (الحماية في MIN_TXNS_H1=30)

PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"
BOOSTS_URLS = ("https://api.dexscreener.com/token-boosts/top/v1",
               "https://api.dexscreener.com/token-boosts/latest/v1")
SEARCH_QUERIES = ("raydium", "pumpswap", "SOL%2FUSDC", "WBNB", "PancakeSwap", "WETH", "uniswap")
SEARCH_URL = "https://api.dexscreener.com/latest/dex/search?q={q}"
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
    if ((p.get("baseToken") or {}).get("symbol") or "").upper() in BASE_TOKENS:
        return False
    created = (p.get("pairCreatedAt") or 0) / 1000
    if created and (time.time() - created) / 60 < AGE_MIN_MIN:
        return False
    t = (p.get("txns") or {}).get("h24") or {}
    if (t.get("buys", 0) + t.get("sells", 0)) < MIN_TXNS_24:
        return False
    # ⚡ الحراك الحي والتسارع — العمر لا يهم، الزخم يهم
    t1 = (p.get("txns") or {}).get("h1") or {}
    b1 = t1.get("buys", 0) or 0
    s1 = t1.get("sells", 0) or 0
    if (b1 + s1) < MIN_TXNS_H1:
        return False
    if (b1 + s1) > 0 and (b1 / (b1 + s1)) < MIN_BUY_RATIO_H1:
        return False
    v1 = (p.get("volume") or {}).get("h1", 0) or 0
    v24 = (p.get("volume") or {}).get("h24", 0) or 0
    if v24 > 0 and v1 < (v24 / 24) * VOL_ACCEL:
        return False
    # 🤖 كشف الحجم الوهمي — الزخم يجب أن يكون بشرياً حقيقياً
    _tx1 = b1 + s1
    if _tx1 > 0 and v1 > 0 and (v1 / _tx1) < MIN_AVG_TRADE:
        return False
    if _tx1 > 200 and (abs(b1 - s1) / _tx1) < WASH_SYMMETRY:
        return False
    if liq > 0 and v1 > liq * MAX_VOL_LIQ_H1:
        return False
    # 🚫 فيتو الدخول المتأخر والانهيار الجاري
    pc = p.get("priceChange") or {}
    try:
        _h1 = float(pc.get("h1") or 0)
        _h6 = float(pc.get("h6") or 0)
        _h24 = float(pc.get("h24") or 0)
    except Exception:
        _h1 = _h6 = _h24 = 0.0
    if _h1 > MAX_PUMP_H1:
        return False
    if _h6 < MAX_DUMP or _h24 < MAX_DUMP:
        return False
    # 🚫 لا دخول في عملة هابطة الآن — الاتجاه اللحظي يجب أن يكون صاعداً
    if _h1 <= 0:
        return False
    try:
        _m5 = float(pc.get("m5") or 0)
    except Exception:
        _m5 = 0.0
    if _m5 < -3.0:
        return False
    return True


MIN_LOCK_DAYS = 180        # 🔒 عملات راديوم/المطلقة يدوياً: القفل ≥ 6 أشهر


async def _gate0_lp_burned(c, p) -> tuple:
    """🔥 الشرط الإلزامي: سيولة محروقة فقط — لا rug ممكن.
    مثبَت: Fartcoin LP=8.97 🔥 | BOME LP=591M 🔓 | TINCAT (PumpSwap) بلا LP → -99.2%
    """
    from radars.memecoin.lp_burn import lp_is_burned
    _pair = p.get("pairAddress")
    if not _pair:
        return False, "لا عنوان بركة"
    return await lp_is_burned(c, _pair)


async def _gate1_solana(c, addr, pair=None):
    # 🔥 السيولة المحروقة تتخطّى شرطَي القفل والتركيز — الحرق أقوى منهما
    #    (لا يمكن سحب ما أُحرق مفتاحه). الأخطار الحقيقية تبقى مفحوصة.
    _burned = False
    if pair:
        try:
            from radars.memecoin.lp_burn import lp_is_burned
            _burned, _bw = await lp_is_burned(c, pair, addr, WSOL_MINT)
            if _burned:
                log.info("🔥 %s سيولة محروقة — %s", addr[:8], _bw)
        except Exception:
            _burned = False
    try:
        r = await c.get(f"https://api.rugcheck.xyz/v1/tokens/{addr}/report", timeout=15)
        if r.status_code != 200:
            return False, "لا بيانات RugCheck (احترازي)"
        j = r.json()
    except Exception:
        return False, "خطأ RugCheck"

    if j.get("rugged") is True:
        return False, "RugCheck: rugged"

    _lockers = j.get("lockers") or {}
    _liq_total = float(j.get("totalMarketLiquidity") or 0)
    lp = j.get("lpLockedPct", 0) or 0

    if _burned:
        pass   # 🔥 محروقة → لا حاجة لقفل
    elif _lockers:
        if lp < 80:
            return False, f"سيولة مقفلة {lp:.0f}% فقط"
        _dated = [float(v.get("unlockDate") or 0) for v in _lockers.values()]
        _dated = [d for d in _dated if d > 0]
        if _dated:
            _days = (min(_dated) - time.time()) / 86400
            if _days < MIN_LOCK_DAYS:
                return False, f"قفل قصير: {_days:.0f} يوم فقط (المطلوب {MIN_LOCK_DAYS})"
    else:
        if _liq_total < MIN_LIQ:
            return False, f"سيولة ضعيفة ${_liq_total:,.0f} (بلا قفل)"
    # 🔥 المحروقة تتجاهل مخاطر القفل فقط — الحرق أقوى من أي قفل.
    #    (كان يُكتشف الحرق ثم تُرفض بـ"LP Vault unlocked" — 43 مرّة)
    _lock_risks = ("lp vault unlocked", "large amount of lp unlocked",
                   "low liquidity", "lp unlocked")
    for rk in (j.get("risks") or []):
        if (rk.get("level") or "").lower() in ("danger", "high"):
            _nm = (rk.get("name") or "").lower()
            if _burned and any(k in _nm for k in _lock_risks):
                continue
            return False, rk.get("name", "خطر عالٍ")
    # 🔥 المحروقة: نقاط RugCheck تحتسب قفل السيولة — وهو بلا معنى لمن أحرق LP.
    #    Fartcoin score=96 ومخاطرها كلها "LP Vault unlocked" مع 515,171 حاملاً.
    #    نتجاهل النقاط للمحروقة فقط إن لم تكن هناك مخاطر غير قفلية.
    _sn = j.get("score_normalised", 0) or 0
    if _sn > 50:
        _non_lock = [rk for rk in (j.get("risks") or [])
                     if not any(k in (rk.get("name") or "").lower()
                                for k in _lock_risks)]
        if not (_burned and not _non_lock):
            return False, f"نقاط خطر عالية ({_sn})"
    return True, "نجح"


async def _gate1_evm(c, addr, chain):
    # فيتوهات BSC/Ethereum عبر GoPlus
    cid = "56" if chain == "bsc" else "1"
    try:
        r = await c.get(f"https://api.gopluslabs.io/api/v1/token_security/{cid}?contract_addresses={addr}", timeout=12)
        d = (r.json().get("result") or {}).get(addr.lower(), {})
        if len(_GP_CACHE) > 500:
            _GP_CACHE.clear()
        _GP_CACHE[addr.lower()] = d
    except Exception:
        return False, "خطأ GoPlus"
    if not d:
        return False, "غير مفهرس (احترازي)"
    # 🔥 قفل LP إلزامي على EVM — GoPlus يعطيه بدقّة (PIZZA و bNS كانتا 0% وخسرتا)
    _lp = d.get("lp_holders") or []
    _locked = sum(float(h.get("percent", 0) or 0) for h in _lp
                  if str(h.get("is_locked")) == "1") * 100
    if _locked < 80:
        return False, f"LP مقفلة {_locked:.0f}% فقط (المطلوب 80%)"

    checks = [("is_honeypot", "1", "honeypot"),
              ("is_mintable", "1", "mintable"), ("is_open_source", "0", "كود مغلق"),
              ("cannot_sell_all", "1", "منع بيع الكل"), ("hidden_owner", "1", "مالك مخفي"),
              ("can_take_back_ownership", "1", "استرجاع ملكية")]
    for field, bad, name in checks:
        if str(d.get(field)) == bad:
            return False, name
    # 🔓 proxy مسموح بشروط: نمط معماري شائع على BSC (427 رفضاً في 12س)،
    #    لكن الخطر أن يُغيَّر الكود بعد الشراء. نسمح به فقط إن تخلّى المالك
    #    عن الملكية وكان الكود مفتوحاً — فلا أحد يستطيع ترقيته.
    if str(d.get("is_proxy")) == "1":
        _owner = str(d.get("owner_address") or "").lower()
        _renounced = (not _owner) or _owner in (
            "0x0000000000000000000000000000000000000000",
            "0x000000000000000000000000000000000000dead")
        if not _renounced:
            return False, "proxy + مالك فعّال"
        if str(d.get("is_open_source")) != "1":
            return False, "proxy + كود مغلق"
        if str(d.get("selfdestruct")) == "1":
            return False, "proxy + selfdestruct"
    bt = float(d.get("buy_tax") or 0)
    st = float(d.get("sell_tax") or 0)
    if bt > 0.10 or st > 0.10:
        return False, f"ضرائب {bt*100:.0f}/{st*100:.0f}%"
    return True, "نجح"


_GP_CACHE = {}


_AMM_PROGRAMS = {
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "pump.fun",
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA": "pumpswap",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "raydium",
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C": "raydium_cpmm",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "raydium_clmm",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "jupiter",
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo": "meteora",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "orca",
}
SOL_RPC = "https://api.mainnet-beta.solana.com"
NO_BUY_MAX_PCT = 10.0
_RC_CACHE = {}


async def _rugcheck_report(cc, addr):
    # تقرير RugCheck بكاش قصير — البوابتان 2 و2.5 تقرآن منه بنداء واحد
    _hit = _RC_CACHE.get(addr)
    if _hit and time.time() - _hit[0] < 120:
        return _hit[1]
    try:
        r = await cc.get(f"https://api.rugcheck.xyz/v1/tokens/{addr}/report", timeout=12)
        j = r.json() if r.status_code == 200 else None
    except Exception:
        j = None
    if len(_RC_CACHE) > 200:
        _RC_CACHE.clear()
    _RC_CACHE[addr] = (time.time(), j)
    return j


async def _holder_bought_onchain(cc, ata):
    # هل وصلت العملة لهذا الحساب عبر شراء AMM حقيقي؟ (None = تعذّر الفحص)
    try:
        r = await cc.post(SOL_RPC, json={"jsonrpc": "2.0", "id": 1,
                                         "method": "getSignaturesForAddress",
                                         "params": [ata, {"limit": 100}]}, timeout=10)
        sigs = (r.json() or {}).get("result") or []
        if not sigs:
            return None
        first = sigs[-1].get("signature")
        if not first:
            return None
        t = await cc.post(SOL_RPC, json={"jsonrpc": "2.0", "id": 1,
                                         "method": "getTransaction",
                                         "params": [first, {"encoding": "jsonParsed",
                                                            "maxSupportedTransactionVersion": 0}]}, timeout=12)
        res = (t.json() or {}).get("result") or {}
        progs = set()
        for ins in ((res.get("transaction") or {}).get("message") or {}).get("instructions", []) or []:
            progs.add(ins.get("programId", ""))
        for ig in ((res.get("meta") or {}).get("innerInstructions") or []):
            for ins in ig.get("instructions", []) or []:
                progs.add(ins.get("programId", ""))
        if not progs:
            return None
        return any(p in _AMM_PROGRAMS for p in progs)
    except Exception:
        return None


async def _gate25_onchain(cc, addr, pair=None):
    # البوابة 2.5: إثبات الشراء الحقيقي على البلوكشين لأعلى الحاملين
    j = await _rugcheck_report(cc, addr)
    if not j:
        return True, "تعذّر التقرير"
    # 💎 إعفاء الناضجة المحروقة: البوابة تكشف "توزيع المطوّر على محافظ الإطلاق".
    #    في عملة بـ515k حامل، أعلى الحاملين منصّات وصناديق تستلم تحويلات بطبيعتها.
    #    شرطان معاً: سيولة محروقة (لا سحب) + توزيع واسع (لا محفظة تُسقط السعر).
    _h = int(j.get("totalHolders") or 0)
    if _h >= 10000 and pair:
        try:
            from radars.memecoin.lp_burn import lp_is_burned
            _b, _bw = await lp_is_burned(cc, pair, addr, WSOL_MINT)
            if _b:
                return True, f"ناضجة محروقة ({_h:,} حامل) — إعفاء مبرَّر"
        except Exception:
            pass
    th = j.get("topHolders") or []
    if len(th) < 2:
        return True, "لا حاملين"
    no_buy = 0.0
    checked = 0
    for h in th[1:6]:
        pct = h.get("pct") or 0
        ata = h.get("address")
        if pct < 1.0 or not ata:
            continue
        bought = await _holder_bought_onchain(cc, ata)
        if bought is None:
            continue
        checked += 1
        if not bought:
            no_buy += pct
    if checked and no_buy > NO_BUY_MAX_PCT:
        return False, f"توزيع بلا شراء: {no_buy:.0f}% استلموا تحويلاً"
    return True, "نجح"


BSC_RPC = "https://bsc-mainnet.nodereal.io/v1/64a9df0874fb4a93b9d0a3849de012d3"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
BSC_BLOCK_SEC = 0.75
BSC_SPAN = 20000
BSC_MAX_BATCHES = 10


async def _bsc_rpc(cc, method, params):
    try:
        r = await cc.post(BSC_RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=20)
        return (r.json() or {}).get("result")
    except Exception:
        return None


async def _gate25_evm(cc, tok, pair, created_ms):
    # البوابة 2.5 لـ BNB: من اشترى فعلاً من الزوج، ومن استلم تحويلاً مجانياً
    if not pair:
        return True, "لا زوج"
    if created_ms and (time.time() * 1000 - created_ms) > 7 * 24 * 3600 * 1000:
        return True, "عملة ناضجة"
    d = _GP_CACHE.get((tok or "").lower())
    hs = (d or {}).get("holders") or []
    humans = []
    for h in hs:
        try:
            pct = float(h.get("percent") or 0) * 100
        except Exception:
            continue
        a = (h.get("address") or "").lower()
        if pct >= 1.0 and a and not (h.get("tag") or "") and str(h.get("is_contract")) != "1":
            humans.append((pct, a))
    if not humans:
        return True, "لا حاملين بشر"
    bn = await _bsc_rpc(cc, "eth_blockNumber", [])
    if not bn:
        return True, "تعذّر RPC"
    latest = int(bn, 16)
    age_sec = ((time.time() * 1000) - created_ms) / 1000 if created_ms else 86400
    span_total = min(int(max(age_sec, 600) / BSC_BLOCK_SEC) + 200, BSC_SPAN * BSC_MAX_BATCHES)
    start = max(0, latest - span_total)
    _pad = lambda a: "0x" + "0" * 24 + a[2:].lower()
    buyers = set()
    scanned = False
    for i in range(BSC_MAX_BATCHES):
        fb = start + i * BSC_SPAN
        if fb > latest:
            break
        tb = min(fb + BSC_SPAN, latest)
        logs = await _bsc_rpc(cc, "eth_getLogs", [{"fromBlock": hex(fb), "toBlock": hex(tb),
                                                   "address": tok, "topics": [TRANSFER_TOPIC, _pad(pair)]}])
        if not isinstance(logs, list):
            continue
        scanned = True
        for lg in logs:
            tp = lg.get("topics") or []
            if len(tp) >= 3:
                buyers.add("0x" + tp[2][-40:].lower())
    if not scanned:
        return True, "تعذّر المسح"
    no_buy = sum(pct for pct, a in humans if a not in buyers)
    if no_buy > NO_BUY_MAX_PCT:
        return False, f"توزيع بلا شراء: {no_buy:.0f}% استلموا تحويلاً"
    return True, "نجح"


async def _gate2_evm(cc, addr, chain):
    # البوابة 2 لشبكات EVM: توزيع الحاملين من GoPlus (استثناء العقود والمجمّعات، النسب كسور ×100)
    d = _GP_CACHE.get(addr.lower())
    if d is None:
        cid = "56" if chain == "bsc" else "1"
        try:
            r = await cc.get(f"https://api.gopluslabs.io/api/v1/token_security/{cid}?contract_addresses={addr}", timeout=12)
            d = (r.json().get("result") or {}).get(addr.lower(), {})
        except Exception:
            return False, "خطأ تقرير الحاملين"
    if not d:
        return False, "لا بيانات حاملين (احترازي)"
    try:
        _cp = float(d.get("creator_percent") or 0) * 100
        _op = float(d.get("owner_percent") or 0) * 100
    except Exception:
        _cp = _op = 0.0
    if _cp > 5:
        return False, f"المنشئ يملك {_cp:.0f}%"
    if _op > 5:
        return False, f"المالك يملك {_op:.0f}%"
    hs = d.get("holders") or []
    if not hs:
        return False, "لا بيانات حاملين (احترازي)"
    _human = []
    for h in hs:
        try:
            _pct = float(h.get("percent") or 0) * 100
        except Exception:
            _pct = 0.0
        _tag = str(h.get("tag") or "").lower()
        _safe_tag = any(k in _tag for k in ("lock", "burn", "null", "dead", "pair",
                                            "pool", "router", "liquidity"))
        # عقد غير معروف الوسم يُحسب: قد يكون محفظة منشئ متنكّرة (ثغرة رَغ)
        if not _safe_tag:
            _human.append(_pct)
    if _human and max(_human) > 15:
        return False, f"حامل فرد يملك {max(_human):.0f}%"
    if sum(_human) > 30:
        return False, f"تركيز بشري: {sum(_human):.0f}%"
    return True, "نجح"


async def _gate2_solana(cc, addr):
    # البوابة 2: توزيع الحاملين وشبكات الداخليين — صائد التوزيع على محافظ لحظة الإطلاق
    j = await _rugcheck_report(cc, addr)
    if not j:
        return False, "لا تقرير حاملين (احترازي)"
    th = j.get("topHolders") or []
    if not th:
        return False, "لا بيانات حاملين (احترازي)"
    _ins = sum((h.get("pct") or 0) for h in th if h.get("insider"))
    if _ins > 5:
        return False, f"داخليون يملكون {_ins:.0f}%"
    # 📊 insiderNetworks يرصد التحويلات لا الملكية — USELESS: 532 محفظة "شبكة"
    #    لكن حصّة الداخليين 0.00% و136,854 حاملاً. المقياس الصحيح هو الحصّة (_ins أعلاه).
    #    نرفض الشبكة فقط إن كانت حصّتها معتبرة أو الحاملون قليلين (عملة صغيرة مُسيطَر عليها).
    _nets = j.get("insiderNetworks") or []
    _holders = int(j.get("totalHolders") or 0)
    if _nets and (_ins > 2.0 or _holders < 2000):
        return False, f"شبكة داخليين ({_ins:.1f}% · {_holders} حامل)"
    _rest = sum((h.get("pct") or 0) for h in th[1:10])
    if _rest > 30:
        return False, f"تركيز موزّع: الحاملون 2-10 يملكون {_rest:.0f}%"
    if len(th) > 1 and (th[1].get("pct") or 0) > 15:
        return False, f"حامل فرد يملك {(th[1].get('pct') or 0):.0f}%"
    return True, "نجح"


async def _gate1(c, chain, addr, pair=None):
    if chain == "solana":
        return await _gate1_solana(c, addr, pair)
    return await _gate1_evm(c, addr, chain)


# ═══════ 💎 المسار الثاني: العملات الناضجة (تصحيح في اتجاه صاعد) ═══════
#   مسارَان يعملان معاً: الصاروخ يُقاس بالانفجار، والناضجة بالعمق والاستمرار.
#   Fartcoin/USELESS: سيولة بالملايين وحاملون بالآلاف — نقاطها 35 بتنقيط الصواريخ
#   لكنها أأمن بكثير وتعيش شهوراً. ندخلها عند التصحيح لا عند القمة.
MATURE_MIN_LIQ = 200_000
MATURE_MIN_VOL24 = 300_000
MATURE_MIN_HOLDERS = 2000
MATURE_DIP_LOW = -35.0
MATURE_DIP_HIGH = -3.0
MATURE_MIN_BUY = 0.50
MATURE_SCORE_MIN = 60


def _score_mature(p, holders: int = 0) -> int:
    """💎 تنقيط الناضجة: العمق والتوزيع والاستمرار — لا الانفجار."""
    pts = 0.0
    liq = (p.get("liquidity") or {}).get("usd", 0) or 0
    vol = (p.get("volume") or {}).get("h24", 0) or 0
    pts += min(30.0, liq / 1_000_000 * 30)
    pts += min(25.0, vol / 2_000_000 * 25)
    pts += min(20.0, (holders / 20000) * 20)
    t = (p.get("txns") or {}).get("h24") or {}
    b = t.get("buys", 0) or 0
    s = t.get("sells", 0) or 0
    if (b + s) > 0:
        pts += min(10.0, (b / (b + s)) * 18)
    pc = p.get("priceChange") or {}
    try:
        h24 = float(pc.get("h24") or 0)
        h1 = float(pc.get("h1") or 0)
    except Exception:
        h24 = h1 = 0.0
    if MATURE_DIP_LOW <= h24 <= MATURE_DIP_HIGH:
        pts += 10
        if h1 > 0:
            pts += 5
    return min(100, round(pts))


def _mature_qualifies(p, holders: int = 0) -> tuple:
    """هل هي ناضجة ومؤهّلة للدخول عند التصحيح؟"""
    liq = (p.get("liquidity") or {}).get("usd", 0) or 0
    vol = (p.get("volume") or {}).get("h24", 0) or 0
    if liq < MATURE_MIN_LIQ:
        return False, f"عمق {liq:,.0f}"
    if vol < MATURE_MIN_VOL24:
        return False, f"حجم {vol:,.0f}"
    if holders and holders < MATURE_MIN_HOLDERS:
        return False, f"حاملون {holders}"
    pc = p.get("priceChange") or {}
    try:
        h24 = float(pc.get("h24") or 0)
    except Exception:
        h24 = 0.0
    if not (MATURE_DIP_LOW <= h24 <= MATURE_DIP_HIGH):
        return False, f"ليست في تصحيح (h24 {h24:+.0f}%)"
    t = (p.get("txns") or {}).get("h24") or {}
    b = t.get("buys", 0) or 0
    s = t.get("sells", 0) or 0
    if (b + s) > 0 and (b / (b + s)) < MATURE_MIN_BUY:
        return False, "بائعون مسيطرون"
    return True, "ناضجة مؤهّلة"


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


# ═══════ 🚀 الدخول المبكر: أمان أولاً ثم مراقبة تدفّق لحظي ═══════
EARLY_MIN_LIQ        = 20_000
EARLY_WATCH_MAX      = 20  # ✅ أُعيد بعد سدّ ثغرة نسبة الشراء (FOXVSHEEP)
EARLY_WATCH_TTL      = 2700
EARLY_MIN_TRADES_60  = 8
EARLY_MIN_BUY_RATIO  = 0.60
EARLY_MIN_VOL_RATIO  = 0.60
EARLY_ACCEL          = 1.3
EARLY_MAX_PUMP       = 60.0
EARLY_WATCH: dict = {}


def _gate0_early(p):
    """🚀 أمان وجودة فقط — بلا شروط تراكمية."""
    if p.get("chainId") not in CHAINS:
        return False
    liq = (p.get("liquidity") or {}).get("usd", 0) or 0
    if liq < EARLY_MIN_LIQ:
        return False
    if ((p.get("baseToken") or {}).get("symbol") or "").upper() in BASE_TOKENS:
        return False
    t1 = (p.get("txns") or {}).get("h1") or {}
    b1 = (t1.get("buys", 0) or 0) + (t1.get("sells", 0) or 0)
    v1 = (p.get("volume") or {}).get("h1", 0) or 0
    if b1 > 0 and v1 > 0 and (v1 / b1) < MIN_AVG_TRADE:
        return False
    # 🚫 لا دخول والبائعون مسيطرون — الثغرة التي أدخلت FOXVSHEEP (45% مشترين) وخسرت -66.5%
    _buys = (t1.get("buys", 0) or 0)
    _sells = (t1.get("sells", 0) or 0)
    if (_buys + _sells) > 0 and (_buys / (_buys + _sells)) < MIN_BUY_RATIO_H1:
        return False
    if liq > 0 and v1 > liq * MAX_VOL_LIQ_H1:
        return False
    pc = p.get("priceChange") or {}
    try:
        _h6 = float(pc.get("h6") or 0); _h24 = float(pc.get("h24") or 0)
        _m5 = float(pc.get("m5") or 0)
    except Exception:
        _h6 = _h24 = _m5 = 0.0
    if _h6 < MAX_DUMP or _h24 < MAX_DUMP:
        return False
    if _m5 < -3.0:
        return False
    return True


def early_watch_add(addr, symbol):
    if not addr or addr in EARLY_WATCH:
        return False
    if len(EARLY_WATCH) >= EARLY_WATCH_MAX:
        return False
    EARLY_WATCH[addr] = {"symbol": symbol or "?", "added": time.time()}
    log.info("🚀👁 مراقبة مبكرة: %s (المراقَبون %d)", symbol, len(EARLY_WATCH))
    return True


async def early_watch_loop():
    """🚀 يدخل لحظة تسارع الشراء الحقيقي."""
    from radars.memecoin.live_stream import get_flow, unwatch_token
    log.info("🚀🐸 مراقب الدخول المبكر بدأ")
    while True:
        try:
            now = time.time()
            for addr in list(EARLY_WATCH.keys()):
                info = EARLY_WATCH.get(addr) or {}
                sym = info.get("symbol", "?")
                if now - (info.get("added") or 0) > EARLY_WATCH_TTL:
                    EARLY_WATCH.pop(addr, None)
                    try:
                        await unwatch_token(addr)
                    except Exception:
                        pass
                    log.info("🚀👁 انتهت مهلة المراقبة: %s", sym)
                    continue
                f60 = get_flow(addr, 60.0)
                if not f60 or f60["trades"] < EARLY_MIN_TRADES_60:
                    continue
                if f60["buy_ratio"] < EARLY_MIN_BUY_RATIO or f60["vol_ratio"] < EARLY_MIN_VOL_RATIO:
                    continue
                f180 = get_flow(addr, 180.0)
                if f180 and f180["trades"] > 0:
                    if f60["trades"] < (f180["trades"] / 3.0) * EARLY_ACCEL:
                        continue
                if _meme_seen(addr):
                    EARLY_WATCH.pop(addr, None)
                    continue
                try:
                    async with httpx.AsyncClient() as cc:
                        pairs = await _fetch_pairs(cc, addr)
                        if not pairs:
                            continue
                        p = max(pairs, key=lambda x: (x.get("liquidity") or {}).get("usd", 0) or 0)
                        pc = p.get("priceChange") or {}
                        try:
                            _h1 = float(pc.get("h1") or 0)
                        except Exception:
                            _h1 = 0.0
                        if _h1 > EARLY_MAX_PUMP:
                            EARLY_WATCH.pop(addr, None)
                            await unwatch_token(addr)
                            log.info("🚀🚫 %s فات الوقت (h1 %+.0f%%)", sym, _h1)
                            continue
                        sc = _score(p)
                        # 🛡️ الثغرة: كان يُصدر بلا فحص العتبة (CREPE نقاط 60)
                        _need = EVM_SIGNAL_THRESHOLD if p.get("chainId") in ("bsc", "ethereum") else SIGNAL_THRESHOLD
                        if sc < _need:
                            EARLY_WATCH.pop(addr, None)
                            log.info("🚀🚫 %s نقاط %d < %d — لا دخول", sym, sc, _need)
                            continue
                        _meme_save(p, sc)
                        await _meme_broadcast(p, sc)
                        EARLY_WATCH.pop(addr, None)
                        log.info("🚀🐸 دخول مبكر: %s | صفقات60=%d شراء=%.0f%% حجم=%.0f%% score=%d",
                                 sym, f60["trades"], f60["buy_ratio"] * 100, f60["vol_ratio"] * 100, sc)
                except Exception as e:
                    log.warning("🚀 دخول مبكر %s: %s", sym, e)
        except Exception as e:
            log.warning("early watch loop: %s", e)
        await asyncio.sleep(10)


async def _discover(cc):
    """مصدر موسّع: البروفايلات + المعزّزة + بحث مستهدف لكل شبكة.
    يرجع (قائمة عناوين للفحص، خريطة أزواج جاهزة من البحث)."""
    addrs = {}
    ready = {}
    tasks = [_fetch_profiles(cc)]
    for u in BOOSTS_URLS:
        tasks.append(_fetch_json(cc, u))
    for q in SEARCH_QUERIES:
        tasks.append(_fetch_json(cc, SEARCH_URL.format(q=q)))
    res = await asyncio.gather(*tasks, return_exceptions=True)
    for item in res:
        if isinstance(item, Exception) or item is None:
            continue
        if isinstance(item, list):
            for x in item:
                ch, ad = x.get("chainId"), x.get("tokenAddress")
                if ch in CHAINS and ad:
                    addrs[ad] = ch
        elif isinstance(item, dict):
            for pr in (item.get("pairs") or []):
                ch = pr.get("chainId")
                ad = (pr.get("baseToken") or {}).get("address")
                if ch in CHAINS and ad:
                    addrs[ad] = ch
                    _prev = ready.get(ad)
                    if not _prev or ((pr.get("liquidity") or {}).get("usd", 0) or 0) > ((_prev.get("liquidity") or {}).get("usd", 0) or 0):
                        ready[ad] = pr
    return addrs, ready


async def _fetch_json(cc, url):
    try:
        r = await cc.get(url, timeout=15)
        return r.json()
    except Exception:
        return None


async def scan():
    """يرصد العملات الجديدة، يمرّرها على البوابة 0 (متوازياً)، يرجع الناجين."""
    async with httpx.AsyncClient() as c:
        _addrs, _ready = await _discover(c)
        cands = [(ch, ad) for ad, ch in _addrs.items()]

        async def _check(chain, addr):
            best = _ready.get(addr)
            if best is None:
                pairs = await _fetch_pairs(c, addr)
                if not pairs:
                    return None
                best = max(pairs, key=lambda x: (x.get("liquidity") or {}).get("usd", 0) or 0)
            # 💎 مساران: الصاروخ يُقاس بالزخم، والناضجة بالعمق والتصحيح.
            #    كانت الناضجة تُرفض عند _gate0 فلا تصل لمسارها أبداً
            #    (USELESS $1.5M · MUSHU · aura — كلها محروقة ونظيفة ومُهدرة).
            if not _gate0(best):
                _mok, _mwhy = _mature_qualifies(best, 0)
                if not _mok:
                    return None
                log.info("💎 %s: هادئة لكن ناضجة — تُفحص كناضجة (%s)",
                         (best.get("baseToken") or {}).get("symbol", "?"), _mwhy)
            ok, reason = await _gate1(c, chain, addr, best.get("pairAddress"))
            if not ok:
                log.info("🐸🚫 %s (%s) بوابة1: %s", (best.get("baseToken") or {}).get("symbol", "?"), chain, reason)
                _mark_rejected(addr)
                return None
            mark_verified(addr, "بوابة1")
            ok2, reason2 = (await _gate2_solana(c, addr)) if chain == "solana" else (await _gate2_evm(c, addr, chain))
            if not ok2:
                log.info("🐸🚫 %s (%s) بوابة2: %s", (best.get("baseToken") or {}).get("symbol", "?"), chain, reason2)
                _mark_rejected(addr)
                return None
            if chain == "solana":
                ok25, reason25 = await _gate25_onchain(c, addr, best.get("pairAddress"))
            elif chain == "bsc":
                ok25, reason25 = await _gate25_evm(c, addr, best.get("pairAddress"), best.get("pairCreatedAt"))
            else:
                ok25, reason25 = True, ""
            if not ok25:
                log.info("🐸🚫 %s (%s) بوابة2.5: %s", (best.get("baseToken") or {}).get("symbol", "?"), chain, reason25)
                _mark_rejected(addr)
                return None
            return best

        res = await asyncio.gather(*[_check(ch, a) for ch, a in cands])
        return [r for r in res if r]


MEME_DB = os.path.join(os.path.dirname(__file__), "..", "..", "db", "memecoin.db")
MEME_CHANNEL = "-1003918596088"
# 📊 تحليل 241 صفقة — المزيج الرابح الوحيد:
#    score ≥92 + شراء ≥0.62 = 92 صفقة · فوز 63% · صافي +87.8%
#    بينما score 88-92 وحدها = -377.3% (فوز 26%) — أسوأ منطقة
#    والساعات 0-6 UTC = -448.1% (ميتة) | 12-18 UTC = +56.4% (الوحيدة الموجبة)
SIGNAL_THRESHOLD = 92   # 🔥 أُعيد — الآن بشرط حرق السيولة الإلزامي
# 📊 BSC خسرت -56.9% (11 صفقة) و ETH -36.5% (3) — عتبة أعلى للشبكات الخاسرة
EVM_SIGNAL_THRESHOLD = 80
DEAD_HOURS_UTC = (0, 1, 2, 3, 4, 5)   # ساعات خاسرة مثبتة


def _init_meme_db():
    os.makedirs(os.path.dirname(MEME_DB), exist_ok=True)
    conn = sqlite3.connect(MEME_DB)
    conn.execute("CREATE TABLE IF NOT EXISTS meme_signals(id INTEGER PRIMARY KEY, symbol TEXT, address TEXT UNIQUE, chain TEXT, score INTEGER, liq REAL, vol REAL, url TEXT, ts INTEGER, active INTEGER DEFAULT 1)")
    for _col, _def in (("entry_price", "REAL"), ("status", "TEXT DEFAULT 'open'"), ("exit_price", "REAL"),
                       ("pnl_pct", "REAL"), ("peak_price", "REAL"), ("closed_ts", "INTEGER"), ("buys_ratio", "REAL"), ("last_price", "REAL")):
        try: conn.execute(f"ALTER TABLE meme_signals ADD COLUMN {_col} {_def}")
        except Exception: pass
    conn.commit(); conn.close()


SEEN_TTL = 86400   # 🕐 الحظر 24 ساعة لا للأبد


def _meme_seen(addr):
    """محظورة إن كانت مفتوحة الآن، أو صدرت خلال 24 ساعة.
    كان الحظر أبدياً: 294 عملة مُستبعدة نهائياً حتى لو انفجرت لاحقاً."""
    try:
        conn = sqlite3.connect(MEME_DB)
        r = conn.execute(
            "SELECT 1 FROM meme_signals WHERE address=? AND "
            "(status='open' OR ts > ?)",
            (addr, int(time.time()) - SEEN_TTL)).fetchone()
        conn.close(); return bool(r)
    except Exception:
        return False


# ═══ 🛡️ الحارس الموحّد: لا إصدار بلا تحقّق مسبق ═══
#   المشكلة التي يحلّها: 5 مسارات تُصدر إشارات، وكلٌّ بحراسته الخاصة —
#   فثغرة في واحد تُبطل كل الحماية. الآن نقطة تحكّم واحدة لا تُتجاوز.
_VERIFIED: dict = {}          # address -> (وقت التحقّق, سبب)
VERIFY_TTL = 600              # صلاحية التحقّق 10 دقائق


def mark_verified(addr: str, why: str = ""):
    """تُستدعى بعد اجتياز بوابة1 (التي تفحص الحرق/القفل)."""
    if addr:
        _VERIFIED[addr] = (time.time(), why)
        if len(_VERIFIED) > 500:
            _now = time.time()
            for k in [k for k, v in _VERIFIED.items() if _now - v[0] > 3600]:
                _VERIFIED.pop(k, None)


def is_verified(addr: str) -> bool:
    v = _VERIFIED.get(addr or "")
    return bool(v and (time.time() - v[0]) < VERIFY_TTL)


def _meme_save(p, sc):
    # 🛡️ الحارس: لا تُسجَّل إشارة لعملة لم تجتز بوابة الأمان (حرق/قفل)
    _a = (p.get("baseToken") or {}).get("address", "")
    if not is_verified(_a):
        log.warning("🛡️🚫 %s: إصدار بلا تحقّق أمان — مُنع",
                    (p.get("baseToken") or {}).get("symbol", "?"))
        return
    b = p.get("baseToken") or {}
    try:
        conn = sqlite3.connect(MEME_DB)
        _t = (p.get("txns") or {}).get("h24") or {}
        _tt = (_t.get("buys", 0) or 0) + (_t.get("sells", 0) or 0)
        _ratio = ((_t.get("buys", 0) or 0) / _tt) if _tt else 0
        _px = float(p.get("priceUsd") or 0)
        # 📊 كان INSERT OR IGNORE يتجاهل الإشارة الجديدة بصمت لأن address UNIQUE
        #    (KM بُثَّت 22:42 ولم تُحفَظ لوجود سجلّ من 10:32) — REPLACE يحدّث السجل
        # 📊 حالة العملة لحظة الدخول — بلا هذا لا نعرف إن دخلنا في البداية أم الذروة
        _pc = p.get("priceChange") or {}
        _t1 = (p.get("txns") or {}).get("h1") or {}
        _tx1 = (_t1.get("buys", 0) or 0) + (_t1.get("sells", 0) or 0)
        conn.execute("INSERT INTO meme_signals(symbol,address,chain,score,liq,vol,url,ts,entry_price,status,peak_price,buys_ratio,h1_at_entry,h6_at_entry,h24_at_entry,vol_h1,txns_h1) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (b.get("symbol", "?"), b.get("address", ""), p.get("chainId"), sc,
                      (p.get("liquidity") or {}).get("usd", 0), (p.get("volume") or {}).get("h24", 0),
                      p.get("url", ""), int(time.time()), _px, "open", _px, _ratio,
                      float(_pc.get("h1") or 0), float(_pc.get("h6") or 0),
                      float(_pc.get("h24") or 0),
                      (p.get("volume") or {}).get("h1", 0) or 0, _tx1))
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
        from services.notifier import push_note
        await push_note("meme", "signal", f"🐸 إشارة ميم: {b.get('symbol','?')} ({p.get('chainId')}) — {sc}/100")
    except Exception as e:
        log.warning("meme broadcast: %s", e)


_SL_PENDING: dict = {}
_SAFETY_LAST: dict = {}          # 🛡️ آخر فحص أمان لكل صفقة
SAFETY_RECHECK_SEC = 20          # 🚨 السحب يقع في دقيقة — لا مؤشّر يسبقه
LIQ_DRAIN_EXIT = 0.85            # 🚨 أي انخفاض 15% في البركة = خروج فوري
MAX_HOLD_MIN = 90                # ⏰ نافذة التعرّض
# 📊 تحليل 248 صفقة: 65 صفقة "لم تصعد" خسرت -1603% بفوز 2% فقط
#    الصفقة التي لا تصعد 3% في أول 10 دقائق لن تصعد — خروج فوري
EARLY_EXIT_MIN = 10              # مهلة إثبات الحركة
EARLY_EXIT_MIN_RISE = 3.0        # الحد الأدنى للصعود خلال المهلة

# 🌊 عتبات الخروج التدفّقي للميم (تُضبط بالقياس)
MEME_FLOW_WINDOW = 180.0
MEME_MIN_FLOW_TRADES = 8
MEME_SELL_VOL = 0.35
MEME_SELL_BUYRATIO = 0.50
MEME_SELL_CONFIRM = 60.0
# 📊 قياس: الأرضية -18% لكن متوسط الخاسر الفعلي -23.7% (تُخترق بين النبضات)
#    -12% تجعل الخسارة الفعلية ~16% فتصير النسبة رابحة مع فوز 53%
MEME_HARD_FLOOR = -12.0
MEME_WICK_PNL = -35.0        # 🕯️ أسوأ من هذا في نبضة واحدة = ذيل مشتبه به
_WICK_SEEN: dict = {}        # id -> (وقت أول قراءة كارثية, سعرها)
# 📊 القياس: متوسط التراجع عن القمة قبل الخروج 18.2% · و46 صفقة تركنا فيها >25%
MEME_TRAIL_ARM = 6.0        # نحمي من +6% بدل +12%
MEME_TRAIL_GIVEBACK = 10.0  # تراجع 10% عن القمة يقفل
# 📊 146 صفقة صعدت +10%+ وربحت 84% منها (+1,737.9%)
#    لكن تراجع 10% ثابت يبتلع كل ربح صفقة بلغت +10% (تُغلق عند 0.0%)
#    سلّم متدرّج: كلّما علت القمة زاد المسموح — ويُحفظ دائماً نصفها على الأقل
MEME_GIVE_LADDER = ((25.0, 8.0), (18.0, 6.0), (12.0, 5.0), (6.0, 3.0))
MEME_PEAK_LOCK = 20.0       # فوق +20% نحمي بصرامة أعلى
MEME_PEAK_LOCK_GIVE = 7.0   # تراجع 7% فقط يقفل الرابح الكبير


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
        from services.notifier import push_note
        await push_note("meme", "closed", f"{emoji} إغلاق ميم: {r.get('symbol','?')} {pnl:+.1f}% — {reason}")
    except Exception as e:
        log.warning("meme close bc: %s", e)


async def _meme_track_one(cc, r):
    # ⚡ السعر اللحظي من تيار الصفقات أولاً — يضرب الوقف على الحركة الحقيقية
    px = 0.0
    try:
        from radars.memecoin.live_stream import get_live_price, watch_token, _watch_trades
        if r["address"] not in _watch_trades:
            await watch_token(r["address"])
        _lp = get_live_price(r["address"])
        if _lp:
            px = float(_lp)
    except Exception:
        px = 0.0
    if px <= 0:
        pairs = await _fetch_pairs(cc, r["address"])
        if not pairs:
            return
        best = max(pairs, key=lambda x: (x.get("liquidity") or {}).get("usd", 0) or 0)
        px = float(best.get("priceUsd") or 0)
    entry = float(r.get("entry_price") or 0)
    if px <= 0 or entry <= 0:
        return
    pnl = (px - entry) / entry * 100
    try:
        _lc = sqlite3.connect(MEME_DB)
        _lc.execute("UPDATE meme_signals SET last_price=? WHERE id=?", (px, r["id"]))
        _lc.commit(); _lc.close()
    except Exception:
        pass
    # 🛡️ حارس أمان بعد الدخول: الخطر قد يظهر بعد الشراء
    _sid_g = r["id"]
    if time.time() - _SAFETY_LAST.get(_sid_g, 0) >= SAFETY_RECHECK_SEC:
        _SAFETY_LAST[_sid_g] = time.time()
        # 🚨 سحب السيولة: أخطر من أي فحص — البركة تُفرَّغ في دقائق
        try:
            _lp = await _fetch_pairs(cc, r["address"])
            if _lp:
                _bp = max(_lp, key=lambda x: (x.get("liquidity") or {}).get("usd", 0) or 0)
                _now_liq = float((_bp.get("liquidity") or {}).get("usd", 0) or 0)
                _base_liq = float(r.get("liq") or 0)
                if _base_liq > 0 and _now_liq < _base_liq * LIQ_DRAIN_EXIT:
                    log.warning("🚨 %s سحب سيولة: $%.0f → $%.0f (%.0f%%) — خروج فوري",
                                r.get("symbol"), _base_liq, _now_liq,
                                _now_liq / _base_liq * 100)
                    try:
                        from radars.memecoin.live_stream import unwatch_token
                        await unwatch_token(r["address"])
                    except Exception:
                        pass
                    _meme_close(r["id"], px, pnl)
                    await _meme_close_broadcast(r, px, pnl, "🚨 سحب سيولة")
                    _SL_PENDING.pop(_sid_g, None)
                    _SAFETY_LAST.pop(_sid_g, None)
                    return
        except Exception as _le:
            log.debug("liq drain check: %s", _le)
        # 🛡️ الحارس يفحص ما يتغيّر فقط (سحب السيولة أعلاه · rugged) —
        #    لا شروط الدخول التي قبلناها. كان يُغلق KM بعد ثانية بـ"قفل 0%"
        #    بينما الرادار قبلها كمحروقة (LP=11.23).
        _ok_s, _why_s = True, ""
        try:
            _rc = await _rugcheck_report(cc, r["address"])
            if _rc and _rc.get("rugged"):
                _ok_s, _why_s = False, "rugged مؤكَّد"
        except Exception:
            pass
        if not _ok_s:
            log.warning("🛡️🚨 %s خطر أمان بعد الدخول: %s — إغلاق فوري", r.get("symbol"), _why_s)
            try:
                from radars.memecoin.live_stream import unwatch_token
                await unwatch_token(r["address"])
            except Exception:
                pass
            _meme_close(r["id"], px, pnl)
            await _meme_close_broadcast(r, px, pnl, f"🛡️ أمان: {_why_s}")
            _SL_PENDING.pop(_sid_g, None)
            _SAFETY_LAST.pop(_sid_g, None)
            return
    peak = max(float(r.get("peak_price") or entry), px)
    if peak > float(r.get("peak_price") or 0):
        _meme_peak(r["id"], peak)
    peak_pnl = (peak - entry) / entry * 100
    reason = None
    _age_h = (time.time() - (r.get("ts") or 0)) / 3600
    _sid = r["id"]
    _flow = None
    try:
        from radars.memecoin.live_stream import get_flow
        _flow = get_flow(r["address"], MEME_FLOW_WINDOW)
    except Exception:
        _flow = None
    _trades = (_flow or {}).get("trades", 0) or 0
    _buy_ratio = (_flow or {}).get("buy_ratio", 0.0) or 0.0
    _vol_ratio = (_flow or {}).get("vol_ratio", 0.0) or 0.0
    # 🕯️ حارس الذيل: انهيار كارثي في نبضة واحدة قد يكون ذيلاً يرتدّ.
    #    FOXVSHEEP بِيعت عند -66.5% ثم عاد السعر 3 أضعاف — لا نبيع بلا تأكيد قراءتين.
    if pnl <= MEME_WICK_PNL:
        _w = _WICK_SEEN.get(_sid)
        if not _w:
            _WICK_SEEN[_sid] = (time.time(), px)
            log.warning("🕯️ %s قراءة كارثية %.1f%% — انتظار تأكيد نبضة", r.get("symbol"), pnl)
            return
        _wt, _wpx = _w
        if px > _wpx * 1.15:
            # ارتدّ أكثر من 15% عن قراءة الذيل → كان ذيلاً، نتابع الصفقة
            _WICK_SEEN.pop(_sid, None)
            log.info("🕯️ %s كان ذيلاً — ارتدّ، نتابع", r.get("symbol"))
            return
        _WICK_SEEN.pop(_sid, None)
        # مؤكَّد: انهيار حقيقي → إغلاق
    else:
        _WICK_SEEN.pop(_sid, None)

    if pnl <= MEME_HARD_FLOOR:
        reason = "🛑 أرضية أمان -18%"
        _SL_PENDING.pop(_sid, None)
    elif _trades >= MEME_MIN_FLOW_TRADES:
        if _vol_ratio < MEME_SELL_VOL:
            reason = "🔻 بيع: سيطرة بائعين على الحجم"
            _SL_PENDING.pop(_sid, None)
        elif _buy_ratio < MEME_SELL_BUYRATIO:
            _p = _SL_PENDING.get(_sid)
            if not _p:
                _SL_PENDING[_sid] = time.time()
                log.info("🌊 %s تضاؤل مشترين — انتظار تأكيد %ds", r.get("symbol"), int(MEME_SELL_CONFIRM))
            elif time.time() - _p >= MEME_SELL_CONFIRM:
                reason = "🔻 بيع: تضاؤل المشترين (مؤكَّد)"
                _SL_PENDING.pop(_sid, None)
        else:
            _SL_PENDING.pop(_sid, None)
    else:
        _SL_PENDING.pop(_sid, None)
        _give = MEME_TRAIL_GIVEBACK
        for _lvl, _g in MEME_GIVE_LADDER:
            if peak_pnl >= _lvl:
                _give = _g
                break
        if peak_pnl >= MEME_TRAIL_ARM and pnl <= peak_pnl - _give:
            reason = "🔒 قفل: تراجع عن القمة"
    if not reason:
        if _age_h >= 2 and abs(pnl) < 2 and (peak_pnl or 0) < 4:
            reason = "⏱ خروج: لا حركة في ساعتين"
        elif (time.time() - (r.get("ts") or 0) > EARLY_EXIT_MIN * 60
              and peak_pnl < EARLY_EXIT_MIN_RISE):
            reason = f"⏱ لم تصعد {EARLY_EXIT_MIN_RISE:.0f}% في {EARLY_EXIT_MIN}د"
        elif time.time() - (r.get("ts") or 0) > MAX_HOLD_MIN * 60:
            reason = f"⏰ نافذة التعرّض {MAX_HOLD_MIN}د"
    if reason:
        try:
            from radars.memecoin.live_stream import unwatch_token
            await unwatch_token(r["address"])
        except Exception:
            pass
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
        await asyncio.sleep(3)   # 📊 كانت 10ث — الأرضية -18% كانت تُخترق لـ-23% بين النبضات


async def meme_loop():
    _init_meme_db()
    asyncio.create_task(meme_tracker_loop())
    asyncio.create_task(early_watch_loop())
    from radars.memecoin.watchlist import watch_loop
    asyncio.create_task(watch_loop())
    log.info("\U0001F438 Meme radar loop started")
    while True:
        try:
            survivors = await scan()
            for p in survivors:
                sc = _score(p)
                # 🕐 الساعات الميتة: 0-6 UTC خسرت -448.1% على 64 صفقة
                if datetime.utcnow().hour in DEAD_HOURS_UTC:
                    continue
                # 🔥 لا دخول إلا بسيولة محروقة — الشرط الإلزامي ضدّ rug pull
                if p.get("chainId") == "solana":
                    try:
                        import httpx as _hx
                        async with _hx.AsyncClient() as _bc:
                            _bok, _bwhy = await _gate0_lp_burned(_bc, p)
                        if not _bok:
                            log.info("🔥🚫 %s: %s",
                                     (p.get("baseToken") or {}).get("symbol", "?"), _bwhy)
                            continue
                    except Exception as _be:
                        log.debug("lp burn check: %s", _be)
                        continue
                _need = EVM_SIGNAL_THRESHOLD if p.get("chainId") in ("bsc", "ethereum") else SIGNAL_THRESHOLD
                # 💎 المسار الثاني: لم تبلغ عتبة الصواريخ؟ نفحصها كناضجة
                if sc < _need:
                    try:
                        _h = 0
                        _rc = await _rugcheck_report(c, addr)
                        if _rc:
                            _h = int(_rc.get("totalHolders") or 0)
                        _mok, _mwhy = _mature_qualifies(p, _h)
                        if _mok:
                            _msc = _score_mature(p, _h)
                            if _msc >= MATURE_SCORE_MIN:
                                log.info("💎 ناضجة: %s نقاط %d (عمق $%.0f · %d حامل) — %s",
                                         (p.get("baseToken") or {}).get("symbol", "?"), _msc,
                                         (p.get("liquidity") or {}).get("usd", 0) or 0, _h, _mwhy)
                                sc = _msc
                                _need = MATURE_SCORE_MIN
                    except Exception as _me:
                        log.debug("mature path: %s", _me)
                if sc < _need:
                    # 👁️ نظيفة (اجتازت كل بوابات الأمان) لكنها لم تنفجر بعد
                    #    → تُراقَب لا تُرفَض، وندخل عند علامات الانطلاق
                    try:
                        from radars.memecoin.watchlist import add_to_watch
                        _a = (p.get("baseToken") or {}).get("address") or ""
                        _s = (p.get("baseToken") or {}).get("symbol") or "?"
                        if _a and not _meme_seen(_a):
                            add_to_watch(_a, _s, p)
                    except Exception as _we:
                        log.debug("watch add: %s", _we)
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
        await asyncio.sleep(60)


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
