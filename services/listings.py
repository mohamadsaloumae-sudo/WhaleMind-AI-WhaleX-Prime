"""🗺️ جدول الإدراج الحقيقيّ — أي عملة مدرجة على أي منصّة.

المشكلة المقيسة: جدول universe يسجّل منصّة واحدة لكل عملة — من أين
رصدها الرادار، لا أين تُتداول فعلاً. فـCATIUSDT مسجّلة binance وقد
تكون مدرجة في بايبت أيضاً. التوجيه على هذا الجدول تخمين.

الحلّ: نسأل كل منصّة عن قائمة عقودها الآجلة الدائمة ونخزّنها.
بيانات من المصدر لا استنتاج.

ثلاثة ضمانات:
  1 الفشل يفتح لا يغلق — جدول فارغ أو قديم يعني السماح لا الحجب
  2 لا نحجب على منصّة لم نجلب قائمتها بنجاح قط
  3 القراءة من ذاكرة — بلا شبكة في مسار التنفيذ

التحديث: refresh_all() كل 6 ساعات · الاطفاء: touch listings.off
"""
import logging
import os
import sqlite3
import time

log = logging.getLogger("listings")

DB = "/opt/whalex/db/listings.db"
OFF_FLAG = "/opt/whalex/db/listings.off"
STALE_SEC = 86400 * 2          # قائمة أقدم من يومين لا يُحتجّ بها
REFRESH_SEC = 6 * 3600
EXCHANGES = ("binance", "bybit", "okx", "bitget", "mexc", "gate", "bingx")

_CACHE = {}                     # {exchange: {symbol, ...}}
_META = {}                      # {exchange: {"ts": float, "count": int}}


