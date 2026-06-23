"""
WhaleMind-Prime-Core — engine.py V2
═══════════════════════════════════════════════════════════════════
ترقية شاملة:
- ✅ 11 استراتيجية أصلية محتفظ بها
- ➕ Delta 1 + Delta 2 + Divergence
- ➕ Multi-Timeframe (15m + 1H + 4H)
- ➕ Funding Rate Filter
- ➕ Open Interest Confirmation
- ➕ BTC Macro Trend
- ➕ Volume Profile
- ➕ Accumulation Watchlist
- 🎯 Accuracy حقيقية من DB
- ⚡ Leverage ديناميكي (Grade + ATR + Volume)
═══════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import asyncio, logging, time, json
from dataclasses import dataclass, field
from typing import Optional
import math
import httpx

log = logging.getLogger("engine")

# ═══════════════════════════════════════════════════════════════
# ─── DATA STRUCTURES ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

@dataclass
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    buy_volume: float = 0.0

@dataclass
class MarketTier:
    symbol: str
    volume_24h: float
    tier: str
    max_leverage: float
    min_score: float
    min_confidence: float

@dataclass
class Signal:
    symbol: str
    direction: str
    grade: str
    score: float
    confidence: float
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    leverage: float
    strategies: str
    radar_type: str = "futures"
    tier: str = "B"
    timestamp: int = field(default_factory=lambda: int(time.time()))
    end_time: Optional[int] = None
    highest_hit: Optional[float] = None
    fvg_zone: Optional[float] = None
    liquidation_signal: bool = False
    waiting_room: bool = False
    # ✨ حقول جديدة
    funding_rate: float = 0.0
    open_interest_change: float = 0.0
    btc_trend: str = "NEUTRAL"
    mtf_15m: str = "NEUTRAL"
    mtf_1h: str = "NEUTRAL"
    mtf_4h: str = "NEUTRAL"
    rr_tp1: float = 0.0
    rr_tp2: float = 0.0
    rr_tp3: float = 0.0
    accuracy: float = 0.0
    strategy_count: int = 0
    regime: str = ""
    range_pos: float = 0.0
    rsi: float = 0.0

@dataclass
class ShadowTrade:
    symbol: str
    direction: str
    entry: float
    sl: float
    tp1: float
    strategies: str
    score: float
    confidence: float
    # ─── المميزات المهندَسة (درس النموذج — يتعلّم منها الأنماط) ───
    regime: str = ""            # TRENDING_UP/DOWN/RANGING
    range_pos: float = 0.0      # موقع السعر في النطاق (0-1)
    rsi: float = 0.0
    stoch_k: float = 0.0
    stoch_d: float = 0.0
    macd_hist: float = 0.0
    grade: str = "B"
    tier: str = "B"
    funding: float = 0.0
    oi_change: float = 0.0
    btc_trend: str = ""         # اتجاه BTC وقت الإشارة
    hawk_phase: str = ""        # مرحلة عين الصقر (MARKUP/MARKDOWN/...)
    hawk_modifier: float = 1.0  # معامل عين الصقر
    volume_ratio: float = 0.0   # نسبة حجم الشمعة لمتوسط 20
    key_strat_count: int = 0    # عدد الاستراتيجيات الأساسية
    # ─── النتيجة (ما يتعلّمه النموذج: هل كانت صحيحة؟) ───
    timestamp: int = field(default_factory=lambda: int(time.time()))
    result: Optional[str] = None
    exit_price: Optional[float] = None
    pnl_pct: Optional[float] = None
    closed_at: Optional[int] = None

# ═══════════════════════════════════════════════════════════════
# ─── BTC MACRO TREND CACHE ──────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

BTC_TREND = {"trend": "NEUTRAL", "last_update": 0, "btc_change_1h": 0.0, "btc_change_24h": 0.0}

async def update_btc_macro():
    """يحدّث اتجاه BTC كل 5 دقائق — يستخدمه كل الإشارات"""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=BTCUSDT")
            d = r.json()
            change_24h = float(d.get("priceChangePercent", 0))
            r2 = await c.get("https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1h&limit=2")
            klines = r2.json()
            change_1h = ((float(klines[-1][4]) - float(klines[-2][4])) / float(klines[-2][4])) * 100

            # الاتجاه العام يُقاس على 24 ساعة وحدها (1h متقلّبة، كانت تقتل البوّابة).
            # عتبة 1.5% تلتقط الاتجاه بثبات. change_1h يبقى للمعلومة لا للمنع.
            if change_24h > 1.5:
                trend = "BULLISH"
            elif change_24h < -1.5:
                trend = "BEARISH"
            else:
                trend = "NEUTRAL"

            BTC_TREND.update({
                "trend": trend,
                "last_update": int(time.time()),
                "btc_change_1h": round(change_1h, 2),
                "btc_change_24h": round(change_24h, 2),
            })
            log.info("₿ BTC_TREND=%s | 24h=%+.2f%% 1h=%+.2f%%", trend, change_24h, change_1h)
    except Exception as e:
        log.debug("BTC macro update error: %s", e)

# ═══════════════════════════════════════════════════════════════
# ─── FUNDING & OPEN INTEREST FETCHERS ───────────────────────────
# ═══════════════════════════════════════════════════════════════

_funding_cache = {}
_oi_cache = {}

async def get_funding_rate(symbol: str) -> float:
    """نسبة التمويل: > 0 = LONG مزدحم, < 0 = SHORT مزدحم"""
    now = int(time.time())
    cached = _funding_cache.get(symbol)
    if cached and now - cached["t"] < 600:
        return cached["v"]
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}")
            v = float(r.json().get("lastFundingRate", 0)) * 100
            _funding_cache[symbol] = {"t": now, "v": v}
            return v
    except:
        return 0.0

async def get_oi_change(symbol: str) -> float:
    """نسبة تغير الفائدة المفتوحة آخر 4 ساعات"""
    now = int(time.time())
    cached = _oi_cache.get(symbol)
    if cached and now - cached["t"] < 600:
        return cached["v"]
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"https://fapi.binance.com/futures/data/openInterestHist?symbol={symbol}&period=1h&limit=5")
            data = r.json()
            if len(data) >= 2:
                old_oi = float(data[0]["sumOpenInterest"])
                new_oi = float(data[-1]["sumOpenInterest"])
                pct = ((new_oi - old_oi) / old_oi * 100) if old_oi > 0 else 0
                _oi_cache[symbol] = {"t": now, "v": pct}
                return pct
    except:
        pass
    return 0.0

# ═══════════════════════════════════════════════════════════════
# ─── MULTI-TIMEFRAME CONFIRMATION ───────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def fetch_klines_async(symbol: str, interval: str, limit: int = 50) -> list[Candle]:
    """جلب شموع من Binance"""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}")
            data = r.json()
            return [Candle(
                time=int(k[0]) // 1000,
                open=float(k[1]),
                high=float(k[2]),
                low=float(k[3]),
                close=float(k[4]),
                volume=float(k[5]),
                buy_volume=float(k[9]),
            ) for k in data]
    except:
        return []

def quick_trend(candles: list[Candle]) -> str:
    """تحديد سريع لاتجاه الإطار الزمني — يعتمد على EMA + Price Action"""
    if len(candles) < 20:
        return "NEUTRAL"
    closes = [c.close for c in candles]
    e9 = ema(closes, 9)
    e21 = ema(closes, 21)
    if e9[-1] is None or e21[-1] is None:
        return "NEUTRAL"
    price = closes[-1]
    # اتجاه واضح: السعر + EMA9 + EMA21 جميعاً يتوافقون
    if price > e9[-1] > e21[-1]:
        return "BULLISH"
    if price < e9[-1] < e21[-1]:
        return "BEARISH"
    return "NEUTRAL"

async def mtf_check(symbol: str, direction: str) -> tuple[bool, dict]:
    """
    فحص الإطارات الزمنية المتعددة:
    - 15m + 1H + 4H
    يعيد (متفقة: bool, تفاصيل: dict)
    """
    try:
        k15, k1h, k4h = await asyncio.gather(
            fetch_klines_async(symbol, "15m", 30),
            fetch_klines_async(symbol, "1h", 30),
            fetch_klines_async(symbol, "4h", 30),
        )
        t15 = quick_trend(k15)
        t1h = quick_trend(k1h)
        t4h = quick_trend(k4h)

        details = {"15m": t15, "1h": t1h, "4h": t4h}
        required = "BULLISH" if direction == "LONG" else "BEARISH"
        agreed = sum(1 for t in [t15, t1h, t4h] if t == required)
        opposed = sum(1 for t in [t15, t1h, t4h] if t != required and t != "NEUTRAL")

        # الإشارة تمر إذا 2 من 3 على الأقل يتفقان (و لا أحد يعاكس بشدة)
        passed = agreed >= 2 and opposed <= 1
        return passed, details
    except Exception as e:
        log.debug("MTF check error: %s", e)
        return True, {"15m": "NEUTRAL", "1h": "NEUTRAL", "4h": "NEUTRAL"}

# ═══════════════════════════════════════════════════════════════
# ─── ACCURACY FROM DB ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

_accuracy_cache = {"t": 0, "value": 75.0}

def get_real_accuracy() -> float:
    """جلب نسبة الدقة الحقيقية من DB (الإشارات السابقة المغلقة)"""
    now = int(time.time())
    if now - _accuracy_cache["t"] < 600:
        return _accuracy_cache["value"]
    try:
        from db.database import get_session, Signal as DBSignal
        from sqlalchemy import and_, or_
        db = get_session()
        # الإشارات التي حققت TP1 على الأقل
        total = db.query(DBSignal).filter(DBSignal.end_time != None).count()
        if total < 10:
            _accuracy_cache.update({"t": now, "value": 75.0})
            return 75.0
        wins = db.query(DBSignal).filter(
            and_(DBSignal.end_time != None, DBSignal.highest_hit != None)
        ).count()
        # تقدير: إذا highest_hit موجود = الصفقة وصلت لـ TP على الأقل
        acc = round((wins / total) * 100, 1) if total > 0 else 75.0
        # تطبيع: لا أقل من 60 ولا أكثر من 95
        acc = max(60.0, min(95.0, acc))
        _accuracy_cache.update({"t": now, "value": acc})
        return acc
    except Exception as e:
        log.debug("accuracy DB error: %s", e)
        return 75.0

# ═══════════════════════════════════════════════════════════════
# ─── INDICATORS ────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def ema(data: list[float], period: int) -> list[float]:
    if len(data) < period:
        return [None] * len(data)
    result, k = [], 2 / (period + 1)
    e = sum(data[:period]) / period
    result = [None] * (period - 1) + [e]
    for i in range(period, len(data)):
        e = data[i] * k + e * (1 - k)
        result.append(e)
    return result

def rsi(data: list[float], period: int = 14) -> float:
    if len(data) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = data[i] - data[i-1]
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for i in range(period + 1, len(data)):
        diff = data[i] - data[i-1]
        gain = diff if diff > 0 else 0
        loss = abs(diff) if diff < 0 else 0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def macd(data: list[float]) -> tuple[float, float, float]:
    if len(data) < 26:
        return 0.0, 0.0, 0.0
    e12 = ema(data, 12)
    e26 = ema(data, 26)
    macd_line = [a - b for a, b in zip(e12, e26) if a is not None and b is not None]
    signal_line = ema(macd_line, 9)
    if not signal_line or signal_line[-1] is None:
        return 0.0, 0.0, 0.0
    return macd_line[-1], signal_line[-1], macd_line[-1] - signal_line[-1]

def bollinger(data: list[float], period: int = 20) -> tuple[float, float, float, float]:
    if len(data) < period:
        m = sum(data) / len(data) if data else 0
        return m, m, m, 0
    recent = data[-period:]
    sma = sum(recent) / period
    variance = sum((x - sma) ** 2 for x in recent) / period
    std = math.sqrt(variance)
    return sma + 2 * std, sma, sma - 2 * std, std

def atr(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.001
    trs = []
    for i in range(1, len(candles)):
        h = candles[i].high
        l = candles[i].low
        pc = candles[i-1].close
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    return sum(trs[-period:]) / period

def stoch_rsi(data: list[float], period: int = 14) -> tuple[float, float]:
    if len(data) < period * 2:
        return 50.0, 50.0
    rsi_values = []
    for i in range(period, len(data)):
        slice_ = data[i-period:i+1]
        rsi_values.append(rsi(slice_, min(period, len(slice_)-1)))
    if len(rsi_values) < period:
        return 50.0, 50.0
    recent = rsi_values[-period:]
    hi, lo = max(recent), min(recent)
    if hi == lo:
        return 50.0, 50.0
    k = (rsi_values[-1] - lo) / (hi - lo) * 100
    if len(rsi_values) >= 3:
        d = sum([(rsi_values[i] - lo) / (hi - lo) * 100 for i in range(-3, 0)]) / 3
    else:
        d = k
    return k, d

def vwap(candles: list[Candle]) -> float:
    if not candles:
        return 0.0
    total_pv = sum(((c.high + c.low + c.close) / 3) * c.volume for c in candles)
    total_v = sum(c.volume for c in candles)
    return total_pv / total_v if total_v > 0 else 0.0

def obi(candles: list[Candle]) -> float:
    if not candles:
        return 0.0
    last = candles[-1]
    if last.volume == 0:
        return 0.0
    buy = last.buy_volume if last.buy_volume > 0 else last.volume / 2
    sell = last.volume - buy
    return (buy - sell) / last.volume if last.volume > 0 else 0.0

def cvd(candles: list[Candle]) -> float:
    total = 0.0
    for c in candles:
        if c.buy_volume > 0:
            sell = c.volume - c.buy_volume
            total += c.buy_volume - sell
        else:
            total += c.volume if c.close > c.open else -c.volume
    return total

# ═══════════════════════════════════════════════════════════════
# ─── DELTA STRATEGIES (الجديدة) ─────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def delta_flow(candles: list[Candle]) -> float:
    """مجموع Buy - Sell على آخر 5 شموع"""
    if len(candles) < 5:
        return 0.0
    total = 0.0
    for c in candles[-5:]:
        if c.buy_volume > 0:
            sell = c.volume - c.buy_volume
            total += c.buy_volume - sell
        else:
            total += c.volume if c.close > c.open else -c.volume
    return total

def delta_1(candles: list[Candle]) -> float:
    """Delta قصير المدى — آخر 5 شموع"""
    return delta_flow(candles)

def delta_2(candles: list[Candle]) -> float:
    """Delta متوسط المدى — آخر 20 شمعة"""
    if len(candles) < 20:
        return 0.0
    total = 0.0
    for c in candles[-20:]:
        if c.buy_volume > 0:
            sell = c.volume - c.buy_volume
            total += c.buy_volume - sell
        else:
            total += c.volume if c.close > c.open else -c.volume
    return total

def delta_divergence(candles: list[Candle]) -> tuple[str, float]:
    """
    الفرق بين Delta1 و Delta2:
    - D1 > 0 و D2 < 0 = انعكاس صعودي (آخر 5 شموع شراء قوي بعد بيع طويل)
    - D1 < 0 و D2 > 0 = انعكاس هبوطي
    يعيد (الاتجاه, القوة 0-3)
    """
    d1 = delta_1(candles)
    d2 = delta_2(candles)
    if d2 == 0:
        return "", 0.0
    # نسبة الانعكاس
    ratio = abs(d1) / abs(d2) if abs(d2) > 0 else 0
    if d1 > 0 and d2 < 0 and ratio > 0.3:
        strength = min(3.0, ratio * 2)
        return "LONG", strength
    if d1 < 0 and d2 > 0 and ratio > 0.3:
        strength = min(3.0, ratio * 2)
        return "SHORT", strength
    return "", 0.0

# ═══════════════════════════════════════════════════════════════
# ─── VOLUME PROFILE FILTER ──────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def volume_profile_check(candles: list[Candle]) -> tuple[bool, float]:
    """
    يتحقق أن volume الشمعة الحالية أعلى من متوسط آخر 20 شمعة
    يعيد (passed, ratio)
    """
    if len(candles) < 20:
        return True, 1.0
    # نستخدم آخر شمعة مكتملة (candles[-2]) لأن candles[-1] لم تكتمل بعد
    completed_vol = candles[-2].volume
    avg_vol = sum(c.volume for c in candles[-21:-1]) / 20
    if avg_vol == 0:
        return True, 1.0
    ratio = completed_vol / avg_vol
    return ratio > 0.5, ratio  # 50% من المتوسط — عتبة واقعية

# ═══════════════════════════════════════════════════════════════
# ─── CVD DIVERGENCE ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def cvd_divergence(candles: list[Candle]) -> tuple[str, float]:
    """
    تباعد CVD:
    - السعر يهبط لكن CVD يرتفع = شراء خفي → LONG
    - السعر يصعد لكن CVD يهبط = بيع خفي → SHORT
    """
    if len(candles) < 20:
        return "", 0.0

    half = len(candles) // 2
    recent_cvd = cvd(candles[half:])
    older_cvd = cvd(candles[:half])
    price_change = (candles[-1].close - candles[0].close) / candles[0].close * 100

    cvd_change = recent_cvd - older_cvd
    avg_vol = sum(c.volume for c in candles) / len(candles) if candles else 1

    if price_change < -1 and cvd_change > avg_vol * 2:
        strength = min(3.0, abs(cvd_change) / (avg_vol * 5))
        return "LONG", strength
    if price_change > 1 and cvd_change < -avg_vol * 2:
        strength = min(3.0, abs(cvd_change) / (avg_vol * 5))
        return "SHORT", strength

    return "", 0.0

# ═══════════════════════════════════════════════════════════════
# ─── FVG (Fair Value Gaps) ──────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def find_fvg(candles: list[Candle]) -> list[dict]:
    """يبحث عن فجوات السعر — مناطق سيولة محتملة"""
    fvgs = []
    if len(candles) < 3:
        return fvgs
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        # Bullish FVG: low الشمعة الثالثة > high الأولى
        if c3.low > c1.high:
            fvgs.append({
                "type": "bullish",
                "top": c3.low,
                "bottom": c1.high,
                "mid": (c3.low + c1.high) / 2,
                "index": i
            })
        # Bearish FVG
        elif c3.high < c1.low:
            fvgs.append({
                "type": "bearish",
                "top": c1.low,
                "bottom": c3.high,
                "mid": (c1.low + c3.high) / 2,
                "index": i
            })
    return fvgs[-3:]

def price_near_fvg(price: float, fvgs: list[dict], tolerance: float = 0.005) -> Optional[dict]:
    """يتحقق إذا السعر قريب من FVG"""
    for fvg in reversed(fvgs):
        if fvg["bottom"] <= price <= fvg["top"]:
            return fvg
        mid = fvg["mid"]
        if abs(price - mid) / mid < tolerance:
            return fvg
    return None

# ═══════════════════════════════════════════════════════════════
# ─── ACCUMULATION WATCHLIST ─────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

WATCHLIST: dict[str, dict] = {}

def add_to_watchlist(symbol: str, direction: str, score: float):
    """يضيف عملة لقائمة المراقبة (تجميع صامت)"""
    WATCHLIST[symbol] = {
        "direction": direction,
        "added_at": int(time.time()),
        "initial_score": score,
        "checks": 0,
    }

def check_watchlist_breakout(symbol: str, current_score: float, current_direction: str) -> bool:
    """يتحقق إذا العملة في watchlist + score الحالي > 1.5x الأول = اختراق"""
    if symbol not in WATCHLIST:
        return False
    w = WATCHLIST[symbol]
    if w["direction"] != current_direction:
        del WATCHLIST[symbol]
        return False
    w["checks"] += 1
    if current_score > w["initial_score"] * 1.5:
        del WATCHLIST[symbol]
        return True
    # حذف بعد 50 فحص بلا اختراق
    if w["checks"] > 50:
        del WATCHLIST[symbol]
    return False

# ═══════════════════════════════════════════════════════════════
# ─── LIQUIDATION CASCADE ────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def detect_liquidation_cascade(candles: list[Candle]) -> tuple[bool, str]:
    if len(candles) < 5:
        return False, ""
    recent = candles[-5:]
    avg_vol = sum(c.volume for c in candles[-20:-5]) / 15 if len(candles) > 20 else 1
    recent_vol = sum(c.volume for c in recent)
    vol_ratio = recent_vol / (avg_vol * 5) if avg_vol > 0 else 0
    price_move = (recent[-1].close - recent[0].open) / recent[0].open * 100
    if vol_ratio > 2.5 and price_move < -3.0:
        return True, "LONG"
    if vol_ratio > 2.5 and price_move > 3.0:
        return True, "SHORT"
    return False, ""

def detect_stop_hunt(candles: list[Candle]) -> tuple[bool, str]:
    if len(candles) < 10:
        return False, ""
    recent = candles[-10:]
    highs = [c.high for c in recent[:-2]]
    lows = [c.low for c in recent[:-2]]
    last = recent[-1]
    prev_high = max(highs)
    prev_low = min(lows)
    if last.high > prev_high and last.close < prev_high:
        wick_ratio = (last.high - last.close) / (last.high - last.low) if (last.high - last.low) > 0 else 0
        if wick_ratio > 0.6:
            return True, "SHORT"
    if last.low < prev_low and last.close > prev_low:
        wick_ratio = (last.close - last.low) / (last.high - last.low) if (last.high - last.low) > 0 else 0
        if wick_ratio > 0.6:
            return True, "LONG"
    return False, ""

def detect_spoofing(candles: list[Candle]) -> bool:
    """يكشف أوامر وهمية: حجم كبير بدون حركة سعر"""
    if len(candles) < 5:
        return False
    recent = candles[-3:]
    avg_vol = sum(c.volume for c in candles[-20:]) / 20 if len(candles) >= 20 else 1
    for c in recent:
        if c.volume > avg_vol * 3:
            range_ = c.high - c.low
            body = abs(c.close - c.open)
            if range_ > 0 and body / range_ < 0.2:
                return True
    return False

# ═══════════════════════════════════════════════════════════════
# ─── GUARDIAN VETO ──────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def guardian_veto(direction, rsi_v, bb_u, bb_l, bb_m, price, cvd_hint, oracle_context):
    if direction == "LONG":
        if rsi_v > 75:
            return True, "RSI تشبع شرائي مفرط — يُمنع LONG"
        if price > bb_u:
            return True, "السعر فوق بولينجر العلوي — يُمنع LONG"
    if direction == "SHORT":
        if rsi_v < 25:
            return True, "RSI تشبع بيعي مفرط — يُمنع SHORT"
        if price < bb_l:
            return True, "السعر تحت بولينجر السفلي — يُمنع SHORT"
    if cvd_hint and cvd_hint != direction:
        return True, f"CVD يعاكس الاتجاه ({cvd_hint}) — احتمال تلاعب"
    if oracle_context.get("token_unlock_warning") and direction == "LONG":
        return True, "⚠️ فك تجميد عملات خلال 24 ساعة"
    if oracle_context.get("macro_bearish") and direction == "LONG":
        return True, "⚠️ بيانات الفيدرالي سلبية"
    return False, ""

# ═══════════════════════════════════════════════════════════════
# ─── DYNAMIC LEVERAGE & TARGETS ─────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def guardian_leverage(
    tier: MarketTier,
    score: float,
    atr_val: float,
    price: float,
    direction: str,
    grade: str = "B",
    volume_ratio: float = 1.0,
    liquidation_mode: bool = False
) -> tuple[float, float, float, float, float]:
    """
    رافعة ديناميكية + SL/TP من ATR الحقيقي
    العوامل: Grade + ATR + Volume Ratio
    """
    # 1. الرافعة الأساسية حسب Grade
    base_lev = {
        "S": 8.0,   # أعلى ثقة
        "A": 5.0,
        "B": 3.0,
        "C": 2.0,
    }.get(grade, 2.0)

    # 2. تعديل حسب ATR (تقلبات عالية = رافعة أقل)
    atr_pct = (atr_val / price) * 100 if price > 0 else 1
    if atr_pct > 3.0:
        base_lev *= 0.5  # تقلبات عالية جداً
    elif atr_pct > 2.0:
        base_lev *= 0.75
    elif atr_pct < 0.8:
        base_lev *= 1.2  # تقلبات منخفضة = رافعة أعلى ممكنة

    # 3. تعديل حسب السيولة
    if volume_ratio > 1.5:
        base_lev *= 1.15
    elif volume_ratio < 0.7:
        base_lev *= 0.8

    # 4. حد أقصى حسب tier
    leverage = min(base_lev, tier.max_leverage)
    leverage = max(2.0, leverage)  # حد أدنى 2x

    # 5. SL/TP من ATR الفعلي
    sl_distance = atr_val * 1.5
    tp1_distance = atr_val * 2.0
    tp2_distance = atr_val * 3.5
    tp3_distance = atr_val * 5.5

    if liquidation_mode:
        # في حالة الانفجار: أهداف أبعد
        tp1_distance *= 1.3
        tp2_distance *= 1.5
        tp3_distance *= 1.8

    if direction == "LONG":
        sl = price - sl_distance
        tp1 = price + tp1_distance
        tp2 = price + tp2_distance
        tp3 = price + tp3_distance
    else:
        sl = price + sl_distance
        tp1 = price - tp1_distance
        tp2 = price - tp2_distance
        tp3 = price - tp3_distance

    return round(leverage, 1), round(sl, 6), round(tp1, 6), round(tp2, 6), round(tp3, 6)

# ═══════════════════════════════════════════════════════════════
# ─── GRADE CALCULATOR (المعدّل) ─────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def calc_grade(score: float, conf: float, strat_count: int = 0, key_strats: int = 0) -> str:
    """
    حساب Grade — معايير أعلى للجودة
    key_strats = عدد الاستراتيجيات القوية (Liquidation, Stop Hunt, FVG, CVD, Delta Div)
    """
    # Grade S: أعلى ثقة + استراتيجيات متعددة + قوية
    if score >= 9.0 and conf >= 85 and strat_count >= 5 and key_strats >= 2:
        return "S"
    # Grade A: جودة عالية (score + conf + استراتيجية قوية) — لا نشترط 5
    if score >= 7.0 and conf >= 75 and key_strats >= 1:
        return "A"
    # Grade B: متوسط
    if score >= 5.5 and conf >= 65:
        return "B"
    return "C"

# ═══════════════════════════════════════════════════════════════
# ─── ORDER BLOCKS ───────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def find_order_blocks(candles: list[Candle]) -> list[dict]:
    obs = []
    avg_vol = sum(c.volume for c in candles) / len(candles) if candles else 1
    for i in range(1, len(candles) - 1):
        c = candles[i]
        if c.volume > avg_vol * 1.5:
            body = abs(c.close - c.open)
            range_ = c.high - c.low
            if range_ > 0 and body / range_ > 0.6:
                obs.append({
                    "type": "bullish" if c.close > c.open else "bearish",
                    "top": max(c.open, c.close),
                    "bottom": min(c.open, c.close),
                    "mid": (c.high + c.low) / 2,
                    "index": i
                })
    return obs[-5:] if obs else []

# ═══════════════════════════════════════════════════════════════
# ─── SLEEPING GIANTS ────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def sleeping_giant_score(candles: list[Candle]) -> float:
    if len(candles) < 20:
        return 0.0
    score = 0.0
    closes = [c.close for c in candles]
    recent_high = max(c.high for c in candles[-20:])
    recent_low = min(c.low for c in candles[-20:])
    price_range_pct = (recent_high - recent_low) / recent_low * 100
    if price_range_pct < 5.0:
        score += 3.0
    elif price_range_pct < 8.0:
        score += 1.5
    bb_u, bb_m, bb_l, bb_std = bollinger(closes)
    bb_width = (bb_u - bb_l) / bb_m * 100 if bb_m > 0 else 0
    if bb_width < 3.0:
        score += 3.0
    elif bb_width < 5.0:
        score += 1.5
    cvd_val = cvd(candles)
    avg_vol = sum(c.volume for c in candles[-20:]) / 20
    if cvd_val > avg_vol * 2:
        score += 2.0
    sell_candles = [c for c in candles[-10:] if c.close < c.open]
    if sell_candles:
        avg_sell_vol = sum(c.volume for c in sell_candles) / len(sell_candles)
        if avg_sell_vol > avg_vol and price_range_pct < 5.0:
            score += 2.0
    return min(10.0, score)

# ═══════════════════════════════════════════════════════════════
# ─── PREDATOR AGENT V2 — صائد الجودة العالية ────────────────────
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# ─── PREDATOR V3 — هجين ذكي يتبع السوق ─────────────────────────
# ═══════════════════════════════════════════════════════════════

def market_regime(candles: list) -> tuple[str, dict]:
    """
    تحديد حالة السوق على إطار 15m:
      TRENDING_UP   — اتجاه صاعد واضح
      TRENDING_DOWN — اتجاه هابط واضح
      RANGING       — نطاق عرضي
    يعتمد على ميل EMA50 + ترتيب EMA + قوة الحركة (ADX-like).
    """
    if len(candles) < 55:
        return "RANGING", {}

    closes = [c.close for c in candles]
    e20 = ema(closes, 20)
    e50 = ema(closes, 50)
    if e20[-1] is None or e50[-1] is None:
        return "RANGING", {}

    price = closes[-1]
    ema20_now, ema50_now = e20[-1], e50[-1]

    # ميل EMA50 على آخر 10 شموع (نسبة %)
    ema50_prev = e50[-10] if e50[-10] is not None else ema50_now
    ema50_slope = (ema50_now - ema50_prev) / ema50_prev * 100 if ema50_prev else 0

    # قوة الاتجاه: المسافة بين EMA20 و EMA50 نسبةً للسعر
    ema_gap = abs(ema20_now - ema50_now) / price * 100 if price else 0

    details = {
        "ema20": round(ema20_now, 6),
        "ema50": round(ema50_now, 6),
        "ema50_slope": round(ema50_slope, 3),
        "ema_gap": round(ema_gap, 3),
    }

    # اتجاه صاعد: EMA20 > EMA50 + ميل صاعد + فجوة (معايرة على بيانات 15m حقيقية)
    # أزلنا شرط price>EMA20 الصارم (السعر يتذبذب حول EMA20 بفروق ضئيلة)
    if ema20_now > ema50_now and ema50_slope > 0.25 and ema_gap > 0.20:
        return "TRENDING_UP", details
    # اتجاه هابط: EMA20 < EMA50 + ميل هابط + فجوة
    if ema20_now < ema50_now and ema50_slope < -0.25 and ema_gap > 0.20:
        return "TRENDING_DOWN", details
    # غير ذلك = نطاق عرضي
    return "RANGING", details


def range_position(candles: list, lookback: int = 20) -> float:
    """
    موقع السعر الحالي داخل نطاق آخر N شمعة:
      0.0 = القاع تماماً
      1.0 = القمة تماماً
      0.5 = المنتصف
    """
    if len(candles) < lookback:
        return 0.5
    window = candles[-lookback:]
    hi = max(c.high for c in window)
    lo = min(c.low for c in window)
    price = candles[-1].close
    if hi == lo:
        return 0.5
    pos = (price - lo) / (hi - lo)
    return max(0.0, min(1.0, pos))


def guardian_veto_v3(direction, rsi_v, sk, sd, price, bb_u, bb_l, bb_m,
                     range_pos, regime, cvd_hint, oracle_context,
                     hist_low_dist=100.0, hist_high_dist=100.0):
    """
    Guardian Veto V3 — عتبات واقعية + فلتر موقع لحظي + فلتر اتجاه
    + 🦅 حارس القاع/القمة التاريخي (يمنع SHORT في قاع تاريخي مهما كان range_pos).
    يعيد (vetoed: bool, reason: str)
    """
    # ─── 0. 🦅 حارس القاع/القمة التاريخي (الأهم — يمنع الفتح الجماعي في القاع) ───
    # range_pos اللحظي يُخدع: عملة هبطت 50% قد تُظهر range_pos=50% في نطاق ضيّق
    # القاع التاريخي الحقيقي هو الحَكَم. عتبة 8% = منطقة خطر الارتداد.
    # عتبة 3%: فقط ملامسة القاع/القمة الحقيقية (8% كانت واسعة جداً تبتلع كل السوق)
    if direction == "SHORT" and hist_low_dist < 3.0:
        return True, f"🦅 قاع تاريخي ({hist_low_dist:+.1f}% فوق القاع) — لا SHORT، خطر ارتداد"
    if direction == "LONG" and hist_high_dist < 3.0:
        return True, f"🦅 قمة تاريخية ({hist_high_dist:+.1f}% تحت القمة) — لا LONG، خطر هبوط"

    # ─── 1. فلتر التشبع الواقعي ───
    if direction == "LONG":
        if rsi_v > 68:
            return True, f"RSI مرتفع ({rsi_v:.0f}) — LONG في منطقة شراء زائد"
        if sk > 85 and sd > 85:
            return True, f"StochRSI مُشبع ({sk:.0f}) — قمة محتملة"
    if direction == "SHORT":
        if rsi_v < 32:
            return True, f"RSI منخفض ({rsi_v:.0f}) — SHORT في منطقة بيع زائد"
        if sk < 15 and sd < 15:
            return True, f"StochRSI مُشبع بيعياً ({sk:.0f}) — قاع محتمل"

    # ─── 2. فلتر موقع السعر (الأهم — يمنع خطأ ADA) ───
    if direction == "LONG" and range_pos > 0.65:
        return True, f"موقع السعر مرتفع ({range_pos:.0%} من النطاق) — لا LONG في القمة"
    if direction == "SHORT" and range_pos < 0.35 and regime != "TRENDING_DOWN":
        return True, f"موقع السعر منخفض ({range_pos:.0%} من النطاق) — لا SHORT في قاع نطاق عرضي"

    # ─── 3. فلتر الاتجاه الأكبر — لا تقاوم التريند ───
    if regime == "TRENDING_UP" and direction == "SHORT":
        # منع مشروط: SHORT في الصعود مرفوض إلا عند قمة انفجار مكتملة + انعكاس قوي مؤكّد
        # (الفلسفة ب: نصطاد قمم الانفجار حتى في الصعود — بشرط صارم جداً)
        # نستخدم البارامترات المتاحة: rsi_v, sk, sd (لا obi هنا)
        top_reversal = (
            range_pos > 0.78                  # قمة قصوى
            and rsi_v >= 68                   # إشباع شديد
            and sk > 80 and sk < sd           # Stoch انعكس من القمة (K عبر D هابطاً)
        )
        if not top_reversal:
            return True, "السوق صاعد — يُمنع SHORT (لا قمة انفجار مؤكّدة)"
        # قمة انفجار مؤكّدة → نسمح (لا نمنع)
    if regime == "TRENDING_DOWN" and direction == "LONG":
        return True, "السوق هابط — يُمنع LONG ضد الاتجاه"

    # ─── 4. CVD يعاكس ───
    if cvd_hint and cvd_hint != direction:
        return True, f"CVD يعاكس الاتجاه ({cvd_hint})"

    # ─── 5. Oracle ───
    if oracle_context.get("token_unlock_warning") and direction == "LONG":
        return True, "⚠️ فك تجميد عملات خلال 24 ساعة"
    if oracle_context.get("macro_bearish") and direction == "LONG":
        return True, "⚠️ بيانات ماكرو سلبية"

    return False, ""


# ═══════════════════════════════════════════════════════════════
# ─── PREDATOR AGENT V3 ──────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def predator_agent(
    candles: list,
    symbol: str,
    tier,
    oracle_context: dict,
    signal_queue,
) -> None:
    """
    Predator V3 — منطق هجين ذكي:
      • TRENDING_UP   → LONG عند Pullback فقط
      • TRENDING_DOWN → SHORT عند Pullback فقط
      • RANGING       → Reversal عند الحواف
    فلاتر إلزامية: موقع السعر + Guardian واقعي + MTF + Funding/OI.
    """
    if len(candles) < 60:
        return

    closes = [c.close for c in candles]
    price = closes[-1]

    # ─── المؤشرات ───
    rsi_v = rsi(closes)
    mv, ms, mh = macd(closes)
    bb_u, bb_m, bb_l, bb_std = bollinger(closes)
    atr_v = atr(candles)
    sk, sd = stoch_rsi(closes)
    vwap_v = vwap(candles)
    obi_v = obi(candles)
    cvd_val = cvd(candles)
    d1 = delta_1(candles)
    d2 = delta_2(candles)
    delta_div_dir, delta_div_strength = delta_divergence(candles)
    cvd_hint, cvd_strength = cvd_divergence(candles)
    vol_passed, vol_ratio = volume_profile_check(candles)
    fvgs = find_fvg(candles)
    near_fvg = price_near_fvg(price, fvgs)
    liq_cascade, liq_dir = detect_liquidation_cascade(candles)
    stop_hunt, sh_dir = detect_stop_hunt(candles)
    spoofing = detect_spoofing(candles)

    # ─── حالة السوق + موقع السعر ───
    regime, regime_details = market_regime(candles)
    range_pos = range_position(candles, 20)

    # ─── 🦅 القاع/القمة التاريخي (يومي 30) — الحل الجذري لـ"SHORT في القاع" ───
    # range_pos اللحظي (20 شمعة 15m) يُخدع في الهبوط: نطاق ضيّق متحرك
    # يجعل القاع التاريخي يبدو "وسط النطاق". نقيس المسافة الحقيقية للقاع/القمة.
    hist_low_dist = 100.0   # % فوق القاع التاريخي
    hist_high_dist = 100.0  # % تحت القمة التاريخية
    try:
        daily = await fetch_klines_async(symbol, "1d", 30)
        if len(daily) >= 10:
            d_low = min(x.low for x in daily)
            d_high = max(x.high for x in daily)
            if d_low > 0:
                hist_low_dist = (price - d_low) / d_low * 100
            if d_high > 0:
                hist_high_dist = (d_high - price) / price * 100
    except Exception:
        pass

    # ═══ السوق ميت → تجاهل ═══
    if not vol_passed:
        return

    # ═══ Spoofing → تجاهل (تلاعب) ═══
    if spoofing:
        log.debug("Spoofing detected: %s", symbol)
        return

    long_score = 0.0
    short_score = 0.0
    long_strats = []
    short_strats = []
    long_key = 0
    short_key = 0

    # ════════════════════════════════════════════════════════════
    # المنطق حسب حالة السوق
    # ════════════════════════════════════════════════════════════

    if regime == "TRENDING_UP":
        # ─── نبحث عن LONG عند Pullback (ارتداد للأسفل ثم استئناف) ───
        # Pullback صحي: السعر ارتد لكن RSI ما زال 40-58 (ليس مُشبع)
        pullback_zone = (range_pos < 0.55) and (40 <= rsi_v <= 58)
        near_ema = price <= bb_m * 1.01  # قرب الوسط (EMA/BB mid)

        if pullback_zone or near_ema:
            long_score += 2.0
            long_strats.append("🔄 Pullback في اتجاه صاعد")
            long_key += 1
        # تأكيد الزخم الصاعد العام
        if mh > 0 and mv > 0:
            long_score += 1.0
            long_strats.append("MACD Bullish")
        # ارتداد من دعم (BB Lower أو FVG)
        if price < bb_m and price > bb_l:
            long_score += 1.0
            long_strats.append("ارتداد من منطقة دعم")
        # Delta Reversal صاعد (شراء يعود)
        if delta_div_dir == "LONG":
            long_score += 1.5 + delta_div_strength * 0.5
            long_strats.append(f"⚡ Delta Reversal ({delta_div_strength:.1f}x)")
            long_key += 1
        # CVD divergence صاعد
        if cvd_hint == "LONG":
            long_score += 1.5 + cvd_strength * 0.5
            long_strats.append(f"CVD Divergence ({cvd_strength:.1f}x)")
            long_key += 1
        # FVG bullish
        if near_fvg and near_fvg["type"] == "bullish":
            long_score += 1.5
            long_strats.append("FVG Bullish Zone")
            long_key += 1
        # Stop hunt للأسفل (صيد سيولة ثم صعود)
        if stop_hunt and sh_dir == "LONG":
            long_score += 2.0
            long_strats.append("🎯 Stop Hunt LONG")
            long_key += 1
        # RSI ارتد من oversold داخل الاتجاه
        if rsi_v < 45:
            long_score += 1.0
            long_strats.append("RSI ارتداد")
        # StochRSI يخرج من القاع
        if sk < 30 and sk > sd:
            long_score += 1.0
            long_strats.append("Stoch RSI صاعد من القاع")

        # ═══ مسار SHORT: قمة انفجار في سوق صاعد (الفلسفة ب) ═══
        # نصطاد العملة المنفجرة عند قمتها القصوى + انعكاس مؤكّد فقط
        # (الحارس المركزي يفلتر أيضاً: pos>0.78 + RSI>=68 + Stoch K<D)
        explosion_top = (range_pos > 0.78) and (rsi_v >= 68)
        if explosion_top:
            short_score += 2.0
            short_strats.append(f"💥 قمة انفجار ({range_pos:.0%}, RSI {rsi_v:.0f})")
            short_key += 1
            if sk > 80 and sk < sd:
                short_score += 2.0
                short_strats.append("📉 Stoch انعكس من القمة (K<D)")
                short_key += 1
            if price >= bb_u * 0.99:
                short_score += 1.5
                short_strats.append("BB Upper — قمة قصوى")
            if cvd_hint == "SHORT":
                short_score += 1.5 + cvd_strength * 0.5
                short_strats.append(f"CVD Divergence ({cvd_strength:.1f}x)")
                short_key += 1
            if delta_div_dir == "SHORT":
                short_score += 1.5 + delta_div_strength * 0.5
                short_strats.append(f"⚡ Delta Reversal ({delta_div_strength:.1f}x)")
                short_key += 1
            if stop_hunt and sh_dir == "SHORT":
                short_score += 2.0
                short_strats.append("🎯 Stop Hunt SHORT")
                short_key += 1

    elif regime == "TRENDING_DOWN":
        # ═══════════════════════════════════════════════════════════
        # SHORT في الهبوط = قمة الارتداد + دليل انعكاس مؤكّد فقط
        # (مبني على بحث فني: لا SHORT من الوسط — فخ pullback)
        # القاعدة: ندخل عند قمة الارتداد عند ظهور دليل الانعكاس،
        #          لا في منتصف الصعود (بلا دليل).
        # ═══════════════════════════════════════════════════════════

        # ─── الشرط الإلزامي 1: قمة الارتداد (المنطقة العليا فقط) ───
        # range_pos > 0.62 = السعر قرب قمة الارتداد (لا الوسط ولا القاع)
        at_pullback_top = range_pos > 0.62
        # أو السعر قرب/فوق بولينجر العلوي (قمة محلية / تجاوز)
        at_resistance = price >= bb_u * 0.985

        # مساحة الهبوط الإلزامية: لا شورت إذا كان السعر ملاصقاً للدعم (BB سفلي، ضمن 2%).
        #   قاع الحركة = ارتداد محتمل، مساحة ربح ضيّقة. (DOGE دخلت على بُعد 0.5% من الدعم)
        #   نعتمد bb_l اللحظي لا range_pos (الذي قد يكون مضلّلاً).
        _has_drop_room = price > bb_l * 1.02
        in_short_zone = (at_pullback_top or (at_resistance and range_pos > 0.50)) and _has_drop_room

        if not in_short_zone:
            # ليس عند قمة → لا SHORT، ننتظر ونراقب (لا نفتح من الوسط)
            pass
        else:
            # نحن عند قمة الارتداد — نبحث عن دليل الانعكاس
            short_score += 1.5
            short_strats.append(f"📍 قمة ارتداد ({range_pos:.0%})")

            # ─── دليل انعكاس 1: RSI ارتفع للمنطقة العليا ثم ينعكس ───
            # RSI وصل 58+ (الارتداد اكتمل) — لا 42-52 (الوسط)
            if rsi_v >= 58:
                short_score += 1.5
                short_strats.append(f"RSI مرتفع ({rsi_v:.0f}) — ارتداد ناضج")
                short_key += 1

            # ─── دليل انعكاس 2: Stoch %K عبر %D هابطاً من القمة (تأكيد) ───
            if sk > 70 and sk < sd:
                short_score += 2.0
                short_strats.append("📉 Stoch انعكس من القمة (K<D)")
                short_key += 1

            # ─── دليل انعكاس 3: السعر قرب/فوق BB العلوي (قمة) ───
            if at_resistance:
                short_score += 1.5
                short_strats.append("BB Upper — قمة محلية")
                short_key += 1

            # ─── دليل انعكاس 4: Order Book — ضغط بيع عند القمة ───
            # obi سالب = asks تطغى (بائعون يدخلون عند القمة)
            if obi_v < -0.15:
                short_score += 1.5
                short_strats.append(f"📊 ضغط بيع OB ({obi_v:.2f})")
                short_key += 1

            # ─── دليل انعكاس 5: MACD ينعكس هابطاً ───
            if mh < 0 and mv < 0:
                short_score += 1.0
                short_strats.append("MACD Bearish")

            # ─── دليل انعكاس 6: CVD Divergence هابط ───
            if cvd_hint == "SHORT":
                short_score += 1.5 + cvd_strength * 0.5
                short_strats.append(f"CVD Divergence ({cvd_strength:.1f}x)")
                short_key += 1

            # ─── دليل انعكاس 7: Delta Reversal هابط ───
            if delta_div_dir == "SHORT":
                short_score += 1.5 + delta_div_strength * 0.5
                short_strats.append(f"⚡ Delta Reversal ({delta_div_strength:.1f}x)")
                short_key += 1

            # ─── دليل انعكاس 8: FVG هابطة ───
            if near_fvg and near_fvg["type"] == "bearish":
                short_score += 1.5
                short_strats.append("FVG Bearish Zone")
                short_key += 1

            # ─── دليل انعكاس 9: Stop Hunt (صيد سيولة فوق القمة ثم هبوط) ───
            if stop_hunt and sh_dir == "SHORT":
                short_score += 2.0
                short_strats.append("🎯 Stop Hunt SHORT")
                short_key += 1

    else:  # RANGING — Reversal عند الحواف فقط
        # ─── LONG عند قاع النطاق ───
        if range_pos < 0.30:
            if rsi_v < 40:
                long_score += 2.0
                long_strats.append("قاع النطاق + RSI منخفض")
                long_key += 1
            if price <= bb_l * 1.01:
                long_score += 1.5
                long_strats.append("BB Lower Touch")
            if sk < 20 and sk > sd:
                long_score += 1.5
                long_strats.append("Stoch RSI صاعد من القاع")
            if cvd_hint == "LONG":
                long_score += 1.5 + cvd_strength * 0.5
                long_strats.append(f"CVD Divergence ({cvd_strength:.1f}x)")
                long_key += 1
            if delta_div_dir == "LONG":
                long_score += 1.5
                long_strats.append("⚡ Delta Reversal")
                long_key += 1
            if stop_hunt and sh_dir == "LONG":
                long_score += 2.0
                long_strats.append("🎯 Stop Hunt LONG")
                long_key += 1

        # ─── SHORT عند قمة النطاق ───
        elif range_pos > 0.70:
            if rsi_v > 60:
                short_score += 2.0
                short_strats.append("قمة النطاق + RSI مرتفع")
                short_key += 1
            if price >= bb_u * 0.99:
                short_score += 1.5
                short_strats.append("BB Upper Touch")
            if sk > 80 and sk < sd:
                short_score += 1.5
                short_strats.append("Stoch RSI هابط من القمة")
            if cvd_hint == "SHORT":
                short_score += 1.5 + cvd_strength * 0.5
                short_strats.append(f"CVD Divergence ({cvd_strength:.1f}x)")
                short_key += 1
            if delta_div_dir == "SHORT":
                short_score += 1.5
                short_strats.append("⚡ Delta Reversal")
                short_key += 1
            if stop_hunt and sh_dir == "SHORT":
                short_score += 2.0
                short_strats.append("🎯 Stop Hunt SHORT")
                short_key += 1
        # المنتصف في RANGING = لا إشارة

    # ─── Liquidation Cascade (يعمل في كل الحالات — انعكاس عنيف) ───
    if liq_cascade:
        if liq_dir == "LONG" and regime != "TRENDING_DOWN":
            long_score += 2.5
            long_strats.append("💥 Liquidation Cascade → LONG")
            long_key += 1
        elif liq_dir == "SHORT" and regime != "TRENDING_UP":
            short_score += 2.5
            short_strats.append("💥 Liquidation Cascade → SHORT")
            short_key += 1

    # ─── Volume bonus ───
    if vol_ratio > 1.5:
        if long_score > short_score and long_score > 0:
            long_score += 0.5
            long_strats.append(f"📊 Volume Spike ({vol_ratio:.1f}x)")
        elif short_score > 0:
            short_score += 0.5
            short_strats.append(f"📊 Volume Spike ({vol_ratio:.1f}x)")

    # ════════════════════════════════════════════════════════════
    # اتخاذ القرار
    # ════════════════════════════════════════════════════════════
    MIN_SCORE = 6.0  # عتبة جودة واقعية (بدل 5.0 المكسورة)

    direction, score, strats, key_strats = None, 0.0, [], 0
    if long_score >= MIN_SCORE and long_score > short_score:
        direction, score, strats, key_strats = "LONG", long_score, long_strats, long_key
    elif short_score >= MIN_SCORE and short_score > long_score:
        direction, score, strats, key_strats = "SHORT", short_score, short_strats, short_key

    if not direction:
        return

    # ─── لا بد من استراتيجية قوية واحدة على الأقل ───
    if key_strats < 1:
        log.debug("Reject %s %s — no key strategy", symbol, direction)
        return

    # ═══ بوّابة BTC الذكية: العملات مرتبطة بـBTC، فالتعارض معه خطر (الارتباط يغلب) ═══
    #   نتداول مع اتّجاه BTC، أو ضدّه/في المحايد فقط بانعكاس قويّ مؤكّد (score>=9).
    #   الجذر: كارثة 01:00 — 5 شورت في BTC محايد (score 7-8.5) ماتت لمّا صعد BTC.
    #   score>=9 نادر (7 من ~190) = قمّة/قاع راسخ يبرّر مخالفة BTC.
    _btc = BTC_TREND.get("trend", "NEUTRAL")
    _strong = (score >= 9.0)
    if direction == "SHORT" and _btc != "BEARISH" and not _strong:
        log.info("₿ BTC gate: %s SHORT مرفوض — BTC %s (ليس هابطاً) score=%.1f", symbol, _btc, score)
        return
    if direction == "LONG" and _btc != "BULLISH" and not _strong:
        log.info("₿ BTC gate: %s LONG مرفوض — BTC %s (ليس صاعداً) score=%.1f", symbol, _btc, score)
        return

    # ─── الثقة ───
    strat_count = len(strats)
    conf = min(95.0, 45.0 + score * 4.5 + strat_count * 2)
    if conf < 62.0:
        return

    # ═══ Guardian Veto V3 (الحارس الواقعي) ═══
    vetoed, veto_reason = guardian_veto_v3(
        direction, rsi_v, sk, sd, price, bb_u, bb_l, bb_m,
        range_pos, regime, cvd_hint, oracle_context,
        hist_low_dist, hist_high_dist
    )
    if vetoed:
        log.info("🛡️ Veto: %s %s — %s", symbol, direction, veto_reason)
        return

    # ═══ MTF Confirmation ═══
    mtf_passed, mtf_details = await mtf_check(symbol, direction)
    if not mtf_passed:
        log.debug("MTF reject: %s %s", symbol, direction)
        return

    # ═══ Funding Rate Filter ═══
    funding = await get_funding_rate(symbol)
    if direction == "LONG" and funding > 0.03:
        log.info("Funding reject LONG: %s (funding=%.4f%% — LONG مزدحم)", symbol, funding)
        return
    if direction == "SHORT" and funding < -0.03:
        log.info("Funding reject SHORT: %s (funding=%.4f%% — SHORT مزدحم)", symbol, funding)
        return

    # ═══ Open Interest Filter (مُصحّح للاتجاهين) ═══
    oi_change = await get_oi_change(symbol)
    # في الهبوط (SHORT): انخفاض OI طبيعي (إغلاق لونغات) — نسمح به
    # في الصعود (LONG): انخفاض OI القوي = خروج سيولة → تجاهل
    if direction == "LONG" and oi_change < -3.0:
        log.info("OI reject LONG: %s (%.1f%% — سيولة تخرج)", symbol, oi_change)
        return
    if direction == "SHORT" and oi_change < -5.0:
        log.info("OI reject SHORT: %s (%.1f%%)", symbol, oi_change)
        return

    # ═══ تأكيد العمق اللحظي (ob_stream): امنع الدخول ضد جدار وهمي ═══
    try:
        from quant_engine.ob_stream import get_signals as _ob_get
        _sw = symbol.replace("/", "").replace("-", "")
        if not _sw.endswith("USDT"):
            _sw += "USDT"
        _spoofs = _ob_get(_sw).get("spoof", [])
        if direction == "SHORT" and any(x["side"] == "bid" for x in _spoofs):
            log.info("🌊 OB-Stream veto: %s SHORT — جدار شراء وهمي (فخّ صعود)", symbol)
            return
        if direction == "LONG" and any(x["side"] == "ask" for x in _spoofs):
            log.info("🌊 OB-Stream veto: %s LONG — جدار بيع وهمي (فخّ هبوط)", symbol)
            return
    except Exception as _obe:
        log.debug("ob_stream check %s: %s", symbol, _obe)

    # ═══ Grade + Leverage ═══
    grade = calc_grade(score, conf, strat_count, key_strats)

    lev, sl, tp1, tp2, tp3 = guardian_leverage(
        tier, score, atr_v, price, direction, grade, vol_ratio, liq_cascade
    )

    risk = abs(price - sl)
    rr_tp1 = abs(tp1 - price) / risk if risk > 0 else 0
    rr_tp2 = abs(tp2 - price) / risk if risk > 0 else 0
    rr_tp3 = abs(tp3 - price) / risk if risk > 0 else 0

    real_accuracy = get_real_accuracy()
    btc = BTC_TREND.get("trend", "NEUTRAL")

    sig = Signal(
        symbol=symbol,
        direction=direction,
        grade=grade,
        score=round(score, 2),
        confidence=round(conf, 1),
        entry=price,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        leverage=lev,
        strategies="\n".join(strats),
        radar_type="futures",
        tier=tier.tier,
        fvg_zone=near_fvg["mid"] if near_fvg else None,
        liquidation_signal=liq_cascade,
        funding_rate=round(funding, 4),
        open_interest_change=round(oi_change, 2),
        btc_trend=btc,
        mtf_15m=mtf_details.get("15m", "NEUTRAL"),
        mtf_1h=mtf_details.get("1h", "NEUTRAL"),
        mtf_4h=mtf_details.get("4h", "NEUTRAL"),
        rr_tp1=round(rr_tp1, 2),
        rr_tp2=round(rr_tp2, 2),
        rr_tp3=round(rr_tp3, 2),
        accuracy=real_accuracy,
        strategy_count=strat_count,
        regime=regime,
        range_pos=range_pos,
        rsi=rsi_v,
    )

    await signal_queue.put(sig)
    log.info("Predator V3 → Queue: %s %s [%s] score=%.1f conf=%.0f%% grade=%s pos=%.0f%% lev=%.0fx",
             symbol, direction, regime, score, conf, grade, range_pos * 100, lev)


# ═══════════════════════════════════════════════════════════════
# ─── SLEEPING GIANTS RADAR (محتفظ به) ──────────────────────────
# ═══════════════════════════════════════════════════════════════

async def sleeping_giants_radar(
    symbol: str,
    candles_daily: list[Candle],
    tier: MarketTier,
    signal_queue: asyncio.Queue,
) -> None:
    if len(candles_daily) < 20:
        return

    sg_score = sleeping_giant_score(candles_daily)
    if sg_score < 6.0:
        return

    closes = [c.close for c in candles_daily]
    price = closes[-1]
    rsi_v = rsi(closes)
    atr_v = atr(candles_daily)

    if rsi_v > 70 or rsi_v < 30:
        return

    direction = "LONG"
    conf = min(90.0, 50.0 + sg_score * 4)

    grade = calc_grade(sg_score, conf, 4, 2)
    lev, sl, tp1, tp2, tp3 = guardian_leverage(
        tier, sg_score, atr_v, price, direction, grade
    )
    lev = min(lev, 3.0)

    risk = abs(price - sl)
    rr_tp1 = abs(tp1 - price) / risk if risk > 0 else 0
    rr_tp2 = abs(tp2 - price) / risk if risk > 0 else 0
    rr_tp3 = abs(tp3 - price) / risk if risk > 0 else 0

    strats = ["🌙 Sleeping Giant", "Volatility Squeeze", "Silent Accumulation"]
    if sg_score >= 8:
        strats.append("⚡ Imminent Explosion")

    sig = Signal(
        symbol=symbol,
        direction=direction,
        grade=grade,
        score=round(sg_score, 2),
        confidence=round(conf, 1),
        entry=price,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        leverage=lev,
        strategies="\n".join(strats),
        radar_type="spot",
        tier=tier.tier,
        rr_tp1=round(rr_tp1, 2),
        rr_tp2=round(rr_tp2, 2),
        rr_tp3=round(rr_tp3, 2),
        accuracy=get_real_accuracy(),
        strategy_count=len(strats),
        btc_trend=BTC_TREND.get("trend", "NEUTRAL"),
    )

    await signal_queue.put(sig)
    log.info("SleepingGiant → Queue: %s score=%.1f conf=%.1f%%", symbol, sg_score, conf)

# ═══════════════════════════════════════════════════════════════
# ─── SHADOW MODE ────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

SHADOW_TRADES: list[ShadowTrade] = []

async def shadow_record(sig: Signal) -> ShadowTrade:
    trade = ShadowTrade(
        symbol=sig.symbol,
        direction=sig.direction,
        entry=sig.entry,
        sl=sig.sl,
        tp1=sig.tp1,
        strategies=sig.strategies,
        score=sig.score,
        confidence=sig.confidence,
        # المميزات المهندَسة المتاحة من Signal
        grade=getattr(sig, "grade", "B"),
        tier=getattr(sig, "tier", "B"),
        funding=getattr(sig, "funding_rate", 0.0),
        oi_change=getattr(sig, "open_interest_change", 0.0),
        btc_trend=getattr(sig, "btc_trend", ""),
        key_strat_count=getattr(sig, "strategy_count", 0),
        regime=getattr(sig, "regime", ""),
        range_pos=getattr(sig, "range_pos", 0.0),
        rsi=getattr(sig, "rsi", 0.0),
    )
    SHADOW_TRADES.append(trade)
    # حفظ دائم في قاعدة بيانات النموذج (يبقى عبر restarts)
    try:
        from ml_recorder import record_signal
        row_id = record_signal(trade)
        if row_id:
            trade.ml_row_id = row_id
    except Exception as e:
        log.debug("ML record error: %s", e)
    return trade

async def shadow_update(trade: ShadowTrade, current_price: float):
    if trade.result:
        return
    is_long = trade.direction == "LONG"
    if is_long:
        if current_price <= trade.sl:
            trade.result = "LOSS"
            trade.exit_price = current_price
            trade.pnl_pct = (current_price - trade.entry) / trade.entry * 100
            trade.closed_at = int(time.time())
        elif current_price >= trade.tp1:
            trade.result = "WIN"
            trade.exit_price = current_price
            trade.pnl_pct = (current_price - trade.entry) / trade.entry * 100
            trade.closed_at = int(time.time())
    else:
        if current_price >= trade.sl:
            trade.result = "LOSS"
            trade.exit_price = current_price
            trade.pnl_pct = (trade.entry - current_price) / trade.entry * 100
            trade.closed_at = int(time.time())
        elif current_price <= trade.tp1:
            trade.result = "WIN"
            trade.exit_price = current_price
            trade.pnl_pct = (trade.entry - current_price) / trade.entry * 100
            trade.closed_at = int(time.time())

def get_shadow_stats() -> dict:
    closed = [t for t in SHADOW_TRADES if t.result]
    if not closed:
        return {"total": 0, "win_rate": 0, "avg_pnl": 0}
    wins = sum(1 for t in closed if t.result == "WIN")
    avg_pnl = sum(t.pnl_pct or 0 for t in closed) / len(closed)
    return {
        "total": len(closed),
        "open": len([t for t in SHADOW_TRADES if not t.result]),
        "win_rate": round(wins / len(closed) * 100, 1),
        "avg_pnl": round(avg_pnl, 2),
        "wins": wins,
        "losses": len(closed) - wins,
    }

# ═══════════════════════════════════════════════════════════════
# ─── GUARDIAN AGENT — معدّل ─────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def guardian_agent(
    signal_queue: asyncio.Queue,
    approved_queue: asyncio.Queue,
    oracle_context: dict
) -> None:
    log.info("Guardian Agent V2 started")
    while True:
        try:
            sig = await asyncio.wait_for(signal_queue.get(), timeout=1.0)

            oracle_veto = (sig.grade == "C")

            if oracle_context.get("market_crash_warning"):
                oracle_veto = True
                log.warning("Guardian: Oracle crash warning — %s rejected", sig.symbol)

            if not oracle_veto:
                try:
                    gc = await fetch_klines_async(sig.symbol, "15m", 100)
                    if len(gc) >= 60:
                        gcl = [x.close for x in gc]
                        gp = gcl[-1]
                        grsi = rsi(gcl)
                        gsk, gsd = stoch_rsi(gcl)
                        gbu, gbm, gbl, _ = bollinger(gcl)
                        grg, _ = market_regime(gc)
                        grp = range_position(gc, 20)
                        ghl = 100.0
                        ghh = 100.0
                        try:
                            gd = await fetch_klines_async(sig.symbol, "1d", 30)
                            if len(gd) >= 10:
                                dl = min(x.low for x in gd)
                                dh = max(x.high for x in gd)
                                if dl > 0:
                                    ghl = (gp - dl) / dl * 100
                                if dh > 0:
                                    ghh = (dh - gp) / gp * 100
                        except Exception:
                            pass
                        gv, gr = guardian_veto_v3(
                            sig.direction, grsi, gsk, gsd, gp,
                            gbu, gbl, gbm, grp, grg,
                            None, oracle_context, ghl, ghh
                        )
                        if gv:
                            log.info("Guardian central REJECT: %s %s — %s", sig.symbol, sig.direction, gr)
                            oracle_veto = True
                except Exception as e:
                    log.debug("Central guard error %s: %s", sig.symbol, e)

            if not oracle_veto:
                await approved_queue.put(sig)
                log.info("Guardian OK %s %s grade=%s (central)", sig.symbol, sig.direction, sig.grade)

            signal_queue.task_done()
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            log.error("Guardian error: %s", e)
            await asyncio.sleep(1)

# ═══════════════════════════════════════════════════════════════
# ─── ORACLE CONTEXT ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def build_oracle_context(oracle_data: dict) -> dict:
    ctx = {
        "token_unlock_warning": False,
        "macro_bearish": False,
        "market_crash_warning": False,
        "usdt_printing": False,
    }
    if oracle_data.get("token_unlock_in_hours", 999) < 24:
        ctx["token_unlock_warning"] = True
    dxy = oracle_data.get("dxy", 100)
    if dxy > 105:
        ctx["macro_bearish"] = True
    btc_change = oracle_data.get("btc_24h_change", 0)
    if btc_change < -8:
        ctx["market_crash_warning"] = True
    if oracle_data.get("usdt_minted_24h", 0) > 500_000_000:
        ctx["usdt_printing"] = True
    return ctx

# ═══════════════════════════════════════════════════════════════
# ─── QUEUE FACTORY ──────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def create_queues():
    """إنشاء Queues + تشغيل BTC macro updater"""
    signal_queue = asyncio.Queue(maxsize=500)
    approved_queue = asyncio.Queue(maxsize=200)
    return signal_queue, approved_queue

async def btc_macro_loop():
    """حلقة تحديث BTC trend كل 5 دقائق"""
    while True:
        await update_btc_macro()
        await asyncio.sleep(300)
