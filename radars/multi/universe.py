"""
🌐 كون العملات الحصرية — العملات غير الموجودة على باينانس

📊 مقيس على السيرفر (17 أغسطس 2026):
   مكسي 499 · جيت 426 · بينج إكس 374 · بيتجت 303 · باي بيت 249 · أوكي إكس 177
   المجموع مع التكرار 2,028 · الفريد 1,268

الفلسفة: جدول واحد يُحدَّث كل ساعة، والماسح يقرأ منه.
   كل عملة تحمل اسم منصّتها — فالإشارة تعرف من أين جاءت.

ما يُستبعد: الأسهم المرمّزة (*STOCK) · المؤشّرات (HK50 · SPX) ·
   الفوركس (TRY · AUD) · المعادن (XAU) — رادارنا مبنيّ لسلوك الكريبتو.
"""
import logging
import re
import sqlite3
import time

log = logging.getLogger("multi_universe")

DB = "/opt/whalex/multi_universe.db"
MIN_VOL_24H = 3_000_000        # حجم يستحقّ التداول
REFRESH_SEC = 3600             # تحديث كل ساعة

# 🟡 باينانس أوّلاً — عملاتها تُرصَد منها هي، والباقي حصريّ.
#    سبب فشلها سابقاً: المحوّل كان يُمرّر apiKey فارغاً فترفضه.
EXCHANGES = ("binance", "mexc", "gate", "bingx", "bitget", "bybit", "okx")

# 🚫 ليست كريبتو — رادارنا يقرأ التصفيات والتدفّق، لا الأسهم
# 📌 ما يُستبعد: الفوركس فقط (TRY · AUD · EUR...) — سعره لا يتحرّك كالكريبتو.
#    أمّا الأسهم والذهب والفضّة والنفط فهي عقود دائمة بهامش USDT على منصّة كريبتو:
#    لها تمويل وتصفيات ورافعة وعمق 24/7 — أي ميكانيكا الكريبتو نفسها، فرادارنا يقرأها.
NOT_CRYPTO = re.compile(
    r"(^TRY$|^AUD$|^EUR$|^GBP$|^JPY$|^CHF$|^CAD$|^CNY$|^INR$|^BRL$"
    r"|^NCFX|^NCSI|^NCCO|^NCSK)", re.I)

# 📌 الأسهم المرمّزة تبقى مقبولة: هي عقود دائمة بهامش USDT على منصّة كريبتو
#    — لها تمويل وتصفيات ورافعة وعمق 24/7، أي ميكانيكا الكريبتو نفسها.
#    (القائمة أدناه محفوظة للرجوع، وغير مستخدمة في الفلترة.)
STOCK_TICKERS = {
    "SNDK", "SOXL", "SKHYNIX", "SKHY", "MU", "SPCX", "TESLA", "TSLA",
    "NVIDIA", "NVDA", "SNXX", "CL", "BZ", "DRAM", "CXMT", "QQQX",
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "AMD", "INTC", "COIN",
    "MSTR", "PLTR", "RIVN", "LCID", "NIO", "BABA", "AVGO", "ASML",
    "AXP", "RBLX", "LGELECTRONICS", "ZHONGJI", "FILECOIN", "SOXX",
    "SPY", "IWM", "TQQQ", "SQQQ", "ARKK", "SMH", "XLE", "XLF",
}


def _init():
    cn = sqlite3.connect(DB)
    cn.execute("""CREATE TABLE IF NOT EXISTS universe(
        symbol TEXT PRIMARY KEY,
        exchange TEXT,
        ccxt_symbol TEXT,
        volume_24h REAL,
        supports_oi INTEGER DEFAULT 1,
        updated_at INTEGER
    )""")
    cn.commit()
    cn.close()


def binance_symbols() -> set:
    """عملات باينانس الدائمة — لنعرف ما هو حصريّ."""
    import httpx
    try:
        r = httpx.get("https://fapi.binance.com/fapi/v1/exchangeInfo", timeout=25).json()
        return {s["symbol"] for s in r.get("symbols", [])
                if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT"
                and s.get("contractType") == "PERPETUAL"}
    except Exception as e:
        log.warning("🌐 باينانس exchangeInfo: %s", e)
        return set()


