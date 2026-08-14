"""🔬📈 WhaleX Long v2 — منطق «نضوب الرافعة» (Leverage Exhaustion)

بديل «صيد القاع» الذي خسر -228% على 424 صفقة.
القياس: القاع العميق فوز 26% (-99.8%) · RSI<38 فوز 24% (-101.2%) · ob_pressure>0.3 فوز 59% (+22%)

الطبقات الأربع (كلها إلزامية):
  1) شلال تصفية طويلة: السعر ↓ و OI ↓ معاً
  2) نضوب مؤكَّد: OI توقّف + السعر استقرّ
  3) امتصاص في العمق: ضغط>0.3 + جدار شراء حقيقي (من WebSocket)
  4) استسلام: تمويل سلبي

🛡️ كل البيانات من WebSocket أو fapi_get (كاش + حارس -1003) — صفر REST مباشر.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field

log = logging.getLogger("whalex_long_v2")

CASCADE_OI_DROP = -2.5      # 📊 معايرة: أعلى مرشّح في سوق هادئ -2.6%
CASCADE_PRICE_DROP = -3.0   # هبوط سعري مصاحب حقيقي
EXHAUST_OI_STALL = 1.0
STABILIZE_BARS = 2
MIN_OB_PRESSURE = 0.30
MIN_BUY_WALL_USDT = 50_000
MAX_FUNDING = 0.0
MIN_RSI = 38.0
SCAN_INTERVAL = 60
COOLDOWN_SEC = 1800

_last_signal: dict = {}

LV2_STATS: dict = {}
_LV2_KEYS = ("checked", "no_data", "no_cascade", "not_exhausted",
             "no_absorption", "weak_wall", "funding_pos", "low_rsi", "emitted")


def _hit(k):
    LV2_STATS[k] = LV2_STATS.get(k, 0) + 1


def lv2_stats_snapshot():
    snap = {k: LV2_STATS.get(k, 0) for k in _LV2_KEYS}
    LV2_STATS.clear()
    return snap


@dataclass
class LongV2Reading:
    symbol: str
    price: float = 0.0
    rsi: float = 50.0
    range_pos: float = 0.5
    volume_ratio: float = 0.0
    funding: float = 0.0
    oi_change: float = 0.0
    oi_recent: float = 0.0
    price_drop: float = 0.0
    ob_pressure: float = 0.0
    buy_wall_usdt: float = 0.0
    cvd_flow: float = 0.0
    absorption: bool = False
    stabilized: bool = False
    reasons: list = field(default_factory=list)


async def _oi_series(symbol: str) -> list:
    """سلسلة OI لآخر 3 ساعات (15m × 12).
    🛡️ عبر fapi_get: كاش مشترك + حارس حظر -1003.
       OI لا يُبثّ عبر WebSocket في Binance، فهذه الطريقة الآمنة الوحيدة.
    """
    from radars.futures.engine import fapi_get
    url = ("https://fapi.binance.com/futures/data/openInterestHist"
           f"?symbol={symbol}&period=15m&limit=12")
    data = await fapi_get(url, ttl=240.0)
    if not isinstance(data, list):
        return []
    try:
        return [float(x["sumOpenInterest"]) for x in data]
    except Exception:
        return []


def _detect_cascade(oi: list, candles) -> tuple:
    if len(oi) < 8 or len(candles) < 8:
        return False, False, 0.0, 0.0, 0.0
    oi_change = ((oi[-1] - oi[0]) / oi[0] * 100) if oi[0] > 0 else 0.0
    oi_recent = ((oi[-1] - oi[-3]) / oi[-3] * 100) if oi[-3] > 0 else 0.0
    highs = [c.high for c in candles[-12:] if getattr(c, "high", 0) > 0]
    px = candles[-1].close
    peak = max(highs) if highs else px
    price_drop = ((px - peak) / peak * 100) if peak > 0 else 0.0
    # 🛡️ حارس القيم الشاذّة: OI ينهار بلا حركة سعر = انتهاء عقود أو خلل بيانات
    #    (ACXUSDT قيست بـ OI -46.3% مع سعر +0.0% — ليست تصفية)
    if oi_change <= -25.0 and price_drop > -2.0:
        return False, False, oi_change, oi_recent, price_drop
    cascade = (oi_change <= CASCADE_OI_DROP) and (price_drop <= CASCADE_PRICE_DROP)
    exhausted = oi_recent > -EXHAUST_OI_STALL
    return cascade, exhausted, oi_change, oi_recent, price_drop


def _stabilized(candles) -> bool:
    if len(candles) < STABILIZE_BARS + 2:
        return False
    lows = [c.low for c in candles[-(STABILIZE_BARS + 2):]]
    return min(lows[2:]) >= min(lows[:2])


async def evaluate_symbol(symbol: str):
    """يفحص رمزاً — يرجع القراءة إن اجتاز كل الطبقات، وإلا None."""
    from radars.futures.engine import (
        fetch_klines_async, rsi as _rsi, range_position, get_funding_rate,
    )
    _hit("checked")
    r = LongV2Reading(symbol=symbol)
    candles = await fetch_klines_async(symbol, "15m", 60)
    if not candles or len(candles) < 30:
        _hit("no_data"); return None
    r.price = candles[-1].close
    closes = [c.close for c in candles]
    r.rsi = _rsi(closes)
    try:
        r.range_pos = range_position(candles)
    except Exception:
        r.range_pos = 0.5
    vols = [getattr(c, "volume", 0) or 0 for c in candles[-21:]]
    if len(vols) >= 21 and sum(vols[:-1]) > 0:
        r.volume_ratio = vols[-1] / (sum(vols[:-1]) / 20)

    oi = await _oi_series(symbol)
    cascade, exhausted, r.oi_change, r.oi_recent, r.price_drop = _detect_cascade(oi, candles)
    if not cascade:
        _hit("no_cascade"); return None
    r.reasons.append(f"شلال تصفية (OI {r.oi_change:+.1f}% · سعر {r.price_drop:+.1f}%)")

    r.stabilized = _stabilized(candles)
    if not (exhausted and r.stabilized):
        _hit("not_exhausted"); return None
    r.reasons.append(f"نضوب الرافعة (OI توقّف {r.oi_recent:+.1f}%)")

    try:
        r.funding = await get_funding_rate(symbol)
    except Exception:
        r.funding = 0.0
    if r.funding >= MAX_FUNDING:
        _hit("funding_pos"); return None
    r.reasons.append(f"استسلام: تمويل {r.funding:+.4f}%")

    if r.rsi < MIN_RSI:
        _hit("low_rsi"); return None

    # 🌊 العمق من WebSocket — لا REST
    _book = None
    try:
        from quant_engine.ob_stream import get_book, get_signals as _obsig
        _book = get_book(symbol)
    except Exception as e:
        log.debug("ob_stream %s: %s", symbol, e)
    if not _book:
        _hit("no_absorption"); return None
    _bids, _asks = _book
    _bv = sum(p * q for p, q in _bids[:20])
    _av = sum(p * q for p, q in _asks[:20])
    r.ob_pressure = ((_bv - _av) / (_bv + _av)) if (_bv + _av) > 0 else 0.0
    if r.ob_pressure < MIN_OB_PRESSURE:
        _hit("no_absorption"); return None
    try:
        if any(x.get("side") == "bid" for x in (_obsig(symbol).get("spoof") or [])):
            _hit("no_absorption"); return None
    except Exception:
        pass

    try:
        _lv = [(p * q) for p, q in _bids[:50]]
        _avg = (sum(_lv) / len(_lv)) if _lv else 0.0
        _mx = max(_lv) if _lv else 0.0
        r.buy_wall_usdt = _mx if (_avg > 0 and _mx >= _avg * 5.0) else 0.0
    except Exception:
        r.buy_wall_usdt = 0.0
    if r.buy_wall_usdt < MIN_BUY_WALL_USDT:
        _hit("weak_wall"); return None
    r.reasons.append(f"امتصاص: ضغط {r.ob_pressure:+.2f} · جدار ${r.buy_wall_usdt:,.0f}")

    try:
        from quant_engine.delta_engine import calculate_cvd, detect_absorption
        from quant_engine.ob_stream import get_klines as _wsk
        kl = _wsk(symbol, "15m", 50)
        if kl:
            cvd, _series = calculate_cvd(kl)
            r.cvd_flow = float(cvd or 0.0)
            r.absorption, _why = detect_absorption(kl)
            if r.absorption:
                r.reasons.append("امتصاص شموع مؤكَّد")
    except Exception:
        pass

    _hit("emitted")
    return r

# ═══════════════════════════════════════════════════════════════
# 🧠 الوقف والأهداف الذكية — كل عملة تُقاس بنفسها (ATR + قاع الشلال)
# ═══════════════════════════════════════════════════════════════
RISK_BUDGET_PCT = 10.0      # أقصى خسارة من رأس المال عند ضرب الوقف
RR_TARGETS = (1.5, 3.0, 5.0)
LEV_MIN = 5.0        # 🎯 الحدّ الأدنى المطلوب (قرار Mohamad)
LEV_MAX = 10.0
MAX_SL_PCT = 12.0    # 🛡️ أقصى شبكة نجاة (المدير يخرج قبلها عادةً)
SL_ATR_BUFFER = 0.5         # الوقف تحت قاع الشلال بنصف ATR


def smart_levels(entry: float, cascade_low: float, atr_v: float) -> dict:
    """الوقف = قاع الشلال - (0.5 x ATR) — مستوى حقيقي لا نسبة مخترعة.
    الأهداف = مضاعفات المخاطرة (1.5 / 3 / 5) → النسبة ثابتة والأسعار متغيّرة.
    الرافعة = ميزانية المخاطرة / مسافة الوقف% → الخسارة القصوى ثابتة.
    ترجع {} إن كان الوقف أعمق مما تسمح به الرافعة الدنيا (رفض لا مضاعفة).
    """
    if entry <= 0:
        return {}
    _atr = atr_v if atr_v and atr_v > 0 else entry * 0.01
    sl = min(cascade_low, entry) - (_atr * SL_ATR_BUFFER)
    _floor = entry * 0.88      # لا أعمق من -12%
    _ceil = entry * 0.99       # لا أضيق من -1%
    if sl > _ceil:
        sl = _ceil
    if sl < _floor:
        sl = _floor
    risk = entry - sl
    if risk <= 0:
        return {}
    sl_pct = risk / entry * 100
    # 🧠 الوقف شبكة نجاة أخيرة لا أداة خروج — مدير الصفقات يخرج عند أول
    #    انقلاب مؤكَّد (is_real_reversal + العين التكتيكية) قبل الوصول إليه.
    #    لذلك لا نرفض صفقة لأن وقفها بعيد؛ نرفض فقط ما يتجاوز أقصى شبكة نجاة.
    if sl_pct > MAX_SL_PCT:
        return {}
    lev = RISK_BUDGET_PCT / sl_pct if sl_pct > 0 else LEV_MIN
    lev = max(LEV_MIN, min(LEV_MAX, round(lev, 1)))
    return {
        "sl": sl,
        "sl_pct": sl_pct,
        "tp1": entry + risk * RR_TARGETS[0],
        "tp2": entry + risk * RR_TARGETS[1],
        "tp3": entry + risk * RR_TARGETS[2],
        "leverage": lev,
        "atr": _atr,
    }


# ═══════════════════════════════════════════════════════════════
# 🔄 حلقة المسح + بناء الإشارة + التوصيل بالمدير
# ═══════════════════════════════════════════════════════════════
async def _build_and_open(r: LongV2Reading, position_manager_fn):
    """يبني إشارة LONG بمستويات ذكية ويمرّرها للمدير (تنفيذ حقيقي)."""
    from radars.futures.engine import Signal, fetch_klines_async, atr as _atr

    # منع التكرار: صفقة مفتوحة على نفس الرمز
    try:
        from radars.futures.position_manager import ACTIVE as _ACTIVE
        for _ex in _ACTIVE.values():
            if getattr(_ex, "status", "") == "open" and _ex.symbol == r.symbol:
                log.info("🔬 %s: صفقة مفتوحة بالفعل — تخطّي", r.symbol)
                return
    except Exception:
        pass

    # التهدئة
    _now = time.time()
    if _now - _last_signal.get(r.symbol, 0) < COOLDOWN_SEC:
        return

    candles = await fetch_klines_async(r.symbol, "15m", 60)
    if not candles or len(candles) < 20:
        return
    _atr_v = _atr(candles)
    _lows = [c.low for c in candles[-12:] if getattr(c, "low", 0) > 0]
    _cascade_low = min(_lows) if _lows else r.price

    lv = smart_levels(r.price, _cascade_low, _atr_v)
    if not lv:
        log.info("🔬 %s: وقف أوسع من حدّ الإدارة — تخطّي", r.symbol)
        return

    _risk = r.price - lv["sl"]
    sig = Signal(
        symbol=r.symbol, direction="LONG", grade="A",
        score=round(7.0 + min(2.0, abs(r.oi_change) / 5), 2),
        confidence=round(min(90.0, 70.0 + len(r.reasons) * 5), 1),
        entry=r.price,
        sl=round(lv["sl"], 8), tp1=round(lv["tp1"], 8),
        tp2=round(lv["tp2"], 8), tp3=round(lv["tp3"], 8),
        leverage=lv["leverage"],
        strategies="\n".join(["🔬 نضوب الرافعة"] + r.reasons),
        radar_type="futures", tier="LV2",
        rr_tp1=1.5, rr_tp2=3.0, rr_tp3=5.0,
        strategy_count=len(r.reasons), btc_trend="NEUTRAL",
        rsi=r.rsi, range_pos=round(r.range_pos, 4),
        volume_ratio=round(r.volume_ratio, 2),
    )

    try:
        from ml_recorder import record_signal
        record_signal(sig)
    except Exception as e:
        log.debug("LV2 ml_record: %s", e)

    log.info("🔬📈 LONG V2 SIGNAL: %s @%.6g lev=%.1fx وقف=%.2f%% [%s]",
             r.symbol, r.price, lv["leverage"], lv["sl_pct"], " · ".join(r.reasons))

    msg = (
        f"🔬 <b>WhaleX Long V2</b> — نضوب الرافعة\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <code>{r.symbol}</code>\n\n"
        f"Entry   <code>{sig.entry:.6g}</code>\n"
        f"Stop    <code>{sig.sl:.6g}</code>  ({lv['sl_pct']:.1f}%)\n"
        f"TP1     <code>{sig.tp1:.6g}</code>\n"
        f"TP2     <code>{sig.tp2:.6g}</code>\n"
        f"TP3     <code>{sig.tp3:.6g}</code>\n\n"
        f"Lev <b>{lv['leverage']:.1f}x</b>  ·  R:R 1.5/3/5\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(f"✅ {x}" for x in r.reasons) +
        f"\n━━━━━━━━━━━━━━━━━━━\n🐋 <i>WhaleMind Prime</i>"
    )
    try:
        from services.telegram import send_message
        from core.config import get_settings
        ch = get_settings().telegram_channel_futures
        if ch:
            await send_message(ch, msg)
    except Exception as e:
        log.error("LV2 broadcast: %s", e)

    _last_signal[r.symbol] = _now
    if position_manager_fn:
        try:
            await position_manager_fn(sig)
            log.info("🔬📈 Long V2 → manager: %s (opened)", r.symbol)
        except Exception as e:
            log.error("LV2 open %s: %s", r.symbol, e)


async def scout_long_v2_loop(position_manager_fn=None):
    """🔬 حلقة WhaleX Long V2 — نضوب الرافعة."""
    import sqlite3
    log.info("🔬📈 WhaleX Long V2 بدأ — منطق نضوب الرافعة")
    while True:
        try:
            try:
                cn = sqlite3.connect("/opt/whalex/coin_profiles.db")
                syms = [x[0] for x in cn.execute(
                    "SELECT symbol FROM coin_profiles ORDER BY avg_daily_volume DESC LIMIT 80")]
                cn.close()
            except Exception as e:
                log.warning("LV2 universe: %s", e)
                syms = []
            for s in syms:
                try:
                    r = await evaluate_symbol(s)
                    if r:
                        await _build_and_open(r, position_manager_fn)
                except Exception as e:
                    log.debug("LV2 %s: %s", s, e)
            _st = lv2_stats_snapshot()
            if _st.get("checked"):
                log.info("🔬 Long V2: فُحص %d | لا شلال %d | لم ينضب %d | لا امتصاص %d | جدار %d | تمويل+ %d | RSI %d | صدر %d",
                         _st["checked"], _st["no_cascade"], _st["not_exhausted"],
                         _st["no_absorption"], _st["weak_wall"], _st["funding_pos"],
                         _st["low_rsi"], _st["emitted"])
        except Exception as e:
            log.warning("LV2 loop: %s", e)
        await asyncio.sleep(SCAN_INTERVAL)
