"""
WhaleMind Advanced Delta Engine
═══════════════════════════════════════════════════════════════════
تحليل تدفق الأوامر (Order Flow) بعمق احترافي

الميزات:
✅ Cumulative Volume Delta (CVD) عبر 4 إطارات
✅ Delta Divergence Detection (السعر يصعد لكن Delta يهبط)
✅ Smart Money Delta (الأوامر الضخمة فقط)
✅ Aggressive vs Passive Delta
✅ Absorption Detection (حجم عالٍ بدون حركة سعر)
✅ Exhaustion Detection (delta يتباطأ في القمة/القاع)
"""

import asyncio
import httpx
import logging
import statistics
from typing import Optional, Dict, List
from dataclasses import dataclass, field

log = logging.getLogger("delta_engine")

BINANCE_FAPI = "https://fapi.binance.com/fapi/v1"

# إطارات الفحص
DELTA_TIMEFRAMES = ["5m", "15m", "1h", "4h"]
DELTA_WEIGHTS = {
    "5m": 0.5,
    "15m": 1.0,
    "1h": 2.0,
    "4h": 2.5,
}

# عتبة Smart Money (طلبات > $50K)
SMART_MONEY_THRESHOLD_USDT = 50_000


@dataclass
class DeltaSnapshot:
    """تحليل Delta لإطار زمني واحد"""
    timeframe: str
    
    # Basic CVD
    cvd: float = 0.0
    cvd_change_pct: float = 0.0  # تغير CVD آخر 5 شموع
    
    # Smart Money
    smart_money_delta: float = 0.0
    smart_money_trades: int = 0
    
    # Aggressive vs Passive
    aggressive_buys: float = 0.0
    aggressive_sells: float = 0.0
    
    # Divergence
    price_change_pct: float = 0.0
    delta_change_pct: float = 0.0
    divergence_detected: bool = False
    divergence_type: str = ""  # bullish_div / bearish_div
    
    # Absorption
    absorption_detected: bool = False
    absorption_side: str = ""  # bid / ask
    
    # Exhaustion
    exhaustion_detected: bool = False
    exhaustion_side: str = ""
    
    # Verdict
    direction: str = "NEUTRAL"  # BULLISH / BEARISH / NEUTRAL
    strength: float = 0.0


@dataclass
class DeltaResult:
    """النتيجة الشاملة"""
    symbol: str
    
    # Per-timeframe snapshots
    timeframes: Dict[str, DeltaSnapshot] = field(default_factory=dict)
    
    # Overall
    overall_direction: str = "NEUTRAL"
    overall_score: float = 0.0  # -1 to +1
    confidence: float = 0.0
    
    # Critical signals
    has_divergence: bool = False
    divergence_tfs: List[str] = field(default_factory=list)
    has_absorption: bool = False
    has_exhaustion: bool = False
    
    # Smart Money
    smart_money_direction: str = "NEUTRAL"  # BUYING / SELLING / NEUTRAL
    smart_money_strength: float = 0.0
    
    # Verdict
    safe_for_long: bool = True
    safe_for_short: bool = True
    rejection_reason: str = ""


# ═══════════════════════════════════════════════════════════════
# ─── FETCHING ─────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def fetch_klines(symbol: str, interval: str, limit: int = 50) -> Optional[List[list]]:
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


async def fetch_aggregated_trades(symbol: str, limit: int = 1000) -> Optional[List[dict]]:
    """يجلب آخر 1000 صفقة مجمعة (للـ Smart Money detection)"""
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                f"{BINANCE_FAPI}/aggTrades",
                params={"symbol": symbol, "limit": limit}
            )
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        log.warning("fetch_aggTrades %s: %s", symbol, e)
    return None


# ═══════════════════════════════════════════════════════════════
# ─── DELTA CALCULATIONS ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def calculate_cvd(klines: List[list]) -> tuple[float, List[float]]:
    """
    حساب Cumulative Volume Delta من شموع Binance
    
    Delta لكل شمعة = taker_buy_volume - taker_sell_volume
    (Binance يعطي taker_buy_quote_volume)
    
    Returns: (total_cvd, cumulative_list)
    """
    cumulative = []
    total = 0.0
    
    for k in klines:
        # k[5] = base volume, k[7] = quote volume
        # k[9] = taker buy base volume, k[10] = taker buy quote volume
        total_quote = float(k[7])
        buy_quote = float(k[10])
        sell_quote = total_quote - buy_quote
        
        delta = buy_quote - sell_quote
        total += delta
        cumulative.append(total)
    
    return total, cumulative


