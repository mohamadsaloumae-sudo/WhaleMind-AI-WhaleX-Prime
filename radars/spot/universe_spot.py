"""🪙🌐 كون السبوت — سبع منصّات لا واحدة."""
import logging, re, sqlite3, time
log = logging.getLogger("spot_universe")
DB = "/opt/whalex/spot_universe.db"
MIN_VOL_24H = 2_000_000
REFRESH_SEC = 3600
MAX_PER_EX = 220
EXCHANGES = ("binance", "bybit", "okx", "bitget", "gate", "mexc", "bingx")
_STABLES = {"USDT","USDC","BUSD","TUSD","DAI","FDUSD","USDD","USDP",
            "PYUSD","EURI","AEUR","USDE","USD1","XUSD","RLUSD"}
_LEV_SUFFIX = ("UP","DOWN","BULL","BEAR","3L","3S","5L","5S")
NOT_CRYPTO = re.compile(r"(^TRY$|^AUD$|^EUR$|^GBP$|^JPY$|^CHF$|^CAD$|^CNY$|^INR$|^BRL$|^ARS$|^ZAR$|^NGN$|^RUB$)", re.I)

def _init():
    cn = sqlite3.connect(DB)
    cn.execute("""CREATE TABLE IF NOT EXISTS spot_universe(
        symbol TEXT PRIMARY KEY, exchange TEXT, ccxt_symbol TEXT,
        volume_24h REAL, updated_at INTEGER)""")
    cn.execute("CREATE INDEX IF NOT EXISTS idx_spot_ex ON spot_universe(exchange)")
    cn.commit(); cn.close()

# 🚫 الأسهم المرمّزة على السبوت: تتبع وول ستريت وتُغلق نهاية الأسبوع —
#    ورادارنا يقرأ سلوك الكريبتو (سيولة 24/7 · تدفّق تيكر · قيعان نطاق).
#    بيتجت وحدها أعطت 218 رمزاً كلّها بادئة R (RTSLA · RNVDA...).
_STOCK_PREFIX = re.compile(r"^(R|X|T)[A-Z]{2,6}$")
_STOCK_HINT = re.compile(r"(STOCK|EQUITY|SHARE|_PRE|PREIPO)", re.I)

def _skip(base: str) -> bool:
    b = (base or "").upper()
    if not b or b in _STABLES: return True
    if NOT_CRYPTO.search(b): return True
    if _STOCK_HINT.search(b): return True
    for sfx in _LEV_SUFFIX:
        if b.endswith(sfx) and len(b) > len(sfx): return True
    return False

def refresh() -> dict:
    import ccxt
    _init()
    best = {}; stats = {}; _listed = {}
    for ex in EXCHANGES:
        try:
            # 🏊 عميل مشترك — لا نُعيد تحميل الأسواق كل دورة
            from services.ccxt_pool import get as _pool, markets as _mk
            e = _pool(ex, "spot", 25000)
            m = _mk(ex, "spot"); tk = e.fetch_tickers()
            cand = []
            for k, v in m.items():
                if not (v.get("spot") and v.get("active")): continue
                if v.get("quote") != "USDT": continue
                base = (v.get("base") or "").upper()
                if _skip(base): continue
                _t = tk.get(k) or {}
                vol = float(_t.get("quoteVolume") or 0)
                if vol <= 0:
                    _bv = float(_t.get("baseVolume") or 0)
                    _px = float(_t.get("last") or _t.get("close") or 0)
                    vol = _bv * _px
                if vol < MIN_VOL_24H: continue
                cand.append((f"{base}USDT", k, vol))
                _listed.setdefault(f"{base}USDT", set()).add(ex)
            cand.sort(key=lambda x: -x[2]); cand = cand[:MAX_PER_EX]
            for sym, ck, vol in cand:
                if sym not in best or vol > best[sym][2]:
                    best[sym] = (ex, ck, vol)
            stats[ex] = len(cand)
            log.info("🪙🌐 %s: %d زوج سبوت", ex, len(cand))
        except Exception as ee:
            stats[ex] = f"خطأ: {str(ee)[:40]}"
            log.warning("🪙🌐 %s: %s", ex, ee)
    # 🚫 تنقية الأسهم المرمّزة — بيتجت تُدرج 218 سهماً ببادئة R بحجوم خيالية
    #    (RMRNA=موديرنا · RWMT=وولمارت · RGLD=ذهب · RIWM=راسل2000).
    #    العملة الحقيقية مُدرَجة على منصّتين فأكثر؛ فالمنفردة ببادئة R سهم.
    _drop = [_s for _s, (_e, _c, _v) in best.items()
             if _s[:-4].startswith("R") and len(_listed.get(_s, ())) < 2]
    # حجم أكبر من بيتكوين على منصّة واحدة = رقم مُضخَّم لا سيولة حقيقية
    _drop += [_s for _s, (_e, _c, _v) in best.items()
              if _v > 1_600_000_000 and _s not in ("BTCUSDT", "ETHUSDT")]
    for _s in _drop:
        best.pop(_s, None)
    if _drop:
        log.info("🪙🌐 استُبعد %d رمزاً (أسهم مرمّزة)", len(_drop))

    cn = sqlite3.connect(DB); now = int(time.time())
    for sym, (ex, ck, vol) in best.items():
        cn.execute("INSERT OR REPLACE INTO spot_universe"
                   "(symbol,exchange,ccxt_symbol,volume_24h,updated_at) VALUES(?,?,?,?,?)",
                   (sym, ex, ck, vol, now))
    for _s in set(_drop):
        cn.execute("DELETE FROM spot_universe WHERE symbol=?", (_s,))
    cn.execute("DELETE FROM spot_universe WHERE updated_at < ?", (now - 7200,))
    cn.commit(); cn.close()
    log.info("🪙🌐 كون السبوت: %d عملة | %s", len(best), stats)
    return {"total": len(best), "by_exchange": stats}

def load(limit: int = 0) -> list:
    _init()
    try:
        cn = sqlite3.connect(DB)
        q = "SELECT symbol,exchange,ccxt_symbol,volume_24h FROM spot_universe ORDER BY volume_24h DESC"
        if limit: q += f" LIMIT {int(limit)}"
        rows = cn.execute(q).fetchall(); cn.close(); return rows
    except Exception as e:
        log.warning("🪙🌐 load: %s", e); return []

def age_sec() -> float:
    try:
        cn = sqlite3.connect(DB)
        r = cn.execute("SELECT MAX(updated_at) FROM spot_universe").fetchone()[0]
        cn.close()
        return time.time() - float(r) if r else 1e9
    except Exception:
        return 1e9
