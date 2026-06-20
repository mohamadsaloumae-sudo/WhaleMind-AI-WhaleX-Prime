"""
WhaleMind Multi-Timeframe Confluence Engine
═══════════════════════════════════════════════════════════════════
فحص 6 إطارات زمنية + 8 مؤشرات في كل إطار = 48 نقطة فحص
يحسب درجة التوافق (Confluence Score)

الإطارات: 5m, 15m, 1H, 4H, 1D, 1W
المؤشرات لكل إطار:
1. EMA Cross (9 vs 21)
2. RSI position
3. MACD direction
4. Bollinger position
5. ADX strength
6. Volume trend
7. Price action (last 3 candles)
8. Support/Resistance proximity
"""

import asyncio
import httpx
import logging
import math
import statistics
from typing import Optional, Dict, List
from dataclasses import dataclass, field

log = logging.getLogger("mtf_confluence")

BINANCE_FAPI = "https://fapi.binance.com/fapi/v1"

TIMEFRAMES = ["5m", "15m", "1h", "4h", "1d", "1w"]
TF_WEIGHTS = {  # وزن كل إطار في القرار
    "5m": 0.5,    # خفيف (للتوقيت الدقيق)
    "15m": 1.0,
    "1h": 1.5,
    "4h": 2.0,    # ثقيل
    "1d": 2.5,    # الأهم
    "1w": 1.5,
}


@dataclass
class TimeframeAnalysis:
    """تحليل إطار زمني واحد"""
    timeframe: str
    bullish_score: int = 0  # 0-8 (عدد المؤشرات الصاعدة)
    bearish_score: int = 0
    direction: str = "NEUTRAL"  # BULLISH / BEARISH / NEUTRAL
    strength: float = 0.0  # 0-1
    
    # تفاصيل المؤشرات
    ema_cross: str = "NEUTRAL"
    rsi_position: str = "NEUTRAL"  # OVERSOLD / NORMAL / OVERBOUGHT
    rsi_value: float = 50.0
    macd_direction: str = "NEUTRAL"
    bb_position: str = "MIDDLE"  # LOWER / MIDDLE / UPPER
    adx_strength: str = "WEAK"   # WEAK / MODERATE / STRONG
    adx_value: float = 0.0
    volume_trend: str = "NEUTRAL"
    candle_pattern: str = "NEUTRAL"
    sr_proximity: str = "NONE"   # NEAR_SUPPORT / NEAR_RESISTANCE / NONE


@dataclass
class MTFResult:
    """النتيجة الشاملة"""
    symbol: str
    overall_direction: str = "NEUTRAL"
    overall_score: float = 0.0  # -1 to +1
    confluence_pct: float = 0.0  # نسبة التوافق %
    confidence: float = 0.0
    
    bullish_weighted: float = 0.0
    bearish_weighted: float = 0.0
    
    timeframes: Dict[str, TimeframeAnalysis] = field(default_factory=dict)
    
    safe_for_long: bool = True
    safe_for_short: bool = True
    rejection_reason: str = ""


# ═══════════════════════════════════════════════════════════════
# ─── INDICATOR CALCULATIONS ───────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def calc_ema(values: List[float], period: int) -> List[float]:
    if len(values) < period:
        return values[:]
    ema = [sum(values[:period]) / period]
    multiplier = 2 / (period + 1)
    for v in values[period:]:
        ema.append((v - ema[-1]) * multiplier + ema[-1])
    # padding
    return [None] * (period - 1) + ema


def calc_rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(0, diff))
        losses.append(abs(min(0, diff)))
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calc_macd(closes: List[float]) -> tuple[float, float, float]:
    """returns (macd, signal, histogram)"""
    if len(closes) < 35:
        return 0.0, 0.0, 0.0
    
    ema12 = calc_ema(closes, 12)
    ema26 = calc_ema(closes, 26)
    
    macd_line = []
    for i in range(len(closes)):
        if ema12[i] is not None and ema26[i] is not None:
            macd_line.append(ema12[i] - ema26[i])
    
    if len(macd_line) < 9:
        return 0.0, 0.0, 0.0
    
    signal = calc_ema(macd_line, 9)
    
    last_macd = macd_line[-1]
    last_signal = signal[-1] if signal[-1] is not None else 0
    histogram = last_macd - last_signal
    
    return last_macd, last_signal, histogram


def calc_bollinger(closes: List[float], period: int = 20, std_dev: float = 2.0) -> tuple[float, float, float]:
    """returns (upper, middle, lower)"""
    if len(closes) < period:
        return 0, 0, 0
    
    recent = closes[-period:]
    middle = sum(recent) / period
    variance = sum((x - middle) ** 2 for x in recent) / period
    std = math.sqrt(variance)
    
    return middle + std_dev * std, middle, middle - std_dev * std