def detect_divergence(klines: List[list], cumulative_cvd: List[float]) -> tuple[bool, str]:
    """
    يكشف Divergence بين السعر و CVD
    
    Bullish Divergence: السعر يهبط لكن CVD يصعد → انعكاس صاعد قادم
    Bearish Divergence: السعر يصعد لكن CVD يهبط → انعكاس هابط قادم
    """
    if len(klines) < 20 or len(cumulative_cvd) < 20:
        return False, ""
    
    # نقارن آخر 10 شموع مع 10 قبلها
    recent_closes = [float(k[4]) for k in klines[-10:]]
    older_closes = [float(k[4]) for k in klines[-20:-10]]
    
    recent_cvd = cumulative_cvd[-10:]
    older_cvd = cumulative_cvd[-20:-10]
    
    recent_price_avg = statistics.mean(recent_closes)
    older_price_avg = statistics.mean(older_closes)
    recent_cvd_avg = statistics.mean(recent_cvd)
    older_cvd_avg = statistics.mean(older_cvd)
    
    price_change = (recent_price_avg - older_price_avg) / older_price_avg if older_price_avg else 0
    
    if older_cvd_avg != 0:
        cvd_change = (recent_cvd_avg - older_cvd_avg) / abs(older_cvd_avg)
    else:
        cvd_change = 0
    
    # Bullish Divergence
    if price_change < -0.005 and cvd_change > 0.05:  # سعر -0.5%، cvd +5%
        return True, "bullish_div"
    
    # Bearish Divergence
    if price_change > 0.005 and cvd_change < -0.05:
        return True, "bearish_div"
    
    return False, ""


def detect_absorption(klines: List[list]) -> tuple[bool, str]:
    """
    Absorption: حجم عالٍ بدون حركة سعر كبيرة
    يعني MM يمتص الضغط في اتجاه معاكس
    
    مثال: 
    - شمعة بحجم 5x المتوسط لكن إغلاق قريب من فتح = absorption
    - الـ side يحدد: إذا الشمعة خضراء = absorption على ask (مقاومة)
    """
    if len(klines) < 20:
        return False, ""
    
    volumes = [float(k[7]) for k in klines]  # quote volume
    avg_vol = statistics.mean(volumes[:-3])  # متوسط ما عدا آخر 3 شموع
    
    if avg_vol == 0:
        return False, ""
    
    # نفحص آخر 3 شموع
    for k in klines[-3:]:
        op = float(k[1])
        cl = float(k[4])
        hi = float(k[2])
        lo = float(k[3])
        vol = float(k[7])
        
        if op == 0:
            continue
        
        # حجم > 4x المتوسط
        if vol < avg_vol * 4:
            continue
        
        # الحركة < 30% من range الشمعة
        body = abs(cl - op)
        full_range = hi - lo
        if full_range == 0 or op == 0:
            continue
        
        body_pct = body / full_range
        range_pct = full_range / op * 100
        
        # absorption = حجم كبير لكن حركة محدودة
        if body_pct < 0.3 and range_pct < 1.5:
            # نحدد الجهة
            # إذا الشمعة خضراء → ask absorption (مقاومة)
            # إذا حمراء → bid absorption (دعم)
            if cl > op:
                return True, "ask"  # مقاومة
            else:
                return True, "bid"  # دعم
    
    return False, ""


def detect_exhaustion(klines: List[list], cumulative_cvd: List[float]) -> tuple[bool, str]:
    """
    Exhaustion: Delta يتباطأ في القمة/القاع
    يعني الترند يفقد قوته
    
    Bullish Exhaustion: في قمة، delta يتباطأ → SHORT قادم
    Bearish Exhaustion: في قاع، delta يتسارع → LONG قادم
    """
    if len(klines) < 15 or len(cumulative_cvd) < 15:
        return False, ""
    
    closes = [float(k[4]) for k in klines]
    
    # هل في قمة؟
    recent_high = max(closes[-5:])
    older_high = max(closes[-15:-5])
    is_at_top = recent_high >= older_high * 1.005
    
    # هل في قاع؟
    recent_low = min(closes[-5:])
    older_low = min(closes[-15:-5])
    is_at_bottom = recent_low <= older_low * 0.995
    
    # Delta الأخير
    recent_delta_speed = cumulative_cvd[-1] - cumulative_cvd[-5]
    older_delta_speed = cumulative_cvd[-5] - cumulative_cvd[-10]
    
    if is_at_top:
        # في قمة، نتوقع delta إيجابي قوي
        # إذا الـ delta يتباطأ = exhaustion
        if older_delta_speed > 0 and recent_delta_speed < older_delta_speed * 0.4:
            return True, "bullish"  # السعر صاعد لكن الشراء يضعف
    
    if is_at_bottom:
        if older_delta_speed < 0 and recent_delta_speed > older_delta_speed * 0.4:
            return True, "bearish"  # السعر هابط لكن البيع يضعف
    
    return False, ""


