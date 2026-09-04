"""تأكيد شمعة الدقيقة — معمارية freqtrade.

الاشارة تصدر من دورة الخمس دقائق. وحين تكون العملة مستنفَدة
(تحرّكت اضعاف مداها اليومي) ننتظر اغلاق شمعة الدقيقة الجارية
ونسأل: هل اغلقت في اتجاهنا؟

  شورت → شمعة هابطة = تأكيد
  لونج → شمعة صاعدة = تأكيد

مقيس على 141 صفقة: الخبيثة تدخل عند استنفاد 300% والسليمة 130%.
والانتظار مرن: 60 - (الوقت mod 60) — يتزامن مع الشمعة لا مؤقّت.

الاطفاء: touch /opt/whalex/db/candle_confirm.off
"""
import logging
import os

log = logging.getLogger("candle_confirm")

CONFIRM_OFF = "/opt/whalex/db/candle_confirm.off"
EXHAUSTION_MIN = 200.0
MAX_WAIT = 65.0
_EXH_CACHE = {}


def _sym(s):
    x = str(s or "").upper().replace("/", "").replace("-", "")
    if x and not x.endswith("USDT"):
        x += "USDT"
    return x


def exhaustion_pct(symbol):
    import time as _t
    import urllib.request as _u
    import json as _j
    s = _sym(symbol)
    ent = _EXH_CACHE.get(s)
    if ent and (_t.time() - ent[0]) < 300:
        return ent[1]
    try:
        url = (f"https://fapi.binance.com/fapi/v1/klines?symbol={s}"
               f"&interval=1d&limit=9")
        with _u.urlopen(url, timeout=8) as r:
            d = _j.load(r)
        if len(d) < 8:
            return None
        prev = d[:-1][-7:]
        trs = []
        for i in range(1, len(prev)):
            h, l = float(prev[i][2]), float(prev[i][3])
            pc = float(prev[i - 1][4])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr = sum(trs) / len(trs) if trs else 0
        if atr <= 0:
            return None
        cur = d[-1]
        val = (float(cur[2]) - float(cur[3])) / atr * 100
        _EXH_CACHE[s] = (_t.time(), val)
        return val
    except Exception as e:
        log.debug("exhaustion %s: %s", symbol, e)
        return None


def last_closed_1m(symbol):
    import urllib.request as _u
    import json as _j
    try:
        url = (f"https://fapi.binance.com/fapi/v1/klines?symbol={_sym(symbol)}"
               f"&interval=1m&limit=2")
        with _u.urlopen(url, timeout=8) as r:
            d = _j.load(r)
        if len(d) < 2:
            return None
        k = d[-2]
        return {"o": float(k[1]), "c": float(k[4])}
    except Exception as e:
        log.debug("kline %s: %s", symbol, e)
        return None


def seconds_to_close(now_ts=None):
    import time as _t
    now = now_ts if now_ts is not None else _t.time()
    rem = 60 - (int(now) % 60)
    return 60.0 if rem == 0 else float(rem)


def needs_confirm(exh):
    if exh is None:
        return False
    try:
        return float(exh) >= EXHAUSTION_MIN
    except Exception:
        return False


def candle_confirms(direction, o, c):
    try:
        o, c = float(o), float(c)
        if o <= 0 or c <= 0:
            return None
        d = str(direction or "").upper()
        if d == "SHORT":
            return c < o
        if d == "LONG":
            return c > o
        return None
    except Exception:
        return None


async def should_enter_candle(symbol, direction):
    """البوابة. اي فشل يعني الدخول — الفشل يفتح لا يغلق."""
    import asyncio
    try:
        if os.path.exists(CONFIRM_OFF):
            return True, ""
        exh = await asyncio.to_thread(exhaustion_pct, symbol)
        if not needs_confirm(exh):
            return True, ""
        wait = min(seconds_to_close(), MAX_WAIT)
        log.info("🕯️ %s %s مستنفَدة %.0f%% — ننتظر %.0fث لاغلاق الشمعة",
                 symbol, direction, exh, wait)
        await asyncio.sleep(wait + 1.5)
        k = await asyncio.to_thread(last_closed_1m, symbol)
        if k is None:
            return True, "تعذّرت الشمعة — نمرّ"
        ok = candle_confirms(direction, k["o"], k["c"])
        if ok is None:
            return True, "شمعة غير صالحة — نمرّ"
        if ok:
            log.info("🕯️✅ %s تأكيد الشمعة", symbol)
            return True, f"تأكيد الشمعة (استنفاد {exh:.0f}%)"
        log.info("🕯️🚫 %s الشمعة عكسنا — الغاء", symbol)
        return False, f"الشمعة عكسنا (استنفاد {exh:.0f}%)"
    except Exception as e:
        log.debug("candle gate: %s", e)
        return True, ""