def calc_adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    """Average Directional Index - يقيس قوة الاتجاه"""
    if len(closes) < period + 1:
        return 0.0
    
    tr_list = []
    plus_dm = []
    minus_dm = []
    
    for i in range(1, len(closes)):
        h = highs[i]
        l = lows[i]
        prev_h = highs[i-1]
        prev_l = lows[i-1]
        prev_c = closes[i-1]
        
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        tr_list.append(tr)
        
        up_move = h - prev_h
        down_move = prev_l - l
        
        plus_dm.append(max(up_move, 0) if up_move > down_move else 0)
        minus_dm.append(max(down_move, 0) if down_move > up_move else 0)
    
    if len(tr_list) < period:
        return 0.0
    
    atr = sum(tr_list[:period]) / period
    plus_di_smooth = sum(plus_dm[:period]) / period
    minus_di_smooth = sum(minus_dm[:period]) / period
    
    if atr == 0:
        return 0.0
    
    plus_di = (plus_di_smooth / atr) * 100
    minus_di = (minus_di_smooth / atr) * 100
    
    if (plus_di + minus_di) == 0:
        return 0.0
    
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
    return dx


# ═══════════════════════════════════════════════════════════════
# ─── FETCHING ─────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def fetch_klines(symbol: str, interval: str, limit: int = 100) -> Optional[List[list]]:
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                f"{BINANCE_FAPI}/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit}
            )
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        log.warning("fetch_klines %s %s: %s", symbol, interval, e)
    return None


# ═══════════════════════════════════════════════════════════════
# ─── TIMEFRAME ANALYSIS ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def analyze_timeframe(klines: List[list], tf: str) -> TimeframeAnalysis:
    """تحليل إطار زمني واحد بـ 8 مؤشرات"""
    result = TimeframeAnalysis(timeframe=tf)
    
    if len(klines) < 50:
        return result
    
    opens = [float(k[1]) for k in klines]
    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    closes = [float(k[4]) for k in klines]
    volumes = [float(k[5]) for k in klines]
    
    current_price = closes[-1]
    bullish = 0
    bearish = 0
    
    # ═══ 1. EMA Cross (9 vs 21) ═══
    ema9 = calc_ema(closes, 9)
    ema21 = calc_ema(closes, 21)
    if ema9[-1] and ema21[-1]:
        if ema9[-1] > ema21[-1] and current_price > ema9[-1]:
            result.ema_cross = "BULLISH"
            bullish += 1
        elif ema9[-1] < ema21[-1] and current_price < ema9[-1]:
            result.ema_cross = "BEARISH"
            bearish += 1
    
    # ═══ 2. RSI ═══
    rsi = calc_rsi(closes, 14)
    result.rsi_value = round(rsi, 2)
    if rsi > 70:
        result.rsi_position = "OVERBOUGHT"
        bearish += 1
    elif rsi < 30:
        result.rsi_position = "OVERSOLD"
        bullish += 1
    elif 50 < rsi <= 70:
        result.rsi_position = "BULLISH"
        bullish += 1
    elif 30 <= rsi < 50:
        result.rsi_position = "BEARISH"
        bearish += 1
    
    # ═══ 3. MACD ═══
    macd_v, signal_v, hist = calc_macd(closes)
    if hist > 0 and macd_v > signal_v:
        result.macd_direction = "BULLISH"
        bullish += 1
    elif hist < 0 and macd_v < signal_v:
        result.macd_direction = "BEARISH"
        bearish += 1
    
    # ═══ 4. Bollinger Bands ═══
    bb_up, bb_mid, bb_low = calc_bollinger(closes)
    if bb_up > 0:
        if current_price >= bb_up * 0.99:
            result.bb_position = "UPPER"
            bearish += 1  # قرب القمة = ضغط بيعي
        elif current_price <= bb_low * 1.01:
            result.bb_position = "LOWER"
            bullish += 1  # قرب القاع = ضغط شرائي
        elif current_price > bb_mid:
            result.bb_position = "UPPER_HALF"
            bullish += 0.5
        else:
            result.bb_position = "LOWER_HALF"
            bearish += 0.5
    
    # ═══ 5. ADX (قوة الاتجاه) ═══
    adx = calc_adx(highs, lows, closes)
    result.adx_value = round(adx, 2)
    if adx > 40:
        result.adx_strength = "STRONG"
        # نضيف للاتجاه الموجود
        if bullish > bearish:
            bullish += 1
        elif bearish > bullish:
            bearish += 1
    elif adx > 25:
        result.adx_strength = "MODERATE"
    else:
        result.adx_strength = "WEAK"
    
    # ═══ 6. Volume Trend ═══
    recent_vol = statistics.mean(volumes[-5:])
    older_vol = statistics.mean(volumes[-25:-5])
    if recent_vol > older_vol * 1.3:
        result.volume_trend = "INCREASING"
        # نضيف للاتجاه الموجود
        if bullish > bearish:
            bullish += 1
        elif bearish > bullish:
            bearish += 1
    elif recent_vol < older_vol * 0.7:
        result.volume_trend = "DECREASING"
    
    # ═══ 7. Price Action (آخر 3 شموع) ═══
    last3 = closes[-3:]
    bullish_candles = sum(1 for i in range(len(last3)) if last3[i] > opens[-3+i])
    if bullish_candles == 3:
        result.candle_pattern = "STRONG_BULLISH"
        bullish += 1
    elif bullish_candles == 0:
        result.candle_pattern = "STRONG_BEARISH"
        bearish += 1
    elif bullish_candles == 2:
        result.candle_pattern = "BULLISH"
        bullish += 0.5
    elif bullish_candles == 1:
        result.candle_pattern = "BEARISH"
        bearish += 0.5
    
    # ═══ 8. Support/Resistance Proximity ═══
    # نحدد أقرب S/R من آخر 50 شمعة
    resistance = max(highs[-50:-1])
    support = min(lows[-50:-1])
    range_size = resistance - support
    
    if range_size > 0:
        dist_to_res = (resistance - current_price) / range_size
        dist_to_sup = (current_price - support) / range_size
        
        if dist_to_res < 0.05:
            result.sr_proximity = "NEAR_RESISTANCE"
            bearish += 1
        elif dist_to_sup < 0.05:
            result.sr_proximity = "NEAR_SUPPORT"
            bullish += 1
    
    # ═══ Final Decision ═══
    result.bullish_score = int(bullish)
    result.bearish_score = int(bearish)
    
    total = bullish + bearish
    if total == 0:
        result.direction = "NEUTRAL"
        result.strength = 0
    elif bullish > bearish:
        result.direction = "BULLISH"
        result.strength = bullish / 8.0
    elif bearish > bullish:
        result.direction = "BEARISH"
        result.strength = bearish / 8.0
    else:
        result.direction = "NEUTRAL"
        result.strength = 0
    
    return result