# ═══════════════════════════════════════════════════════════════
# ─── SMART MONEY DETECTION ────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def analyze_smart_money(trades: List[dict], min_size_usdt: float = SMART_MONEY_THRESHOLD_USDT) -> dict:
    """
    يحلل صفقات Smart Money (الأوامر الكبيرة فقط)
    
    Returns:
        {
            "delta_usdt": float,
            "trades_count": int,
            "direction": "BUYING"/"SELLING"/"NEUTRAL",
            "strength": 0-1
        }
    """
    if not trades:
        return {"delta_usdt": 0, "trades_count": 0, "direction": "NEUTRAL", "strength": 0}
    
    smart_buy_usdt = 0
    smart_sell_usdt = 0
    smart_count = 0
    
    for t in trades:
        try:
            price = float(t.get("p", 0))
            qty = float(t.get("q", 0))
            usdt = price * qty
            
            if usdt < min_size_usdt:
                continue
            
            # m=true means maker, false means taker
            # in Binance: m=true → market sell (someone sold to a bid)
            # m=false → market buy (someone bought from an ask)
            is_buyer_maker = t.get("m", False)
            
            if is_buyer_maker:
                # market sell
                smart_sell_usdt += usdt
            else:
                # market buy
                smart_buy_usdt += usdt
            
            smart_count += 1
        except (ValueError, TypeError):
            continue
    
    delta = smart_buy_usdt - smart_sell_usdt
    total = smart_buy_usdt + smart_sell_usdt
    
    if total == 0:
        return {"delta_usdt": 0, "trades_count": smart_count, "direction": "NEUTRAL", "strength": 0}
    
    ratio = abs(delta) / total
    
    if delta > 0 and ratio > 0.15:
        direction = "BUYING"
    elif delta < 0 and ratio > 0.15:
        direction = "SELLING"
    else:
        direction = "NEUTRAL"
    
    return {
        "delta_usdt": round(delta, 2),
        "trades_count": smart_count,
        "direction": direction,
        "strength": round(ratio, 3),
        "buy_volume": round(smart_buy_usdt, 2),
        "sell_volume": round(smart_sell_usdt, 2),
    }


# ═══════════════════════════════════════════════════════════════
# ─── PER-TIMEFRAME ANALYSIS ───────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def analyze_timeframe_delta(klines: List[list], tf: str) -> DeltaSnapshot:
    """تحليل Delta لإطار زمني واحد"""
    snap = DeltaSnapshot(timeframe=tf)
    
    if len(klines) < 20:
        return snap
    
    # CVD
    total_cvd, cumulative_cvd = calculate_cvd(klines)
    snap.cvd = round(total_cvd, 2)
    
    # CVD change (آخر 5 vs ما قبلهم)
    if len(cumulative_cvd) >= 10:
        recent_cvd = cumulative_cvd[-1]
        older_cvd = cumulative_cvd[-6]
        if abs(older_cvd) > 0:
            snap.cvd_change_pct = round(((recent_cvd - older_cvd) / abs(older_cvd)) * 100, 2)
    
    # Price change
    if len(klines) >= 6:
        recent_price = float(klines[-1][4])
        older_price = float(klines[-6][4])
        if older_price > 0:
            snap.price_change_pct = round(((recent_price - older_price) / older_price) * 100, 3)
    
    # Aggressive vs Passive
    buy_vol = sum(float(k[10]) for k in klines[-10:])  # taker buy
    total_vol = sum(float(k[7]) for k in klines[-10:])
    sell_vol = total_vol - buy_vol
    snap.aggressive_buys = round(buy_vol, 2)
    snap.aggressive_sells = round(sell_vol, 2)
    
    # Divergence
    div_detected, div_type = detect_divergence(klines, cumulative_cvd)
    snap.divergence_detected = div_detected
    snap.divergence_type = div_type
    
    # Absorption
    absorb_detected, absorb_side = detect_absorption(klines)
    snap.absorption_detected = absorb_detected
    snap.absorption_side = absorb_side
    
    # Exhaustion
    exhaust_detected, exhaust_side = detect_exhaustion(klines, cumulative_cvd)
    snap.exhaustion_detected = exhaust_detected
    snap.exhaustion_side = exhaust_side
    
    # Direction
    bullish_signals = 0
    bearish_signals = 0
    
    if snap.cvd_change_pct > 5:
        bullish_signals += 1
    elif snap.cvd_change_pct < -5:
        bearish_signals += 1
    
    if div_type == "bullish_div":
        bullish_signals += 2  # divergence قوي
    elif div_type == "bearish_div":
        bearish_signals += 2
    
    if absorb_side == "bid":
        bullish_signals += 1  # دعم
    elif absorb_side == "ask":
        bearish_signals += 1  # مقاومة
    
    if exhaust_side == "bullish":
        bearish_signals += 1  # سيهبط
    elif exhaust_side == "bearish":
        bullish_signals += 1  # سيصعد
    
    if buy_vol > sell_vol * 1.3:
        bullish_signals += 1
    elif sell_vol > buy_vol * 1.3:
        bearish_signals += 1
    
    total = bullish_signals + bearish_signals
    if total == 0:
        snap.direction = "NEUTRAL"
        snap.strength = 0
    elif bullish_signals > bearish_signals:
        snap.direction = "BULLISH"
        snap.strength = bullish_signals / 7.0
    elif bearish_signals > bullish_signals:
        snap.direction = "BEARISH"
        snap.strength = bearish_signals / 7.0
    
    return snap