def refresh() -> dict:
    """يبني الكون من المنصّات الست — يُختار الأعلى حجماً عند التكرار."""
    import ccxt
    _init()
    bn = binance_symbols()
    if not bn:
        return {"error": "تعذّر جلب كون باينانس"}
    best: dict = {}          # symbol -> (exchange, ccxt_symbol, vol, oi)
    stats = {}
    for ex in EXCHANGES:
        try:
            e = getattr(ccxt, ex)({"enableRateLimit": True, "timeout": 25000,
                                   "options": {"defaultType": "swap"}})
            m = e.load_markets()
            tk = e.fetch_tickers()
            has_oi = bool(e.has.get("fetchOpenInterest"))
            n = 0
            for k, v in m.items():
                if not (v.get("swap") and v.get("linear") and v.get("active")):
                    continue
                if v.get("quote") != "USDT":
                    continue
                base = (v.get("base") or "").upper()
                # 🔁 توحيد التسميات: مكسي تلحق STOCK بالأصل نفسه (SNDK / SNDKSTOCK)
                #    فنجرّدها لنمنع فحص الأصل الواحد مرّتين وإصدار إشارتين له.
                _norm = base[:-5] if base.endswith("STOCK") and len(base) > 5 else base
                sym = f"{_norm}USDT"
                if (ex != "binance" and sym in bn) or NOT_CRYPTO.search(base):
                    continue
                # 💱 أوكي إكس لا تُرجع quoteVolume — نحسبه من baseVolume × السعر.
                #    كان الحجم يُقرأ صفراً فتُقصّ كل عملاتها (179 حصرية!).
                _t = tk.get(k) or {}
                vol = float(_t.get("quoteVolume") or 0)
                if vol <= 0:
                    _bv = float(_t.get("baseVolume") or 0)
                    _px = float(_t.get("last") or _t.get("close") or 0)
                    vol = _bv * _px
                if vol < MIN_VOL_24H:
                    continue
                # عند وجودها على عدّة منصّات نأخذ الأعمق سيولةً
                _cur = best.get(sym)
                if _cur is None or (ex == "binance" and _cur[0] != "binance") \
                        or (_cur[0] != "binance" and vol > _cur[2]):
                    best[sym] = (ex, k, vol, 1 if has_oi else 0)
                n += 1
            stats[ex] = n
            log.info("🌐 %s: %d عملة حصرية بحجم %sM+", ex, n, MIN_VOL_24H // 1_000_000)
        except Exception as ee:
            stats[ex] = f"خطأ: {str(ee)[:40]}"
            log.warning("🌐 %s: %s", ex, ee)

    cn = sqlite3.connect(DB)
    now = int(time.time())
    for sym, (ex, ck, vol, oi) in best.items():
        cn.execute("INSERT OR REPLACE INTO universe"
                   "(symbol,exchange,ccxt_symbol,volume_24h,supports_oi,updated_at)"
                   " VALUES(?,?,?,?,?,?)", (sym, ex, ck, vol, oi, now))
    # نحذف ما لم يُحدَّث — إلا ما له صفقة مفتوحة (NESAUSDT خرجت فضاع سعرها)
    _open = set()
    try:
        import json as _js
        _pc = sqlite3.connect("/opt/whalex/positions.db")
        for (_d,) in _pc.execute("SELECT data FROM active_positions WHERE status!='closed'"):
            try:
                _open.add(_js.loads(_d).get("symbol"))
            except Exception:
                pass
        _pc.close()
    except Exception:
        pass
    if _open:
        _ph = ",".join("?" * len(_open))
        cn.execute(f"DELETE FROM universe WHERE updated_at < ? AND symbol NOT IN ({_ph})",
                   [now - 3 * REFRESH_SEC, *_open])
    else:
        cn.execute("DELETE FROM universe WHERE updated_at < ?", (now - 3 * REFRESH_SEC,))
    cn.commit()
    total = cn.execute("SELECT COUNT(*) FROM universe").fetchone()[0]
    cn.close()
    log.info("🌐 الكون الحصري: %d عملة | التفصيل: %s", total, stats)
    return {"total": total, "per_exchange": stats}


def load(limit: int = 0) -> list:
    """يُرجع الكون مرتّباً بالحجم — للماسح."""
    _init()
    cn = sqlite3.connect(DB)
    cn.row_factory = sqlite3.Row
    q = "SELECT * FROM universe ORDER BY volume_24h DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = [dict(r) for r in cn.execute(q)]
    cn.close()
    return rows
