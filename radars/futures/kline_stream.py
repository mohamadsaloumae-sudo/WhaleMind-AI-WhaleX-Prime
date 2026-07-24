"""🕯️ مخزن الشموع الحيّ — تعبئة واحدة عند الإقلاع، ثم WebSocket إلى الأبد.
بعد التسخين: صفر REST وصفر كاش قديم لكل طلبات الشموع."""
import asyncio
import json
import time
import logging

log = logging.getLogger("kline_stream")

WS_BASE = "wss://fstream.binance.com/stream?streams="
MAX_BARS = 200
_STORE: dict = {}      # (SYM, tf) -> list[list] بصيغة Binance
_TOUCH: dict = {}      # (SYM, tf) -> آخر تحديث من البثّ

_TF_SEC = {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
           "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "8h": 28800,
           "12h": 43200, "1d": 86400}
_WANTED: set = set()   # (SYM, tf) المطلوب بثّها
_READY: set = set()    # ما اكتملت تعبئته
_SEEDING: set = set()
_gen = 0


def want(symbol: str, interval: str):
    """تسجيل زوج/إطار للبثّ الحيّ."""
    global _gen
    k = (symbol.upper(), interval)
    if k not in _WANTED:
        _WANTED.add(k)
        _gen += 1
    return k


def get(symbol: str, interval: str, limit: int = 50):
    """شموع حيّة فقط — تُرفض إن تجمّد بثّها (تُخدم من REST بدلاً منها)."""
    k = (symbol.upper(), interval)
    rows = _STORE.get(k)
    if not rows or k not in _READY or len(rows) < min(limit, 30):
        return None
    # 🧊 حارس الطزاجة: شمعة جارية لم تُحدَّث = بيانات ميتة تفسد المؤشرات
    _max_age = max(90, _TF_SEC.get(interval, 900))
    _last = _TOUCH.get(k, 0)
    if (time.time() - _last) > _max_age:
        return None
    return rows[-limit:]


def age(symbol: str, interval: str):
    """عمر آخر تحديث بالثواني (للتشخيص)."""
    k = (symbol.upper(), interval)
    t = _TOUCH.get(k)
    return round(time.time() - t, 1) if t else None


def stats():
    return {"wanted": len(_WANTED), "ready": len(_READY), "bars": sum(len(v) for v in _STORE.values())}


async def _seed(sym, tf):
    """تعبئة تاريخية مرة واحدة فقط."""
    k = (sym, tf)
    if k in _READY or k in _SEEDING:
        return
    _SEEDING.add(k)
    try:
        from radars.futures.engine import fapi_get
        data = await fapi_get(f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval={tf}&limit={MAX_BARS}", 3600)
        if isinstance(data, list) and data:
            _STORE[k] = data[-MAX_BARS:]
            _READY.add(k)
    except Exception as e:
        log.debug("seed %s %s: %s", sym, tf, e)
    finally:
        _SEEDING.discard(k)


def _apply(sym, tf, kk):
    _TOUCH[(sym, tf)] = time.time()
    """تحديث الشمعة الجارية أو إضافة المكتملة."""
    k = (sym, tf)
    rows = _STORE.get(k)
    if rows is None:
        return
    row = [kk["t"], kk["o"], kk["h"], kk["l"], kk["c"], kk["v"], kk["T"],
           kk.get("q", "0"), kk.get("n", 0), kk.get("V", "0"), kk.get("Q", "0"), "0"]
    if rows and int(rows[-1][0]) == int(kk["t"]):
        rows[-1] = row
    else:
        rows.append(row)
        if len(rows) > MAX_BARS:
            del rows[0:len(rows) - MAX_BARS]


async def _run_batch(pairs):
    streams = "/".join(f"{s.lower()}@kline_{tf}" for s, tf in pairs)
    import websockets
    async with websockets.connect(WS_BASE + streams, ping_interval=20, close_timeout=5) as ws:
        log.info("🕯️🔌 Kline WS: %d تدفق", len(pairs))
        async for msg in ws:
            try:
                d = json.loads(msg).get("data") or {}
                kk = d.get("k") or {}
                if kk:
                    _apply(d.get("s", "").upper(), kk.get("i", ""), kk)
            except Exception:
                pass


async def kline_stream_loop():
    """يعبّئ الجديد ويبثّ الكل، ويعيد الاتصال عند تغيّر القائمة."""
    while True:
        try:
            pairs = sorted(_WANTED)
            if not pairs:
                await asyncio.sleep(5)
                continue
            for s, tf in pairs:
                if (s, tf) not in _READY:
                    await _seed(s, tf)
                    await asyncio.sleep(0.12)   # مباعدة التعبئة
            snapshot = _gen
            chunks = [pairs[i:i + 150] for i in range(0, len(pairs), 150)]
            tasks = [asyncio.create_task(_run_batch(ch)) for ch in chunks]
            while snapshot == _gen and any(not t.done() for t in tasks):
                await asyncio.sleep(3)
            for t in tasks:
                t.cancel()
        except Exception as e:
            log.warning("🕯️🔌 Kline WS drop: %s", e)
        await asyncio.sleep(3)
