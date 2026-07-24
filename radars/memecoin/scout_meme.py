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
MIN_LIQ = 20_000        # سيولة دنيا بالدولار
MIN_VOL_24 = 20_000     # حجم 24 ساعة دنيا
AGE_MIN_MIN = 60        # أصغر عمر بالدقائق — أول ساعة مجزرة
MAX_PUMP_H1 = 50.0      # فوقها = دخول متأخر بعد الانفجار
MAX_DUMP = -30.0        # تحتها = العملة تنهار أصلاً
MIN_TXNS_H1 = 30        # حياة الآن: معاملات آخر ساعة
MIN_BUY_RATIO_H1 = 0.55 # زخم شراء حقيقي مسيطر
MIN_AVG_TRADE = 30.0    # متوسط الصفقة بالدولار — أقل = سبام بوتات
WASH_SYMMETRY = 0.03    # تطابق شراء/بيع مريب = تدوير وهمي
MAX_VOL_LIQ_H1 = 20.0   # حجم الساعة مقابل السيولة — فوقه مستحيل طبيعياً
VOL_ACCEL = 2.0         # حجم الساعة ≥ ضعف المتوسط اليومي = تسارع
BASE_TOKENS = {"WBNB", "BNB", "WETH", "ETH", "USDT", "USDC", "BUSD", "DAI",
               "WSOL", "SOL", "CAKE", "FDUSD", "TUSD", "USDE", "STETH"}
MIN_TXNS_24 = 50        # معاملات 24 ساعة دنيا

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
        if len(_GP_CACHE) > 500:
            _GP_CACHE.clear()
        _GP_CACHE[addr.lower()] = d
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


async def _gate25_onchain(cc, addr):
    # البوابة 2.5: إثبات الشراء الحقيقي على البلوكشين لأعلى الحاملين
    j = await _rugcheck_report(cc, addr)
    if not j:
        return True, "تعذّر التقرير"
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
        if str(h.get("is_contract")) != "1" and not (h.get("tag") or ""):
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
    if j.get("insiderNetworks"):
        return False, "شبكة محافظ داخليين"
    _rest = sum((h.get("pct") or 0) for h in th[1:10])
    if _rest > 30:
        return False, f"تركيز موزّع: الحاملون 2-10 يملكون {_rest:.0f}%"
    if len(th) > 1 and (th[1].get("pct") or 0) > 15:
        return False, f"حامل فرد يملك {(th[1].get('pct') or 0):.0f}%"
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
            if not _gate0(best):
                return None
            ok, reason = await _gate1(c, chain, addr)
            if not ok:
                log.info("🐸🚫 %s (%s) بوابة1: %s", (best.get("baseToken") or {}).get("symbol", "?"), chain, reason)
                return None
            ok2, reason2 = (await _gate2_solana(c, addr)) if chain == "solana" else (await _gate2_evm(c, addr, chain))
            if not ok2:
                log.info("🐸🚫 %s (%s) بوابة2: %s", (best.get("baseToken") or {}).get("symbol", "?"), chain, reason2)
                return None
            if chain == "solana":
                ok25, reason25 = await _gate25_onchain(c, addr)
            elif chain == "bsc":
                ok25, reason25 = await _gate25_evm(c, addr, best.get("pairAddress"), best.get("pairCreatedAt"))
            else:
                ok25, reason25 = True, ""
            if not ok25:
                log.info("🐸🚫 %s (%s) بوابة2.5: %s", (best.get("baseToken") or {}).get("symbol", "?"), chain, reason25)
                return None
            return best

        res = await asyncio.gather(*[_check(ch, a) for ch, a in cands])
        return [r for r in res if r]


MEME_DB = os.path.join(os.path.dirname(__file__), "..", "..", "db", "memecoin.db")
MEME_CHANNEL = "-1003918596088"
SIGNAL_THRESHOLD = 85


def _init_meme_db():
    os.makedirs(os.path.dirname(MEME_DB), exist_ok=True)
    conn = sqlite3.connect(MEME_DB)
    conn.execute("CREATE TABLE IF NOT EXISTS meme_signals(id INTEGER PRIMARY KEY, symbol TEXT, address TEXT UNIQUE, chain TEXT, score INTEGER, liq REAL, vol REAL, url TEXT, ts INTEGER, active INTEGER DEFAULT 1)")
    for _col, _def in (("entry_price", "REAL"), ("status", "TEXT DEFAULT 'open'"), ("exit_price", "REAL"),
                       ("pnl_pct", "REAL"), ("peak_price", "REAL"), ("closed_ts", "INTEGER"), ("buys_ratio", "REAL"), ("last_price", "REAL")):
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
        from services.notifier import push_note
        await push_note("meme", "signal", f"🐸 إشارة ميم: {b.get('symbol','?')} ({p.get('chainId')}) — {sc}/100")
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
    peak = max(float(r.get("peak_price") or entry), px)
    if peak > float(r.get("peak_price") or 0):
        _meme_peak(r["id"], peak)
    peak_pnl = (peak - entry) / entry * 100
    reason = None
    if pnl >= 25:
        reason = "\U0001F3AF \u0627\u0644\u0647\u062f\u0641 +25%"
    elif pnl <= -12:
        reason = "\U0001F6D1 \u0627\u0644\u0648\u0642\u0641 -12%"
    elif peak_pnl >= 25 and pnl <= 15:
        reason = "\U0001F512 \u0642\u0641\u0644 \u0631\u0628\u062d +15%"
    elif peak_pnl >= 15 and pnl <= 8:
        reason = "\U0001F512 \u0642\u0641\u0644 \u0631\u0628\u062d +8%"
    elif peak_pnl >= 8 and pnl <= 3:
        reason = "\U0001F512 \u0642\u0641\u0644 \u0631\u0628\u062d +3%"
    elif time.time() - (r.get("ts") or 0) > 24 * 3600:
        reason = "\u23F1 \u0627\u0646\u062a\u0647\u0627\u0621 24\u0633"
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
        await asyncio.sleep(10)


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
