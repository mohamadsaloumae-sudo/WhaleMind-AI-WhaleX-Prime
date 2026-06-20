"""
WhaleMind Liquidity Health Monitor
═══════════════════════════════════════════════════════════════════
يفحص صحة السيولة الحالية لكل عملة قبل الإشارة

الفكرة:
- profile DB يقيس متوسط 30 يوم (ثابت)
- لكن السيولة تتغير في دقائق!
- نفحص آخر 1h و 24h لنقارن

المؤشرات الـ5:
1. حجم 24h vs avg 30d (Wash Trading detection)
2. عدد الصفقات (Trade Count) — تداول طبيعي vs MM
3. Spread bid/ask — سيولة جافة
4. OB Depth — عمق الكتاب
5. ATR ratio — تقلب شاذ
"""

import asyncio
import httpx
import logging
import statistics
import time
from typing import Optional
from dataclasses import dataclass

log = logging.getLogger("liquidity_health")

BINANCE_FAPI = "https://fapi.binance.com/fapi/v1"

# ─── العتبات (قابلة للضبط) ────────────────────────────────────
VOL_PUMP_THRESHOLD = 3.0      # حجم > 3x المتوسط = مشبوه
VOL_DRY_THRESHOLD = 0.3        # حجم < 30% = جاف
SPREAD_MAX_PCT = 0.30          # spread > 0.30% = مريب
OB_DEPTH_MIN_USDT = 100_000    # < $100K في top 20 = ضحل
ATR_ANOMALY_RATIO = 2.5        # ATR 24h > 2.5x ATR 30d = شاذ
TRADES_PER_MIL_MIN = 50        # أقل من 50 صفقة لكل $1M حجم = MM


@dataclass
class LiquidityReport:
    symbol: str
    timestamp: float
    
    # القياسات
    current_volume_24h: float = 0.0
    avg_volume_30d: float = 0.0
    volume_ratio: float = 0.0
    
    trade_count_24h: int = 0
    trades_per_million: float = 0.0
    
    spread_pct: float = 0.0
    ob_depth_usdt: float = 0.0
    
    atr_24h: float = 0.0
    atr_30d: float = 0.0
    atr_ratio: float = 0.0
    
    # القرار
    healthy: bool = True
    status: str = "GREEN"  # GREEN / YELLOW / RED
    warnings: list = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


# ═══════════════════════════════════════════════════════════════
# ─── DATA FETCHING ────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def fetch_24h_stats(symbol: str) -> Optional[dict]:
    """يجلب إحصاءات 24h: حجم، عدد صفقات، تغيّر سعر"""
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{BINANCE_FAPI}/ticker/24hr",
                           params={"symbol": symbol})
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return None


async def fetch_orderbook_metrics(symbol: str) -> tuple[float, float]:
    """يحسب spread و OB depth"""
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{BINANCE_FAPI}/depth",
                           params={"symbol": symbol, "limit": 20})
            if r.status_code != 200:
                return 0, 0
            d = r.json()
        
        bids = [(float(p), float(q)) for p, q in d["bids"]]
        asks = [(float(p), float(q)) for p, q in d["asks"]]
        if not bids or not asks:
            return 0, 0
        
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        spread_pct = ((best_ask - best_bid) / best_bid) * 100 if best_bid else 0
        
        # depth = top 20 bid + ask
        depth = sum(p * q for p, q in bids) + sum(p * q for p, q in asks)
        
        return round(spread_pct, 4), round(depth, 2)
    except Exception:
        return 0, 0


async def calc_atr_for_period(symbol: str, interval: str, limit: int) -> float:
    """يحسب ATR لفترة معينة"""
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(f"{BINANCE_FAPI}/klines",
                           params={"symbol": symbol, "interval": interval, "limit": limit})
            if r.status_code != 200:
                return 0
            klines = r.json()
        
        if len(klines) < 2:
            return 0
        
        trs = []
        for i in range(1, len(klines)):
            high = float(klines[i][2])
            low = float(klines[i][3])
            prev_close = float(klines[i-1][4])
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        
        return sum(trs) / len(trs) if trs else 0
    except Exception:
        return 0


