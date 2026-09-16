"""💧 ضغط الشراء — الشورت ينجح حين يضعف الشراء لا حين يقوى.

نسبة حجم الشراء الى الحجم الكليّ في آخر 6 شمعات (15د).

مقيس 15 سبتمبر على اربع عيّنات بعتبات مختلفة:
  شورت + شراء <45-48% : +0.94 · +0.65 · +0.65 · +0.83  ✅
  شورت + شراء >52-55% : -0.38 · -1.11 · -1.11 · -0.53  ❌
  والعيّنة الاخيرة 147 و167 صفقة.
  ورفض القمّة + شراء ضعيف = +1.00% (72 صفقة).

الاطفاء: touch /opt/whalex/db/buy_pressure.off
"""
import json
import logging
import os
import time
import urllib.request

log = logging.getLogger("buy_pressure")
OFF = "/opt/whalex/db/buy_pressure.off"
TTL = 240
MAX_FOR_SHORT = 0.52
_C = {}
_EX = {}


def _exchange_of(sym):
    try:
        import sqlite3 as _sq
        c = _sq.connect("/opt/whalex/multi_universe.db")
        r = c.execute("SELECT exchange, ccxt_symbol FROM universe "
                      "WHERE symbol=? LIMIT 1", (sym,)).fetchone()
        c.close()
        if r and r[0] and str(r[0]).lower() != "binance":
            return str(r[0]).lower(), r[1]
    except Exception:
        pass
    return "binance", None


def ratio(symbol):
    """نسبة الشراء 0..1 — او None اذا تعذّر."""
    now = time.time()
    c = _C.get(symbol)
    if c and now - c[0] < TTL:
        return c[1]
    ex, ck = _exchange_of(symbol)
    val = None
    if ex == "binance":
        for host in ("https://fapi.binance.com/fapi/v1/klines?symbol=%s",
                     "https://api.binance.com/api/v3/klines?symbol=%s"):
            try:
                u = (host % symbol) + "&interval=15m&limit=8"
                with urllib.request.urlopen(u, timeout=7) as r:
                    k = json.load(r)
                if k and len(k) >= 6:
                    v = sum(float(x[5]) for x in k[-6:])
                    b = sum(float(x[9]) for x in k[-6:])
                    if v > 0:
                        val = b / v
                    break
            except Exception:
                continue
    else:
        try:
            import ccxt
            e = _EX.get(ex)
            if e is None:
                e = getattr(ccxt, ex)({"enableRateLimit": True,
                                       "timeout": 15000})
                _EX[ex] = e
            o = e.fetch_ohlcv(ck or symbol, "15m", limit=8)
            if o and len(o) >= 6:
                cl = [x[4] for x in o[-6:]]
                op = [x[1] for x in o[-6:]]
                vo = [x[5] for x in o[-6:]]
                up = sum(vo[i] for i in range(6) if cl[i] >= op[i])
                tv = sum(vo)
                if tv > 0:
                    val = up / tv
        except Exception:
            val = None
    _C[symbol] = (now, val)
    return val


def allow(symbol, direction):
    """هل يُسمح؟ الشورت يحتاج ضغط شراء ضعيفاً."""
    if os.path.exists(OFF):
        return True, ""
    if str(direction or "").upper() != "SHORT":
        return True, ""
    try:
        r = ratio(symbol)
    except Exception:
        return True, ""
    if r is None:
        return True, ""
    if r > MAX_FOR_SHORT:
        return False, "ضغط الشراء %.0f%% مرتفع للشورت" % (r * 100)
    return True, ""