# ═══════════════════════════════════════════════════════════════
# ─── MTF CONFLUENCE ──────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def analyze_mtf(symbol: str) -> Optional[MTFResult]:
    """التحليل الشامل عبر 6 إطارات زمنية"""
    result = MTFResult(symbol=symbol)
    
    # جلب كل الإطارات بالتوازي
    tasks = {tf: fetch_klines(symbol, tf, 100) for tf in TIMEFRAMES}
    klines_data = {tf: await task for tf, task in tasks.items()}
    
    # تحليل كل إطار
    for tf in TIMEFRAMES:
        klines = klines_data.get(tf)
        if not klines or len(klines) < 50:
            log.warning("%s %s: insufficient data", symbol, tf)
            result.timeframes[tf] = TimeframeAnalysis(timeframe=tf)
            continue
        result.timeframes[tf] = analyze_timeframe(klines, tf)
    
    # حساب النتيجة المرجحة
    total_weight = 0
    bullish_weighted = 0
    bearish_weighted = 0
    
    for tf, analysis in result.timeframes.items():
        weight = TF_WEIGHTS.get(tf, 1.0)
        total_weight += weight
        
        if analysis.direction == "BULLISH":
            bullish_weighted += weight * analysis.strength
        elif analysis.direction == "BEARISH":
            bearish_weighted += weight * analysis.strength
    
    if total_weight == 0:
        return result
    
    result.bullish_weighted = round(bullish_weighted, 3)
    result.bearish_weighted = round(bearish_weighted, 3)
    
    # النتيجة النهائية
    net = bullish_weighted - bearish_weighted
    max_possible = total_weight  # max value if all timeframes 100% bullish
    
    result.overall_score = round(net / max_possible, 3)
    
    # درجة التوافق (% الإطارات المتفقة)
    bullish_tfs = sum(1 for a in result.timeframes.values() if a.direction == "BULLISH")
    bearish_tfs = sum(1 for a in result.timeframes.values() if a.direction == "BEARISH")
    neutral_tfs = sum(1 for a in result.timeframes.values() if a.direction == "NEUTRAL")
    total_tfs = len(result.timeframes)
    
    if result.overall_score > 0.15:
        result.overall_direction = "BULLISH"
        result.confluence_pct = round((bullish_tfs / total_tfs) * 100, 1)
    elif result.overall_score < -0.15:
        result.overall_direction = "BEARISH"
        result.confluence_pct = round((bearish_tfs / total_tfs) * 100, 1)
    else:
        result.overall_direction = "NEUTRAL"
        result.confluence_pct = round((neutral_tfs / total_tfs) * 100, 1)
    
    result.confidence = round(abs(result.overall_score), 3)
    
    # Verdict
    result.safe_for_long = result.overall_score > -0.2
    result.safe_for_short = result.overall_score < 0.2
    
    reasons = []
    if not result.safe_for_long:
        reasons.append(f"MTF Score معاكس لـ LONG ({result.overall_score:+.2f})")
    if not result.safe_for_short:
        reasons.append(f"MTF Score معاكس لـ SHORT ({result.overall_score:+.2f})")
    result.rejection_reason = " | ".join(reasons)
    
    return result


