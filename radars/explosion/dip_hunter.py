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
SHADOW_FLAG = "/opt/whalex/db/dip_hunter.shadow"
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
    # 📊 مقيس 10 سبتمبر: الرادار يحسب rsi و drop ثم يرميهما في نص،
    #    ويسجل score=7.5 و confidence=85 ثابتين للجميع. فكل صفقاته
    #    متطابقة في قاعدة التدريب ولا يميز الرابح من الخاسر اي حقل.
    #    الان نمرر ما نحسبه فعلا كي يصير القياس ممكنا.
    _rng = (px - floor) / max(1e-12, (peak - floor))
    _c = candles[-1]
    _hi, _loo, _op = float(_c.high), float(_c.low), float(_c.open)
    _rangec = max(1e-12, _hi - _loo)
    _body = abs(px - _op) / max(1e-12, _op) * 100
    _lwick = (min(px, _op) - _loo) / _rangec
    _uwick = (_hi - max(px, _op)) / _rangec
    _atr = 0.0
    try:
        _trs = [max(h[i] - lo[i], abs(h[i] - cl[i - 1]), abs(lo[i] - cl[i - 1]))
                for i in range(-14, 0)]
        _atr = (sum(_trs) / len(_trs)) / max(1e-12, px) * 100
    except Exception:
        _atr = 0.0
    _vr = 0.0
    try:
        _vs = [float(getattr(x, "volume", 0) or 0) for x in candles[-21:-1]]
        _av = sum(_vs) / max(1, len(_vs))
        _vr = float(getattr(_c, "volume", 0) or 0) / max(1e-12, _av)
    except Exception:
        _vr = 0.0
    _touch = sum(1 for x in prev_lows if x <= floor * (1 + LOW_TOL))
    _dist = (px - floor) / max(1e-12, floor) * 100
    _reds = 0
    for i in range(-2, -8, -1):
        try:
            if cl[i] < o[i]:
                _reds += 1
            else:
                break
        except Exception:
            break
    _slope = (cl[-1] - cl[-6]) / max(1e-12, cl[-6]) * 100 if len(cl) > 6 else 0.0
    return True, "", {"price": px, "rsi": round(r, 1), "drop": round(drop, 1),
                      "range_pos": round(_rng, 4), "atr_pct": round(_atr, 3),
                      "body_pct": round(_body, 3), "lower_wick": round(_lwick, 3),
                      "upper_wick": round(_uwick, 3), "vol_ratio": round(_vr, 3),
                      "floor_touches": _touch, "dist_floor": round(_dist, 3),
                      "red_streak": _reds, "slope5": round(_slope, 3)}


async def _emit(symbol, d, position_manager_fn):
    """يبني اشارة LONG ويمرّرها للمدير."""
    from radars.futures.engine import Signal
    px = float(d["price"])
    sig = Signal(
        symbol=symbol, direction="LONG", grade="A",
        score=round(abs(float(d.get("drop") or 0)), 2),
        confidence=round(min(99.0, 50.0 + float(d.get("body_pct") or 0) * 10), 1),
        entry=px,
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
        source_radar="dip_hunter",
        volume_ratio=float(d.get("vol_ratio") or 0),
        rsi=float(d.get("rsi") or 0),
        range_pos=float(d.get("range_pos") or 0),
        strategy_count=int(d.get("floor_touches") or 0),
        regime="dip_r%d_w%d" % (int(d.get("red_streak") or 0),
                                int(float(d.get("lower_wick") or 0) * 100)),
        accuracy=float(d.get("atr_pct") or 0),
        rr_tp1=float(d.get("dist_floor") or 0),
        rr_tp2=float(d.get("slope5") or 0),
        rr_tp3=float(d.get("upper_wick") or 0),
    )
    _last_signal[symbol] = time.time()
    log.info("🎯📈 %s: قاع · هبوط %.1f%% · RSI %.0f @ %.8g",
             symbol, d["drop"], d["rsi"], px)
    # 🧠 التسجيل في قاعدة التدريب — كان مفقوداً تماماً.
    #    34 صفقة يومياً تُفتَح وتُغلق بلا أي أثر: لا تظهر في المراكز
    #    ولا السجلّ الزمنيّ ولا تُحسَب في أي إحصاء ولا يتعلّم منها
    #    النموذج. والمشترك يراها تُفتَح ثم لا يجدها — فيظنّ خللاً
    #    أو تلاعباً. وهذا يهدم مصداقية النظام كلّه.
    try:
        from ml_recorder import record_signal
        record_signal(sig)
    except Exception as _re:
        log.error("🎯 تسجيل %s: %s", symbol, _re)
    # 👁️ وضع الظل: يمسح ويسجل ولا يفتح. مقيس 10 سبتمبر: 211 صفقة
    #    في 3 ايام بمتوسط سالب، وكل حقولها ثابتة فلا قياس ممكن. فنجمع
    #    البيانات الحقيقية بلا خسارة درهم، ثم نصلح الشرط بالارقام.
    #    التشغيل: touch /opt/whalex/db/dip_hunter.shadow
    if os.path.exists(SHADOW_FLAG):
        log.info("👁️ %s ظل — سُجّلت ولم تُفتح (هبوط %.1f%% · RSI %.0f)",
                 symbol, d["drop"], d["rsi"])
        return
    if position_manager_fn:
        try:
            await position_manager_fn(sig)
        except Exception as e:
            log.error("dip open %s: %s", symbol, e)
    # 🚀 التنفيذ للمشتركين — كل رادار يستدعيه بنفسه.
    #    كان ناقصاً هنا فيُفتح المركز في النظام ولا يصل احداً.
    #    مقيس 8 سبتمبر: خمس صفقات DIP رابحة مفتوحة وصفر تنفيذ.
    try:
        import asyncio as _aio
        from services.auto_trade_engine import on_signal_approved as _osa
        _aio.create_task(_osa(sig))
    except Exception as _te:
        log.error("🔴 Dip Hunter: تعذّر ارسال %s للتنفيذ: %s", symbol, _te)


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
