"""👁️ عين الانعكاس — الذروة في نطاق صاعد، والقاع في نطاق هابط.

الشورت: العملة كانت في نطاق صاعد · بلغت اعلى النطاق · وتوقّف صعودها
اللونج : العملة كانت في نطاق هابط · بلغت ادنى النطاق · وتوقّف هبوطها

مقيس 15 سبتمبر على 1150 صفقة (30 يوماً):
  انعكاس   100 صفقة · +1.72%
  غير ذلك 1050 صفقة · -0.50%
وثبت في ثلاث عيّنات: 15 صفقة +7.56% · 45 صفقة +1.69% · 100 صفقة +1.72%

الاطفاء: touch /opt/whalex/db/reversal_eye.off
"""
import json
import logging
import os
import time
import urllib.request

log = logging.getLogger("reversal_eye")
OFF = "/opt/whalex/db/reversal_eye.off"
TTL = 300
_C = {}


_EX = {}


def _exchange_of(sym):
    """منصّة العملة — MX يعمل على سبع منصّات لا باينانس وحدها."""
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


def _kl(sym, limit=96):
    """شموع 15د من منصّة العملة نفسها — لا باينانس دائماً."""
    ex, ck = _exchange_of(sym)
    if ex == "binance":
        for host in ("https://fapi.binance.com/fapi/v1/klines?symbol=%s",
                     "https://api.binance.com/api/v3/klines?symbol=%s"):
            try:
                u = (host % sym) + "&interval=15m&limit=%d" % limit
                with urllib.request.urlopen(u, timeout=8) as r:
                    d = json.load(r)
                if d and len(d) >= 60:
                    return d
            except Exception:
                continue
        return []
    try:
        import ccxt
        e = _EX.get(ex)
        if e is None:
            e = getattr(ccxt, ex)({"enableRateLimit": True, "timeout": 15000})
            _EX[ex] = e
        o = e.fetch_ohlcv(ck or sym, "15m", limit=limit)
        return [[x[0], x[1], x[2], x[3], x[4], x[5]] for x in (o or [])]
    except Exception:
        return []


def state(symbol):
    """نطاق العملة السابق · موقعها فيه · واتجاهها الآن."""
    now = time.time()
    s = _C.get(symbol)
    if s and now - s["at"] < TTL:
        return s
    k = _kl(symbol)
    if len(k) < 60:
        out = {"at": now, "ok": False}
        _C[symbol] = out
        return out
    c = [float(x[4]) for x in k]
    h = [float(x[2]) for x in k]
    l = [float(x[3]) for x in k]
    old = c[:60]
    a = sum(old[:30]) / 30
    b = sum(old[30:]) / 30
    pv = (b - a) / a * 100 if a > 0 else 0
    prev = "up" if pv > 0.5 else ("down" if pv < -0.5 else "flat")
    new = c[-12:]
    x = sum(new[:6]) / 6
    y = sum(new[6:]) / 6
    nv = (y - x) / x * 100 if x > 0 else 0
    cur = "up" if nv > 0.3 else ("down" if nv < -0.3 else "flat")
    hi, lo = max(h[:60]), min(l[:60])
    pos = (c[-1] - lo) / (hi - lo) if hi > lo else 0.5
    out = {"at": now, "ok": True, "prev": prev, "cur": cur,
           "pos": round(pos, 3)}
    _C[symbol] = out
    return out


def is_reversal(symbol, direction):
    """هل هذه الاشارة انعكاس حقيقيّ؟ (bool، سبب)."""
    if os.path.exists(OFF):
        return True, ""
    d = str(direction or "").upper()
    try:
        s = state(symbol)
    except Exception:
        return True, ""
    if not s.get("ok"):
        return True, ""
    p, c, pos = s["prev"], s["cur"], s["pos"]
    if d == "SHORT":
        if p == "up" and pos >= 0.6 and c != "up":
            return True, ""
        return False, ("ليست انعكاس قمّة · نطاق %s · موقع %.0f%% · الآن %s"
                       % (p, pos * 100, c))
    if d == "LONG":
        if p == "down" and pos <= 0.4 and c != "down":
            return True, ""
        return False, ("ليست انعكاس قاع · نطاق %s · موقع %.0f%% · الآن %s"
                       % (p, pos * 100, c))
    return True, ""
