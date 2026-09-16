"""💧 حدّ السيولة — حجم تداول 24 ساعة.

مقيس 15 سبتمبر على 2268 صفقة (30 يوماً):
  بلا فلتر -399 نقطة · ≥50M +49 · ≥75M +133 · ≥100M +104
وثبت موجباً في خمس عتبات متتالية (50·75·100·150·200).

ومع الوقف المتحرّك 0.8/0.3 على شريحة ≥75M:
  +1104 نقطة على 378 صفقة = +2.92% لكل صفقة.

الاطفاء: touch /opt/whalex/db/liquidity_gate.off
"""
import json
import logging
import os
import time
import urllib.request

log = logging.getLogger("liquidity_gate")
OFF = "/opt/whalex/db/liquidity_gate.off"
MIN_M = 75.0
TTL = 900
_C = {"at": 0.0, "v": {}}


def _load():
    now = time.time()
    if now - _C["at"] < TTL and _C["v"]:
        return _C["v"]
    out = {}
    for h in ("https://fapi.binance.com/fapi/v1/ticker/24hr",
              "https://api.binance.com/api/v3/ticker/24hr"):
        try:
            with urllib.request.urlopen(h, timeout=15) as r:
                for x in json.load(r):
                    s = x.get("symbol")
                    q = float(x.get("quoteVolume") or 0) / 1e6
                    if s and q > out.get(s, 0):
                        out[s] = q
        except Exception:
            continue
    if out:
        _C.update({"at": now, "v": out})
        log.info("💧 السيولة: %d رمز · فوق %.0fM: %d",
                 len(out), MIN_M, len([1 for q in out.values() if q >= MIN_M]))
    return _C["v"]


def allow(symbol):
    """هل سيولة العملة كافية؟ (bool، سبب)."""
    if os.path.exists(OFF):
        return True, ""
    try:
        v = _load()
    except Exception:
        return True, ""
    q = v.get(str(symbol or "").upper())
    if q is None:
        return True, ""          # غير مدرجة على باينانس: لا نمنع
    if q < MIN_M:
        return False, "سيولة %.1fM دون %.0fM" % (q, MIN_M)
    return True, ""


def volume_of(symbol):
    """حجم تداول العملة بالملايين — او None اذا غير معروفة."""
    try:
        return _load().get(str(symbol or "").upper())
    except Exception:
        return None