# ═══════════════════════════════════════════════════════════════
# ─── MAIN ANALYSIS ────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def analyze_delta(symbol: str) -> Optional[DeltaResult]:
    """التحليل الشامل لـ Delta عبر 4 إطارات"""
    result = DeltaResult(symbol=symbol)
    
    # جلب كل الإطارات بالتوازي
    tasks = {tf: fetch_klines(symbol, tf, 50) for tf in DELTA_TIMEFRAMES}
    klines_data = {tf: await task for tf, task in tasks.items()}
    
    # تحليل كل إطار
    for tf in DELTA_TIMEFRAMES:
        klines = klines_data.get(tf)
        if not klines or len(klines) < 20:
            result.timeframes[tf] = DeltaSnapshot(timeframe=tf)
            continue
        result.timeframes[tf] = analyze_timeframe_delta(klines, tf)
    
    # Smart Money analysis
    trades = await fetch_aggregated_trades(symbol, 1000)
    sm = analyze_smart_money(trades or [])
    result.smart_money_direction = sm["direction"]
    result.smart_money_strength = sm["strength"]
    
    # Aggregate scoring
    bullish_weighted = 0.0
    bearish_weighted = 0.0
    total_weight = 0.0
    
    for tf, snap in result.timeframes.items():
        weight = DELTA_WEIGHTS.get(tf, 1.0)
        total_weight += weight
        
        if snap.direction == "BULLISH":
            bullish_weighted += weight * snap.strength
        elif snap.direction == "BEARISH":
            bearish_weighted += weight * snap.strength
        
        # Track critical signals
        if snap.divergence_detected:
            result.has_divergence = True
            result.divergence_tfs.append(tf)
        if snap.absorption_detected:
            result.has_absorption = True
        if snap.exhaustion_detected:
            result.has_exhaustion = True
    
    # Smart Money weight
    if sm["direction"] == "BUYING":
        bullish_weighted += sm["strength"] * 2  # وزن قوي
    elif sm["direction"] == "SELLING":
        bearish_weighted += sm["strength"] * 2
    total_weight += 2
    
    # Overall score
    if total_weight > 0:
        net = bullish_weighted - bearish_weighted
        result.overall_score = round(net / total_weight, 3)
    
    if result.overall_score > 0.15:
        result.overall_direction = "BULLISH"
    elif result.overall_score < -0.15:
        result.overall_direction = "BEARISH"
    else:
        result.overall_direction = "NEUTRAL"
    
    result.confidence = round(abs(result.overall_score), 3)
    
    # Verdict
    result.safe_for_long = result.overall_score > -0.25
    result.safe_for_short = result.overall_score < 0.25
    
    reasons = []
    if not result.safe_for_long:
        reasons.append(f"Delta معاكس لـ LONG ({result.overall_score:+.2f})")
    if not result.safe_for_short:
        reasons.append(f"Delta معاكس لـ SHORT ({result.overall_score:+.2f})")
    
    # Critical warnings
    if result.has_divergence:
        bearish_div_tfs = [tf for tf in result.divergence_tfs 
                          if result.timeframes[tf].divergence_type == "bearish_div"]
        bullish_div_tfs = [tf for tf in result.divergence_tfs 
                          if result.timeframes[tf].divergence_type == "bullish_div"]
        if bearish_div_tfs and len(bearish_div_tfs) >= 2:
            result.safe_for_long = False
            reasons.append(f"Bearish divergence على {','.join(bearish_div_tfs)}")
        if bullish_div_tfs and len(bullish_div_tfs) >= 2:
            result.safe_for_short = False
            reasons.append(f"Bullish divergence على {','.join(bullish_div_tfs)}")
    
    result.rejection_reason = " | ".join(reasons)
    
    return result


