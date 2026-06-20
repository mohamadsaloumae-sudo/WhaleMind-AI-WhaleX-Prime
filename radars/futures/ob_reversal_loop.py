"""
WhaleMind OB Reversal Loop
═══════════════════════════════════════════════════════════════════
المسار المستقل لإشارات انعكاس Order Book

يعمل بالتوازي مع Predator:
- يفحص كل العملات الآمنة كل دورة
- عند اكتشاف انعكاس مؤكد + BTC alignment → إشارة فورية
- يبني Signal كاملة (SL/TP محسوبة من ATR) ويضعها في approved_queue
"""

import asyncio
import logging
import time
import httpx
from typing import Optional

from quant_engine.ob_reversal_detector import detect_ob_reversal, OBReversalSignal

log = logging.getLogger("ob_reversal_loop")

BINANCE_FAPI = "https://fapi.binance.com/fapi/v1"

# ─── إعدادات ────────────────────────────────────────────────────
SCAN_INTERVAL = 300        # كل 5 دقائق نفحص الـ44
COOLDOWN_PER_SYMBOL = 1800 # نفس العملة لا تُفحص قبل 30 دقيقة
MIN_CONFIDENCE = 0.65      # Grade B+
LAST_OB_SIGNAL = {}        # symbol → timestamp


# ═══════════════════════════════════════════════════════════════
# ─── ATR Calculation ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def calc_atr_15m(symbol: str, period: int = 14) -> float:
    """يحسب ATR من شموع 15m — لتحديد SL/TP الديناميكي"""
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                f"{BINANCE_FAPI}/klines",
                params={"symbol": symbol, "interval": "15m", "limit": period + 5}
            )
            if r.status_code != 200:
                return 0.0
            klines = r.json()
        
        if len(klines) < period:
            return 0.0
        
        trs = []
        for i in range(1, len(klines)):
            high = float(klines[i][2])
            low = float(klines[i][3])
            prev_close = float(klines[i-1][4])
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        
        return sum(trs[-period:]) / period
    except Exception as e:
        log.debug("calc_atr %s: %s", symbol, e)
        return 0.0


async def get_current_price(symbol: str) -> Optional[float]:
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{BINANCE_FAPI}/ticker/price",
                           params={"symbol": symbol})
            if r.status_code == 200:
                return float(r.json()["price"])
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════
# ─── Signal Builder ────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def build_signal_from_ob(reversal: OBReversalSignal):
    """
    يبني Signal كاملة من OBReversalSignal
    SL = 1.5x ATR
    TP1/TP2/TP3 = 1x/2x/3x ATR (R:R 1:1.33, 1:2.33, 1:3.67 مثل Predator)
    """
    from radars.futures.engine import Signal
    
    price = await get_current_price(reversal.symbol)
    if not price:
        return None
    
    # فحص الموقع: منع LONG في القمة و SHORT في القاع (سيولة النهاية)
    try:
        from radars.futures.engine import fetch_klines_async, range_position, rsi as rsi_calc, stoch_rsi
        _c = await fetch_klines_async(reversal.symbol, "15m", 100)
        if len(_c) >= 60:
            _cl = [x.close for x in _c]
            _pos = range_position(_c, 20)
            _rsi = rsi_calc(_cl)
            _sk, _sd = stoch_rsi(_cl)
            _long = reversal.direction == "LONG"
            if _long and (_pos > 0.65 or _rsi > 65 or (_sk > 90 and _sd > 90)):
                log.info("OB rejected: %s LONG at top (pos=%.0f RSI=%.0f) - end liquidity", reversal.symbol, _pos*100, _rsi)
                return None
            if not _long and (_pos < 0.35 or _rsi < 35 or (_sk < 10 and _sd < 10)):
                log.info("OB rejected: %s SHORT at bottom (pos=%.0f RSI=%.0f) - end liquidity", reversal.symbol, _pos*100, _rsi)
                return None
    except Exception as e:
        log.debug("OB pos check: %s", e)

    atr = await calc_atr_15m(reversal.symbol)
    if atr == 0:
        # fallback: نستخدم 0.5% من السعر
        atr = price * 0.005
    
    # SL/TP
    is_long = reversal.direction == "LONG"
    sl_dist = atr * 1.5
    tp1_dist = atr * 1.5 * 1.33   # R:R 1:1.33
    tp2_dist = atr * 1.5 * 2.33
    tp3_dist = atr * 1.5 * 3.67
    
    if is_long:
        sl = price - sl_dist
        tp1 = price + tp1_dist
        tp2 = price + tp2_dist
        tp3 = price + tp3_dist
    else:
        sl = price + sl_dist
        tp1 = price - tp1_dist
        tp2 = price - tp2_dist
        tp3 = price - tp3_dist
    
    # الرافعة حسب Tier (نقرأها من Profile DB)
    leverage = 5  # default
    try:
        import sqlite3
        conn = sqlite3.connect("/opt/whalex/coin_profiles.db")
        row = conn.execute(
            "SELECT recommended_leverage, tier FROM coin_profiles WHERE symbol=?",
            (reversal.symbol,)
        ).fetchone()
        conn.close()
        if row:
            leverage = row[0]
            profile_tier = row[1]
            tier_letter = {1: "S", 2: "A", 3: "B"}.get(profile_tier, "B")
    except Exception:
        tier_letter = "B"
    
    # الـ confidence (نطبق modifier من BTC alignment)
    confidence_pct = reversal.confidence * 100
    
    # حساب الـ score (محاكاة لـ Predator)
    score = 6.0 + (reversal.confidence * 2.5)  # 6.0 → 8.5
    
    # strategies description
    strategies = f"🐋 OB Reversal • {reversal.persistence_pct:.0f}% persistence"
    if reversal.wall_confirmed:
        strategies += " • Wall Confirmed"
    if reversal.btc_alignment:
        if reversal.btc_alignment.alignment == "CONFIRMED":
            strategies += f" • BTC ✅ {reversal.btc_alignment.btc_direction}"
        elif reversal.btc_alignment.alignment == "DIVERGENT":
            strategies += " • ⚠️ BTC Divergent"
    
    # جلب Funding/OI الحقيقية (كان OB أعمى عنها — تظهر 0%)
    try:
        from radars.futures.engine import get_funding_rate, get_oi_change
        _ob_funding = await get_funding_rate(reversal.symbol)
        _ob_oi = await get_oi_change(reversal.symbol)
    except Exception:
        _ob_funding, _ob_oi = 0.0, 0.0

    sig = Signal(
        symbol=reversal.symbol,
        direction=reversal.direction,
        grade=reversal.grade,
        score=round(score, 1),
        confidence=round(confidence_pct, 1),
        entry=round(price, 8),
        sl=round(sl, 8),
        tp1=round(tp1, 8),
        tp2=round(tp2, 8),
        tp3=round(tp3, 8),
        leverage=leverage,
        strategies=strategies,
        radar_type="futures",
        tier=tier_letter,
        accuracy=75.0,  # سيُحدّث لاحقاً من ML
        strategy_count=1,
        funding_rate=_ob_funding,
        open_interest_change=_ob_oi,
        rr_tp1=1.33,
        rr_tp2=2.33,
        rr_tp3=3.67,
        mtf_15m="OB_REVERSAL",
        mtf_1h="OB_REVERSAL",
        mtf_4h="OB_REVERSAL",
    )
    
    # BTC trend
    if reversal.btc_alignment:
        sig.btc_trend = reversal.btc_alignment.btc_direction
    
    return sig


