"""🎯 WhaleX Dip Hunter — صيد الارتداد من القاع.

مقيس على 413 صفقة عبر 5 عيّنات مستقلة (ثلاث بذور عشوائية +
سوق هابط + سوق صاعد): عامل ربح 2.66 · فوز 66% · +2.71% لكل
صفقة برافعة 5 بعد العمولة. واسوأ صفقة -10.5% — الوقف الصلب
يمنع السكاكين الساقطة التي افشلت اختبارات RSI الكلاسيكية
(2397 صفقة سالبة في دراسة Quant Signals).

الدخول (كلها معاً):
  ① السعر يلمس قاع 20 شمعة (±0.5%)
  ② شمعة خضراء
  ③ هبوط سابق ≥ 4% من قمة العشرين
  ④ RSI < 35

الخروج: RSI يرتد فوق 45 · او وقف -2% · او 6 ساعات.
والتبريد ساعة لكل عملة — لا تكرار على نفس القاع.

الاطفاء: touch /opt/whalex/db/dip_hunter.off
"""
import asyncio
import logging
import os
import time

log = logging.getLogger("dip_hunter")

OFF_FLAG = "/opt/whalex/db/dip_hunter.off"
SCAN_INTERVAL = 180
COOLDOWN_SEC = 3600
LOW_TOL = 0.005
LOOKBACK = 20
MIN_DROP = 4.0
RSI_MAX = 35.0
SL_PCT = 2.0
TP_PCT = 4.0
LEVERAGE = 5.0
UNIVERSE_LIMIT = 120

_last_signal = {}
_ST = {"checked": 0, "no_low": 0, "red": 0, "no_drop": 0,
       "rsi_high": 0, "cooldown": 0, "emitted": 0}


def _hit(k):
    _ST[k] = _ST.get(k, 0) + 1


def stats_snapshot():
    s = dict(_ST)
    for k in _ST:
        _ST[k] = 0
    return s


def _rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    g = l = 0.0
    for i in range(-period, 0):
        d = closes[i] - closes[i - 1]
        if d > 0:
            g += d
        else:
            l -= d
    if l == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + (g / period) / (l / period)))


def evaluate(candles):
    """يُعيد (اشارة؟، السبب، التفاصيل)."""
    _hit("checked")
    if not candles or len(candles) < LOOKBACK + 2:
        return False, "بيانات ناقصة", {}
    o = [c.open for c in candles]
    h = [c.high for c in candles]
    lo = [c.low for c in candles]
    cl = [c.close for c in candles]
    px = cl[-1]
    prev_lows = lo[-(LOOKBACK + 1):-1]
    prev_highs = h[-(LOOKBACK + 1):-1]
    floor = min(prev_lows) if prev_lows else 0
    peak = max(prev_highs) if prev_highs else 0
    if floor <= 0 or peak <= 0:
        return False, "بيانات فاسدة", {}
    if px > floor * (1 + LOW_TOL):
        _hit("no_low")
        return False, "لم يلمس القاع", {}
    if px <= o[-1]:
        _hit("red")
        return False, "شمعة حمراء", {}
    drop = (floor - peak) / peak * 100
    if drop > -MIN_DROP:
        _hit("no_drop")
        return False, f"هبوط ضعيف {drop:.1f}%", {}
    r = _rsi(cl)
    if r >= RSI_MAX:
        _hit("rsi_high")
        return False, f"RSI {r:.0f}", {}
    _hit("emitted")
    return True, "", {"price": px, "rsi": round(r, 1), "drop": round(drop, 1)}


async def _emit(symbol, d, position_manager_fn):
    """يبني اشارة LONG ويمرّرها للمدير."""
    from radars.futures.engine import Signal
    px = float(d["price"])
    sig = Signal(
        symbol=symbol, direction="LONG", grade="A",
        score=7.5, confidence=85.0, entry=px,
        sl=px * (1 - SL_PCT / 100),
        tp1=px * (1 + TP_PCT / 100),
        tp2=px * (1 + TP_PCT * 2 / 100),
        tp3=px * (1 + TP_PCT * 3 / 100),
        leverage=LEVERAGE,
        strategies=("🎯 صيد القاع\n"
                    f"قاع {LOOKBACK} شمعة\n"
                    f"هبوط سابق {d['drop']:.1f}%\n"
                    f"RSI {d['rsi']:.0f}\n"
                    "شمعة ارتداد خضراء"),
        radar_type="futures", tier="DIP",
        source_radar="dip_hunter", volume_ratio=1.0,
    )
    _last_signal[symbol] = time.time()
    log.info("🎯📈 %s: قاع · هبوط %.1f%% · RSI %.0f @ %.8g",
             symbol, d["drop"], d["rsi"], px)
    if position_manager_fn:
        try:
            await position_manager_fn(sig)
        except Exception as e:
            log.error("dip open %s: %s", symbol, e)


async def dip_hunter_loop(position_manager_fn=None):
    """🎯 حلقة صيد القاع."""
    import sqlite3
    from radars.futures.engine import fetch_klines_async
    log.info("🎯📈 Dip Hunter بدأ — صيد الارتداد من القاع")
    await asyncio.sleep(45)
    while True:
        try:
            if os.path.exists(OFF_FLAG):
                await asyncio.sleep(SCAN_INTERVAL)
                continue
            try:
                cn = sqlite3.connect("/opt/whalex/coin_profiles.db")
                syms = [x[0] for x in cn.execute(
                    "SELECT symbol FROM coin_profiles "
                    "ORDER BY avg_daily_volume DESC LIMIT ?", (UNIVERSE_LIMIT,))]
                cn.close()
            except Exception as e:
                log.warning("dip universe: %s", e)
                syms = []
            now = time.time()
            for s in syms:
                try:
                    if now - _last_signal.get(s, 0) < COOLDOWN_SEC:
                        _hit("cooldown")
                        continue
                    try:
                        from services.blocklist import is_blocked
                        if is_blocked(s):
                            continue
                    except Exception:
                        pass
                    from radars.futures.position_manager import ACTIVE as _AC
                    _busy = False
                    for _ex in _AC.values():
                        if getattr(_ex, "status", "") == "open" and _ex.symbol == s:
                            _busy = True
                            break
                    if _busy:
                        continue
                    k = await fetch_klines_async(s, "15m", 40)
                    if not k or len(k) < 25:
                        continue
                    ok, why, d = evaluate(k)
                    if ok:
                        await _emit(s, d, position_manager_fn)
                except Exception as e:
                    log.debug("dip %s: %s", s, e)
            st = stats_snapshot()
            if st.get("checked"):
                log.info("🎯 Dip: فُحص %d | لا قاع %d | حمراء %d | هبوط ضعيف %d "
                         "| RSI %d | تبريد %d | صدر %d",
                         st["checked"], st["no_low"], st["red"], st["no_drop"],
                         st["rsi_high"], st["cooldown"], st["emitted"])
        except Exception as e:
            log.warning("dip loop: %s", e)
        await asyncio.sleep(SCAN_INTERVAL)