def _init():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS listings(
        exchange TEXT NOT NULL,
        symbol   TEXT NOT NULL,
        updated_at INTEGER,
        PRIMARY KEY (exchange, symbol))""")
    c.execute("""CREATE TABLE IF NOT EXISTS listings_meta(
        exchange TEXT PRIMARY KEY,
        count INTEGER,
        updated_at INTEGER,
        last_error TEXT)""")
    c.commit()
    c.close()


def _norm(sym: str) -> str:
    """CATI/USDT:USDT → CATIUSDT · يوحّد صيغة ccxt مع صيغتنا."""
    s = (sym or "").upper()
    if ":" in s:
        s = s.split(":")[0]
    s = s.replace("/", "").replace("-", "").replace("_", "").strip()
    for suf in ("SWAP", "PERP", "PERPETUAL"):
        if s.endswith(suf):
            s = s[:-len(suf)]
    return s


def fetch_exchange(ex_id: str) -> tuple:
    """يجلب رموز العقود الآجلة الدائمة من منصّة واحدة.
    Returns: (set الرموز, نصّ الخطأ أو "")"""
    try:
        import ccxt
        ex = getattr(ccxt, ex_id)({"enableRateLimit": True, "timeout": 20000})
        markets = ex.load_markets()
    except Exception as e:
        return set(), str(e)[:200]

    out = set()
    for m in markets.values():
        try:
            if not m.get("swap"):
                continue
            if m.get("settle") != "USDT":
                continue
            if m.get("active") is False:
                continue
            n = _norm(m.get("id") or m.get("symbol") or "")
            if n.endswith("USDT") and len(n) > 4:
                out.add(n)
        except Exception:
            continue
    return out, ""


def refresh_one(ex_id: str) -> dict:
    syms, err = fetch_exchange(ex_id)
    if err or not syms:
        log.warning("الإدراج %s: فشل الجلب — %s", ex_id, err or "قائمة فارغة")
        try:
            _init()
            c = sqlite3.connect(DB)
            c.execute("INSERT INTO listings_meta(exchange,count,updated_at,last_error) "
                      "VALUES(?,?,?,?) ON CONFLICT(exchange) DO UPDATE SET "
                      "last_error=excluded.last_error",
                      (ex_id, 0, 0, err or "empty"))
            c.commit()
            c.close()
        except Exception as e:
            log.debug("meta %s: %s", ex_id, e)
        return {"exchange": ex_id, "ok": False, "count": 0, "error": err}

    now = int(time.time())
    try:
        _init()
        c = sqlite3.connect(DB)
        c.execute("DELETE FROM listings WHERE exchange=?", (ex_id,))
        c.executemany("INSERT OR REPLACE INTO listings(exchange,symbol,updated_at) "
                      "VALUES(?,?,?)", [(ex_id, s, now) for s in syms])
        c.execute("INSERT INTO listings_meta(exchange,count,updated_at,last_error) "
                  "VALUES(?,?,?,'') ON CONFLICT(exchange) DO UPDATE SET "
                  "count=excluded.count, updated_at=excluded.updated_at, last_error=''",
                  (ex_id, len(syms), now))
        c.commit()
        c.close()
    except Exception as e:
        log.error("حفظ الإدراج %s: %s", ex_id, e)
        return {"exchange": ex_id, "ok": False, "count": 0, "error": str(e)}

    _CACHE[ex_id] = syms
    _META[ex_id] = {"ts": now, "count": len(syms)}
    log.info("الإدراج %s: %d عملة", ex_id, len(syms))
    return {"exchange": ex_id, "ok": True, "count": len(syms), "error": ""}


def refresh_all() -> dict:
    res = {}
    for ex in EXCHANGES:
        res[ex] = refresh_one(ex)
    ok = sum(1 for r in res.values() if r["ok"])
    total = sum(r["count"] for r in res.values())
    log.info("جدول الإدراج: %d منصّة · %d عملة", ok, total)
    return res


def _load():
    """يملأ الذاكرة من القاعدة — يُستدعى مرّة عند الإقلاع."""
    try:
        _init()
        c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        for ex, sym in c.execute("SELECT exchange, symbol FROM listings"):
            _CACHE.setdefault(ex, set()).add(sym)
        for ex, cnt, ts in c.execute(
                "SELECT exchange, count, updated_at FROM listings_meta"):
            _META[ex] = {"ts": ts or 0, "count": cnt or 0}
        c.close()
        log.info("الإدراج مُحمَّل: %s",
                 " · ".join(f"{k} {len(v)}" for k, v in _CACHE.items()))
    except Exception as e:
        log.debug("تحميل الإدراج: %s", e)


def is_listed(symbol: str, exchange: str) -> bool:
    """هل هذه العملة مدرجة على هذه المنصّة؟
    الفشل يفتح: قائمة مفقودة أو قديمة → True (نسمح ونترك المنصّة تحكم)."""
    try:
        if os.path.exists(OFF_FLAG):
            return True
        ex = (exchange or "").lower()
        meta = _META.get(ex)
        if not meta or not meta.get("count"):
            return True
        if (time.time() - (meta.get("ts") or 0)) > STALE_SEC:
            return True
        return _norm(symbol) in _CACHE.get(ex, set())
    except Exception as e:
        log.debug("is_listed: %s", e)
        return True


def snapshot() -> dict:
    return {
        "off": os.path.exists(OFF_FLAG),
        "exchanges": {k: {"count": v.get("count", 0),
                          "age_hours": round((time.time() - (v.get("ts") or 0)) / 3600, 1)}
                      for k, v in _META.items()},
    }


async def listings_loop():
    import asyncio
    log.info("جدول الإدراج بدأ — تحديث كل %d ساعة", REFRESH_SEC // 3600)
    _load()
    await asyncio.sleep(60)
    while True:
        try:
            if not os.path.exists(OFF_FLAG):
                await asyncio.to_thread(refresh_all)
        except Exception as e:
            log.error("حلقة الإدراج: %s", e)
        await asyncio.sleep(REFRESH_SEC)


