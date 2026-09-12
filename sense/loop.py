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


async def sense_loop():
    from sense.sensors import measure_all
    from sense.store import write_batch
    log.info("🔭 مستشعر السوق بدأ — يقيس ويخزّن، لا يقرّر")
    await asyncio.sleep(45)
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
                if warm % 15 == 1:
                    log.info("🔭 المستشعر: %d عملة في البث · %d قيست وخُزّنت",
                             got, len(rows))
            elif warm % 15 == 1:
                log.info("🔭 المستشعر يتهيّأ — %d عملة، ننتظر %d نقطة",
                         got, MIN_PTS)
        except Exception as e:
            log.warning("sense_loop: %s", str(e)[:90])
        await asyncio.sleep(EVERY)