# ═══════════════════════════════════════════════════════════════
# ─── INTEGRATION ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def validate_signal_with_mtf(symbol: str, direction: str) -> tuple[bool, str, dict]:
    """
    يتحقق من إشارة عبر 6 إطارات زمنية
    
    Args:
        symbol: العملة
        direction: "LONG" أو "SHORT"
    
    Returns:
        (approved, reason, details)
    """
    result = await analyze_mtf(symbol)
    if not result:
        return False, "فشل MTF analysis", {}
    
    if direction == "LONG":
        if result.overall_direction == "BEARISH" and result.confidence > 0.3:
            return False, f"MTF يعارض LONG (BEARISH {result.confidence:.0%})", _to_dict(result)
        if not result.safe_for_long:
            return False, result.rejection_reason, _to_dict(result)
    elif direction == "SHORT":
        if result.overall_direction == "BULLISH" and result.confidence > 0.3:
            return False, f"MTF يعارض SHORT (BULLISH {result.confidence:.0%})", _to_dict(result)
        if not result.safe_for_short:
            return False, result.rejection_reason, _to_dict(result)
    
    return True, f"✅ MTF {result.confluence_pct:.0f}% confluence", _to_dict(result)


def _to_dict(r: MTFResult) -> dict:
    return {
        "overall_direction": r.overall_direction,
        "overall_score": r.overall_score,
        "confluence_pct": r.confluence_pct,
        "confidence": r.confidence,
        "timeframes": {
            tf: {
                "direction": a.direction,
                "strength": a.strength,
                "rsi": a.rsi_value,
                "adx": a.adx_value,
            }
            for tf, a in r.timeframes.items()
        }
    }


# ═══════════════════════════════════════════════════════════════
# ─── CLI ──────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def cli_test():
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    
    print(f"\n🔍 MTF Analysis: {symbol}\n")
    
    result = await analyze_mtf(symbol)
    if not result:
        print("❌ Failed")
        return
    
    print(f"═══ Multi-Timeframe Confluence ═══")
    print(f"Overall: {result.overall_direction} (score {result.overall_score:+.3f})")
    print(f"Confluence: {result.confluence_pct:.0f}%")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Bullish weighted: {result.bullish_weighted:.2f}")
    print(f"Bearish weighted: {result.bearish_weighted:.2f}")
    
    print(f"\n═══ Per Timeframe ═══")
    for tf in TIMEFRAMES:
        a = result.timeframes.get(tf)
        if not a: continue
        arrow = "🟢" if a.direction == "BULLISH" else ("🔴" if a.direction == "BEARISH" else "⚪")
        print(f"  {arrow} {tf:4s} | {a.direction:8s} | strength={a.strength:.0%} | RSI={a.rsi_value:.0f} | ADX={a.adx_value:.0f}")
        print(f"        EMA: {a.ema_cross:8s} | MACD: {a.macd_direction:8s} | BB: {a.bb_position:12s} | Vol: {a.volume_trend}")
        print(f"        Candles: {a.candle_pattern:15s} | S/R: {a.sr_proximity}")
    
    print(f"\n═══ Verdict ═══")
    print(f"  Safe for LONG:  {'✅' if result.safe_for_long else '❌'}")
    print(f"  Safe for SHORT: {'✅' if result.safe_for_short else '❌'}")
    if result.rejection_reason:
        print(f"  Reason: {result.rejection_reason}")


if __name__ == "__main__":
    asyncio.run(cli_test())
