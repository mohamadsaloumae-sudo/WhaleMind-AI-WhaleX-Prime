"""🔭 حلقة المستشعر — تمسح السوق كل دقيقة وتخزّن، بلا حكم.

المصدر: البث اللحظي (_TICK) الذي أُصلح 12 سبتمبر — 582 عملة بلا
اي طلب شبكة. نبني منه سلسلة اسعار في الذاكرة ثم نقيس عليها.

مقيس: 344 عملة في 10 ملي ثانية · 1.7 ميجابايت يوميا · 51 شهريا.

الاطفاء: touch /opt/whalex/db/sense.off
"""
import os
import time
import asyncio
import logging
import collections

log = logging.getLogger("sense_loop")
OFF = "/opt/whalex/db/sense.off"
EVERY = 60
KEEP = 90          # كم نقطة نحتفظ بها لكل عملة في الذاكرة
MIN_PTS = 45       # اقل عدد للقياس

# symbol -> deque[(price, vol24, ts)]
_SERIES = collections.defaultdict(lambda: collections.deque(maxlen=KEEP))


class _Bar:
    """شمعة مركّبة من البث — نبني OHLCV من نقاط الدقيقة."""
    __slots__ = ("open", "high", "low", "close", "volume")

    def __init__(self, o, h, l, c, v):
        self.open, self.high, self.low, self.close, self.volume = o, h, l, c, v


def _collect():
    """لقطة من البث اللحظي."""
    try:
        from radars.futures.price_stream import _TICK
    except Exception:
        return 0
    now = time.time()
    n = 0
    for sym, t in list(_TICK.items()):
        if not t or (now - t[3]) > 90:
            continue
        _SERIES[sym].append((float(t[0]), float(t[2] or 0), now))
        n += 1
    return n


def _bars(sym):
    """نحوّل السلسلة الى شموع تقريبية — الحجم من فرق حجم 24س."""
    pts = list(_SERIES[sym])
    if len(pts) < MIN_PTS:
        return None
    out = []
    for i in range(1, len(pts)):
        p0, v0, _ = pts[i - 1]
        p1, v1, _ = pts[i]
        dv = max(0.0, v1 - v0) or abs(p1 - p0) / max(p1, 1e-9) * 1e6
        out.append(_Bar(p0, max(p0, p1), min(p0, p1), p1, dv))
    return out


SNAP = "/opt/whalex/db/sense_series.json"


def _save_series():
    """نحفظ السلسلة على القرص — فإعادة التشغيل لا تمسح شيئاً."""
    import json as _j
    try:
        out = {s: list(d)[-KEEP:] for s, d in _SERIES.items() if len(d) >= 10}
        with open(SNAP + ".tmp", "w") as f:
            _j.dump(out, f)
        os.replace(SNAP + ".tmp", SNAP)
        return len(out)
    except Exception as e:
        log.debug("save series: %s", e)
        return 0


def _load_series():
    """نستعيدها عند الإقلاع — ونتجاهل ما تقادم فوق ساعتين."""
    import json as _j
    try:
        if not os.path.exists(SNAP):
            return 0
        now = time.time()
        d = _j.load(open(SNAP))
        n = 0
        for sym, pts in d.items():
            fresh = [tuple(p) for p in pts if len(p) == 3 and now - p[2] < 7200]
            if len(fresh) >= 10:
                _SERIES[sym].extend(fresh)
                n += 1
        return n
    except Exception as e:
        log.debug("load series: %s", e)
        return 0


async def _warmup():
    """يملأ السلسلة من شموع الدقيقة التاريخية لأنشط العملات."""
    import json as _j
    import urllib.request as _u
    try:
        from radars.futures.price_stream import _TICK
    except Exception:
        return
    syms = sorted(_TICK.items(), key=lambda x: -(x[1][2] or 0))[:200]
    n = 0
    for sym, _t in syms:
        try:
            url = ("https://fapi.binance.com/fapi/v1/klines?symbol=%s"
                   "&interval=1m&limit=%d" % (sym, KEEP))
            d = await asyncio.to_thread(
                lambda: _j.load(_u.urlopen(url, timeout=12)))
            for k in d:
                _SERIES[sym].append((float(k[4]), float(k[7] or 0), int(k[6]) / 1000))
            n += 1
        except Exception:
            continue
        await asyncio.sleep(0.06)
    log.info("🔥 المستشعر سُخّن من التاريخ — %d عملة جاهزة فوراً", n)


async def sense_loop():
    from sense.sensors import measure_all
    from sense.store import write_batch
    log.info("🔭 مستشعر السوق بدأ — يقيس ويخزّن، لا يقرّر")
    await asyncio.sleep(45)
    # 🔥 تسخين من الشموع التاريخية — بلا هذا كل إعادة تشغيل تمسح
    #    الذاكرة ويبدأ العدّ من الصفر (45 دقيقة ضائعة في كل مرّة).
    _rest = _load_series()
    if _rest >= 50:
        log.info("💾 المستشعر استعاد %d عملة من القرص — لا تسخين", _rest)
    else:
        try:
            await _warmup()
        except Exception as _we:
            log.warning("تسخين المستشعر: %s", str(_we)[:80])
    warm = 0
    while True:
        try:
            if os.path.exists(OFF):
                await asyncio.sleep(EVERY)
                continue
            got = _collect()
            warm += 1
            rows = []
            for sym in list(_SERIES):
                bars = _bars(sym)
                if not bars:
                    continue
                m = measure_all(bars)
                if m:
                    v24 = _SERIES[sym][-1][1] if _SERIES[sym] else 0
                    rows.append((sym, "binance", m, v24))
            if rows:
                write_batch(rows)
                if warm % 5 == 0:
                    _save_series()
                if warm % 15 == 1:
                    log.info("🔭 المستشعر: %d عملة في البث · %d قيست وخُزّنت",
                             got, len(rows))
            elif warm % 15 == 1:
                log.info("🔭 المستشعر يتهيّأ — %d عملة، ننتظر %d نقطة",
                         got, MIN_PTS)
        except Exception as e:
            log.warning("sense_loop: %s", str(e)[:90])
        await asyncio.sleep(EVERY)