# ═══════════════════════════════════════════════════════════════
# ─── MAIN ANALYSIS ────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def check_liquidity_health(symbol: str) -> LiquidityReport:
    """
    الفحص الشامل لصحة السيولة
    Returns: LiquidityReport بكل التفاصيل + القرار
    """
    import sqlite3
    
    report = LiquidityReport(symbol=symbol, timestamp=time.time())
    
    # 1. نجلب الـ avg من profile DB
    try:
        conn = sqlite3.connect("/opt/whalex/coin_profiles.db")
        row = conn.execute(
            "SELECT avg_daily_volume FROM coin_profiles WHERE symbol=?",
            (symbol,)
        ).fetchone()
        conn.close()
        if row:
            report.avg_volume_30d = row[0]
    except Exception as e:
        log.debug("DB read %s: %s", symbol, e)
    
    # 2. نجلب البيانات الحية بالتوازي
    stats_task = fetch_24h_stats(symbol)
    ob_task = fetch_orderbook_metrics(symbol)
    atr_24h_task = calc_atr_for_period(symbol, "1h", 24)    # ATR 24 ساعة
    atr_30d_task = calc_atr_for_period(symbol, "1d", 30)   # ATR 30 يوم
    
    stats, (spread, depth), atr_24h, atr_30d = await asyncio.gather(
        stats_task, ob_task, atr_24h_task, atr_30d_task
    )
    
    if not stats:
        report.warnings.append("فشل جلب بيانات 24h")
        report.status = "RED"
        report.healthy = False
        return report
    
    report.current_volume_24h = float(stats.get("quoteVolume", 0))
    report.trade_count_24h = int(stats.get("count", 0))
    report.spread_pct = spread
    report.ob_depth_usdt = depth
    report.atr_24h = atr_24h
    report.atr_30d = atr_30d
    
    # حسابات
    if report.avg_volume_30d > 0:
        report.volume_ratio = report.current_volume_24h / report.avg_volume_30d
    
    if report.current_volume_24h > 0:
        report.trades_per_million = report.trade_count_24h / (report.current_volume_24h / 1_000_000)
    
    if report.atr_30d > 0:
        report.atr_ratio = report.atr_24h / report.atr_30d
    
    # ═══════════════════════════════════════════════════════════
    # ─── القرارات ─────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════
    
    red_flags = 0
    yellow_flags = 0
    
    # 1. حجم 24h
    if report.volume_ratio > VOL_PUMP_THRESHOLD:
        report.warnings.append(f"🚨 حجم مضخم ×{report.volume_ratio:.1f} — Wash Trading محتمل")
        red_flags += 1
    elif report.volume_ratio < VOL_DRY_THRESHOLD:
        report.warnings.append(f"⚠️ سيولة جافة ({report.volume_ratio*100:.0f}%) — حذر")
        yellow_flags += 1
    
    # 2. عدد الصفقات (MM يتحكم؟)
    if report.trades_per_million > 0 and report.trades_per_million < TRADES_PER_MIL_MIN:
        report.warnings.append(
            f"🚨 {report.trades_per_million:.0f} صفقة/مليون فقط — MM يتحكم"
        )
        red_flags += 1
    
    # 3. Spread
    if report.spread_pct > SPREAD_MAX_PCT:
        report.warnings.append(f"⚠️ Spread واسع ({report.spread_pct:.2f}%) — سيولة جافة")
        yellow_flags += 1
    
    # 4. OB Depth
    if report.ob_depth_usdt < OB_DEPTH_MIN_USDT:
        report.warnings.append(
            f"🚨 OB ضحل (${report.ob_depth_usdt:,.0f}) — يتحرك بسهولة"
        )
        red_flags += 1
    
    # 5. ATR شاذ
    if report.atr_ratio > ATR_ANOMALY_RATIO:
        report.warnings.append(f"🚨 تقلب شاذ (ATR ×{report.atr_ratio:.1f}) — pump مفاجئ")
        red_flags += 1
    
    # ─ القرار النهائي ─
    if red_flags >= 1:
        report.status = "RED"
        report.healthy = False
    elif yellow_flags >= 2:
        report.status = "YELLOW"
        report.healthy = False  # نحظر مؤقتاً
    elif yellow_flags == 1:
        report.status = "YELLOW"
        report.healthy = True  # تحذير فقط
    else:
        report.status = "GREEN"
        report.healthy = True
    
    return report