# ═══════════════════════════════════════════════════════════════
# ─── MAIN LOOP ────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def ob_reversal_loop(approved_queue: asyncio.Queue):
    """
    الحلقة الرئيسية — مسار مستقل للإشارات
    
    آلية العمل:
    1. كل 5 دقائق نفحص الـ44 عملة
    2. لكل عملة: لقطة سريعة → إذا انقلاب → تأكيد كامل
    3. عند إشارة مؤكدة → بناء Signal → approved_queue
    """
    log.info("🐋 OB Reversal Loop started")
    
    # نمنح وقتاً للنظام ليستقر بعد التشغيل
    await asyncio.sleep(30)
    
    while True:
        try:
            # جلب العملات الآمنة
            import sqlite3
            conn = sqlite3.connect("/opt/whalex/coin_profiles.db")
            rows = conn.execute(
                "SELECT symbol FROM coin_profiles "
                "WHERE safe_to_trade=1 AND tier <= 3 "
                "ORDER BY tier ASC"
            ).fetchall()
            conn.close()
            
            symbols = [r[0] for r in rows]
            log.info("🔍 OB Reversal scan: %d symbols", len(symbols))
            
            from quant_engine.ob_reversal_detector import quick_scan, detect_ob_reversal
            
            now = int(time.time())
            
            # مرحلة 1: فحص سريع (لقطة واحدة لكل عملة)
            candidates = []
            for symbol in symbols:
                # cooldown
                if now - LAST_OB_SIGNAL.get(symbol, 0) < COOLDOWN_PER_SYMBOL:
                    continue
                
                try:
                    direction = await quick_scan(symbol)
                    if direction:
                        candidates.append((symbol, direction))
                        log.info("  🎯 candidate: %s %s", symbol, direction)
                except Exception as e:
                    log.debug("quick_scan %s: %s", symbol, e)
                
                # rate limit
                await asyncio.sleep(0.2)
            
            log.info("🔬 Confirming %d candidates...", len(candidates))
            
            # مرحلة 2: تأكيد كامل لكل candidate (سيأخذ وقتاً)
            for symbol, _ in candidates:
                try:
                    result = await detect_ob_reversal(symbol, check_btc=True)
                    
                    if result.detected and result.confidence >= MIN_CONFIDENCE:
                        # فحص السيولة الحية قبل البناء
                        from quant_engine.liquidity_health import validate_liquidity
                        liq_ok, liq_reason, liq_data = await validate_liquidity(symbol)
                        if not liq_ok:
                            log.info("🚫 OB Signal blocked (liquidity): %s %s — %s", 
                                     symbol, result.direction, liq_reason)
                            continue
                        if liq_data.get("status") == "YELLOW":
                            log.warning("⚠️ OB Signal with liquidity warning: %s — %s",
                                       symbol, liq_reason)
                        # بناء Signal
                        sig = await build_signal_from_ob(result)
                        if sig:
                            await approved_queue.put(sig)
                            LAST_OB_SIGNAL[symbol] = now
                            log.info(
                                "✅ OB Signal queued: %s %s Grade %s (conf %.0f%%)",
                                sig.symbol, sig.direction, sig.grade, sig.confidence
                            )
                except Exception as e:
                    log.error("OB confirm error %s: %s", symbol, e)
            
            # ننتظر للدورة التالية
            await asyncio.sleep(SCAN_INTERVAL)
        
        except Exception as e:
            log.error("ob_reversal_loop error: %s", e)
            await asyncio.sleep(60)
