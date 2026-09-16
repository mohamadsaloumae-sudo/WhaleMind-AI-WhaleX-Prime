"""👁️ عين لكل عملة — اتجاه العملة لا اتجاه السوق.

ثلاث طبقات، تُحدَّث كل 15 دقيقة:
  ① بيتا — علاقة العملة ببيتكوين (تتبعه · مستقلّة · عكسه)
  ② اتجاه بيتكوين — صاعد · هابط · عرضيّ
  ③ اتجاه العملة نفسها — من ميلها هي

القرار: عملة تتبع بيتكوين وبيتكوين هابط → اللونج ممنوع عليها.
        وعملة عكسية → القاعدة تنقلب.
        والمستقلّة → يحكمها ميلها هي وحدها.

مقيس 15 سبتمبر: LSKUSDT بيتا -7.91 (عكس بيتكوين تماماً)
بينما AINUSDT بيتا +4.43 — فقاعدة واحدة للاثنين خطأ.

الاطفاء: touch /opt/whalex/db/coin_eye.off
"""
import json
import logging
import math
import os
import time
import urllib.request

log = logging.getLogger("coin_eye")
OFF = "/opt/whalex/db/coin_eye.off"
TTL = 900
_EYE = {}
_BTC = {"at": 0.0, "rets": [], "trend": "flat"}


def _kl(sym, limit=96):
    try:
        u = ("https://fapi.binance.com/fapi/v1/klines?symbol=%s"
             "&interval=15m&limit=%d" % (sym, limit))
        with urllib.request.urlopen(u, timeout=8) as r:
            return json.load(r)
    except Exception:
        return []


def _rets(k):
    c = [float(x[4]) for x in k]
    return [(c[i] - c[i - 1]) / c[i - 1] for i in range(1, len(c))], c


def _slope(c):
    """ميل النصف الاخير مقابل الاول — نسبة مئوية."""
    if len(c) < 20:
        return 0.0
    h = len(c) // 2
    a = sum(c[:h]) / h
    b = sum(c[h:]) / (len(c) - h)
    return (b - a) / a * 100.0 if a > 0 else 0.0


def _btc():
    now = time.time()
    if now - _BTC["at"] < TTL and _BTC["rets"]:
        return _BTC
    k = _kl("BTCUSDT")
    if len(k) < 50:
        return _BTC
    r, c = _rets(k)
    s = _slope(c)
    _BTC.update({"at": now, "rets": r,
                 "trend": "up" if s > 0.6 else ("down" if s < -0.6 else "flat"),
                 "slope": round(s, 2)})
    return _BTC


def eye(symbol):
    """يُعيد حالة العملة: بيتا · اتجاهها · اتجاه بيتكوين."""
    now = time.time()
    e = _EYE.get(symbol)
    if e and now - e["at"] < TTL:
        return e
    b = _btc()
    k = _kl(symbol)
    if len(k) < 50 or not b["rets"]:
        out = {"at": now, "beta": None, "trend": None,
               "btc": b.get("trend", "flat"), "kind": "unknown"}
        _EYE[symbol] = out
        return out
    r, c = _rets(k)
    n = min(len(r), len(b["rets"]))
    a, bb = r[-n:], b["rets"][-n:]
    mb = sum(bb) / n
    ma = sum(a) / n
    cov = sum((a[i] - ma) * (bb[i] - mb) for i in range(n)) / n
    var = sum((x - mb) ** 2 for x in bb) / n
    beta = cov / var if var > 0 else 0.0
    s = _slope(c)
    kind = ("follows" if beta > 0.5
            else "inverse" if beta < -0.1 else "independent")
    out = {"at": now, "beta": round(beta, 2), "slope": round(s, 2),
           "trend": "up" if s > 0.6 else ("down" if s < -0.6 else "flat"),
           "btc": b.get("trend", "flat"), "kind": kind}
    _EYE[symbol] = out
    return out


def allow(symbol, direction):
    """هل يُسمح بهذا الاتجاه على هذه العملة الآن؟ (bool، سبب)."""
    if os.path.exists(OFF):
        return True, ""
    d = str(direction or "").upper()
    try:
        e = eye(symbol)
    except Exception:
        return True, ""
    if e.get("beta") is None:
        return True, ""
    k, ct, st = e["kind"], e["btc"], e["trend"]
    # العملة التابعة: يحكمها اتجاه بيتكوين
    if k == "follows":
        if ct == "down" and d == "LONG":
            return False, "تتبع بيتكوين وهو هابط — اللونج ممنوع"
        if ct == "up" and d == "SHORT":
            return False, "تتبع بيتكوين وهو صاعد — الشورت ممنوع"
        return True, ""
    # العكسية: القاعدة تنقلب
    if k == "inverse":
        if ct == "up" and d == "LONG":
            return False, "عكس بيتكوين وهو صاعد — اللونج ممنوع"
        if ct == "down" and d == "SHORT":
            return False, "عكس بيتكوين وهو هابط — الشورت ممنوع"
        return True, ""
    # المستقلّة: ميلها هي وحده
    if st == "down" and d == "LONG":
        return False, "مستقلّة وميلها هابط — اللونج ممنوع"
    if st == "up" and d == "SHORT":
        return False, "مستقلّة وميلها صاعد — الشورت ممنوع"
    return True, ""