# ═══════════════════════════════════════════════════════════════
# ─── CACHE LAYER ──────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

_CACHE = {}  # symbol → (timestamp, report)
CACHE_TTL = 60  # ثانية — صلاحية النتيجة دقيقة واحدة


async def check_liquidity_cached(symbol: str) -> LiquidityReport:
    """يفحص مع cache (لا يعيد الحساب إذا كان فحص حديث)"""
    now = time.time()
    cached = _CACHE.get(symbol)
    if cached and (now - cached[0]) < CACHE_TTL:
        return cached[1]
    
    report = await check_liquidity_health(symbol)
    _CACHE[symbol] = (now, report)
    return report


# ═══════════════════════════════════════════════════════════════
# ─── INTEGRATION HELPER ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def validate_liquidity(symbol: str) -> tuple[bool, str, dict]:
    """
    يُستخدم قبل إرسال أي إشارة
    Returns: (approved, reason, details)
    """
    report = await check_liquidity_cached(symbol)
    
    if not report.healthy:
        reason = " | ".join(report.warnings[:2]) if report.warnings else "Liquidity unhealthy"
        return False, reason, _to_dict(report)
    
    if report.status == "YELLOW":
        # تحذير لكن نقبل
        return True, f"⚠️ {report.warnings[0] if report.warnings else 'تحذير سيولة'}", _to_dict(report)
    
    return True, "✅ السيولة صحية", _to_dict(report)


def _to_dict(r: LiquidityReport) -> dict:
    return {
        "status": r.status,
        "volume_ratio": round(r.volume_ratio, 2),
        "trades_per_million": round(r.trades_per_million, 1),
        "spread_pct": r.spread_pct,
        "ob_depth_usdt": r.ob_depth_usdt,
        "atr_ratio": round(r.atr_ratio, 2),
        "warnings": r.warnings,
    }


# ═══════════════════════════════════════════════════════════════
# ─── CLI ──────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def cli_test():
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    print(f"\n🔍 Liquidity Health: {symbol}\n")
    
    report = await check_liquidity_health(symbol)
    
    status_emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}
    print(f"═══ {status_emoji.get(report.status, '?')} الحالة: {report.status} ═══")
    print(f"Healthy: {'✅ نعم' if report.healthy else '❌ لا'}\n")
    
    print(f"═══ القياسات ═══")
    print(f"  حجم 24h:        ${report.current_volume_24h/1_000_000:,.1f}M")
    print(f"  متوسط 30d:      ${report.avg_volume_30d/1_000_000:,.1f}M")
    print(f"  النسبة:         ×{report.volume_ratio:.2f}")
    print(f"  عدد الصفقات:    {report.trade_count_24h:,}")
    print(f"  صفقة/مليون:     {report.trades_per_million:.0f}")
    print(f"  Spread:         {report.spread_pct:.3f}%")
    print(f"  OB Depth (20):  ${report.ob_depth_usdt:,.0f}")
    print(f"  ATR ratio:      ×{report.atr_ratio:.2f}")
    
    if report.warnings:
        print(f"\n═══ التحذيرات ═══")
        for w in report.warnings:
            print(f"  {w}")
    else:
        print(f"\n✅ لا تحذيرات")


if __name__ == "__main__":
    asyncio.run(cli_test())
