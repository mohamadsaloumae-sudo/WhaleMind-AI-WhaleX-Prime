"""🧭 تحيّز العملات — كل عملة واتجاه على حدة.

عملة خسرت في اتجاه معيّن ثلاث مرات فاكثر يُمنع عليها ذلك
الاتجاه وحده، ويبقى الآخر مسموحاً.

مقيس 13 سبتمبر: تدريب 10 ايام (728 صفقة) واختبار 4 ايام
لم يرها (159 صفقة): -108 صارت -56 بحظر 48 تركيبة.
الاطفاء: touch /opt/whalex/db/coin_bias.off
"""
import os
import sqlite3
import time

ML = "/opt/whalex/ml_training.db"
OFF = "/opt/whalex/db/coin_bias.off"
MIN_N = 3
WINDOW_DAYS = 14
TTL = 1800

_CACHE = {"at": 0.0, "ban": set()}


def build(db=ML, min_n=MIN_N, days=WINDOW_DAYS, now=None):
    """يبني مجموعة (رمز، اتجاه) الممنوعة."""
    t = int(now or time.time())
    agg = {}
    try:
        c = sqlite3.connect(db)
        rows = c.execute(
            "SELECT symbol, direction, pnl_pct FROM training_signals "
            "WHERE close_reason IN ('tactical_exit','sl_hit') "
            "AND pnl_pct IS NOT NULL AND timestamp > ?",
            (t - days * 86400,)).fetchall()
        c.close()
    except Exception:
        return set()
    for sym, d, p in rows:
        if not sym or not d:
            continue
        k = (sym, str(d).upper())
        a = agg.setdefault(k, [0, 0.0])
        a[0] += 1
        a[1] += float(p or 0)
    return {k for k, v in agg.items() if v[0] >= min_n and v[1] < 0}


def refresh(db=ML, now=None):
    _CACHE["ban"] = build(db, now=now)
    _CACHE["at"] = float(now or time.time())
    return len(_CACHE["ban"])


def allowed(symbol, direction, db=ML, now=None, off_path=OFF):
    """هل يُسمح بهذا الاتجاه على هذه العملة؟ يُعيد (bool، السبب)."""
    if os.path.exists(off_path):
        return True, ""
    t = float(now or time.time())
    if t - _CACHE["at"] > TTL:
        refresh(db, now=t)
    if (symbol, str(direction).upper()) in _CACHE["ban"]:
        return False, "تحيّز العملة يمنع %s" % str(direction).upper()
    return True, ""


def snapshot():
    """للفحص: كم تركيبة محظورة وما هي."""
    if not _CACHE["ban"]:
        refresh()
    return sorted(_CACHE["ban"])