# ═══════════════════════════════════════════════════════════════
# ─── INTEGRATION ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def validate_signal_with_delta(symbol: str, direction: str) -> tuple[bool, str, dict]:
    """فلتر Delta للإشارة"""
    result = await analyze_delta(symbol)
    if not result:
        return True, "Delta analysis failed - skipped", {}
    
    if direction == "LONG":
        if not result.safe_for_long:
            return False, result.rejection_reason, _to_dict(result)
        if result.overall_direction == "BEARISH" and result.confidence > 0.3:
            return False, f"Delta BEARISH ({result.confidence:.0%})", _to_dict(result)
    elif direction == "SHORT":
        if not result.safe_for_short:
            return False, result.rejection_reason, _to_dict(result)
        if result.overall_direction == "BULLISH" and result.confidence > 0.3:
            return False, f"Delta BULLISH ({result.confidence:.0%})", _to_dict(result)
    
    msg = f"✅ Delta {result.overall_direction} ({result.overall_score:+.2f})"
    if result.smart_money_direction != "NEUTRAL":
        msg += f" | SM {result.smart_money_direction}"
    return True, msg, _to_dict(result)


def _to_dict(r: DeltaResult) -> dict:
    return {
        "overall_direction": r.overall_direction,
        "overall_score": r.overall_score,
        "confidence": r.confidence,
        "smart_money": r.smart_money_direction,
        "smart_money_strength": r.smart_money_strength,
        "has_divergence": r.has_divergence,
        "has_absorption": r.has_absorption,
        "has_exhaustion": r.has_exhaustion,
        "divergence_tfs": r.divergence_tfs,
    }


# ═══════════════════════════════════════════════════════════════
# ─── CLI ──────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def cli_test():
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    
    print(f"\n🔍 Delta Engine Analysis: {symbol}\n")
    
    result = await analyze_delta(symbol)
    if not result:
        print("❌ Failed")
        return
    
    print(f"═══ Advanced Delta Analysis ═══")
    print(f"Overall: {result.overall_direction} (score {result.overall_score:+.3f})")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"\nSmart Money: {result.smart_money_direction} (strength {result.smart_money_strength:.2%})")
    
    print(f"\n═══ Critical Signals ═══")
    print(f"  Divergence: {'🚨 ' + str(result.divergence_tfs) if result.has_divergence else '✅ None'}")
    print(f"  Absorption: {'🚨 DETECTED' if result.has_absorption else '✅ None'}")
    print(f"  Exhaustion: {'🚨 DETECTED' if result.has_exhaustion else '✅ None'}")
    
    print(f"\n═══ Per Timeframe ═══")
    for tf in DELTA_TIMEFRAMES:
        s = result.timeframes.get(tf)
        if not s: continue
        arrow = "🟢" if s.direction == "BULLISH" else ("🔴" if s.direction == "BEARISH" else "⚪")
        print(f"  {arrow} {tf:4s} | {s.direction:8s} | strength={s.strength:.0%}")
        print(f"        CVD: {s.cvd:,.0f} | change: {s.cvd_change_pct:+.2f}%")
        print(f"        Price change: {s.price_change_pct:+.3f}%")
        if s.divergence_detected:
            print(f"        🚨 Divergence: {s.divergence_type}")
        if s.absorption_detected:
            print(f"        🚨 Absorption ({s.absorption_side})")
        if s.exhaustion_detected:
            print(f"        🚨 Exhaustion ({s.exhaustion_side})")
    
    print(f"\n═══ Verdict ═══")
    print(f"  Safe for LONG:  {'✅' if result.safe_for_long else '❌'}")
    print(f"  Safe for SHORT: {'✅' if result.safe_for_short else '❌'}")
    if result.rejection_reason:
        print(f"  Reason: {result.rejection_reason}")


if __name__ == "__main__":
    asyncio.run(cli_test())
