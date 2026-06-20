"""
WhaleMind Order Book Analyzer V1
═══════════════════════════════════════════════════════════════════
كشف ألاعيب صناع السوق بدقة احترافية

الميزات:
✅ Real Bid/Ask Imbalance (top 20 levels)
✅ Wall Detection (>5x average)
✅ Spoofing Detection (snapshots كل 3 ثوانٍ)
✅ Iceberg Order Detection (refills سريعة)
✅ Liquidity Pool Mapping (تجمعات stops)
✅ Pressure Score (-1.0 to +1.0)
"""

import asyncio
import httpx
import logging
import time
import statistics
from typing import Optional
from dataclasses import dataclass, field

log = logging.getLogger("order_book_analyzer")

BINANCE_FAPI = "https://fapi.binance.com/fapi/v1"


# ═══════════════════════════════════════════════════════════════
# ─── DATA STRUCTURES ──────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

@dataclass
class OrderBookSnapshot:
    """لقطة من Order Book في لحظة معينة"""
    symbol: str
    timestamp: float
    bids: list  # [(price, qty), ...]
    asks: list
    mid_price: float = 0.0
    
    @property
    def best_bid(self) -> float:
        return self.bids[0][0] if self.bids else 0.0
    
    @property
    def best_ask(self) -> float:
        return self.asks[0][0] if self.asks else 0.0
    
    @property
    def spread_pct(self) -> float:
        if self.best_bid == 0: return 0
        return ((self.best_ask - self.best_bid) / self.best_bid) * 100


@dataclass
class OrderBookAnalysis:
    """نتيجة التحليل الكامل"""
    symbol: str
    timestamp: float
    
    # Imbalance
    imbalance: float = 0.0  # -1.0 (sell heavy) → +1.0 (buy heavy)
    bid_total_usdt: float = 0.0
    ask_total_usdt: float = 0.0
    
    # Walls
    bid_walls: list = field(default_factory=list)  # [(price, qty, distance_pct)]
    ask_walls: list = field(default_factory=list)
    
    # Spoofing
    spoofing_detected: bool = False
    spoofing_side: str = ""  # bid / ask / none
    spoofing_score: float = 0.0  # 0-1
    
    # Iceberg
    iceberg_detected: bool = False
    iceberg_side: str = ""
    iceberg_price: float = 0.0
    
    # Liquidity
    liquidity_pools_above: list = field(default_factory=list)  # تجمعات stops فوق
    liquidity_pools_below: list = field(default_factory=list)
    
    # Pressure
    pressure_score: float = 0.0  # -1 → +1
    pressure_direction: str = "NEUTRAL"  # LONG / SHORT / NEUTRAL
    pressure_confidence: float = 0.0
    
    # Verdict
    safe_for_long: bool = True
    safe_for_short: bool = True
    rejection_reason: str = ""


# ═══════════════════════════════════════════════════════════════
# ─── FETCHING ─────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def fetch_order_book(symbol: str, limit: int = 100) -> Optional[OrderBookSnapshot]:
    """يجلب Order Book من Binance Futures"""
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(
                f"{BINANCE_FAPI}/depth",
                params={"symbol": symbol, "limit": limit}
            )
            if r.status_code != 200:
                return None
            data = r.json()
            
            bids = [(float(p), float(q)) for p, q in data["bids"]]
            asks = [(float(p), float(q)) for p, q in data["asks"]]
            
            mid = (bids[0][0] + asks[0][0]) / 2 if bids and asks else 0
            
            return OrderBookSnapshot(
                symbol=symbol,
                timestamp=time.time(),
                bids=bids,
                asks=asks,
                mid_price=mid
            )
    except Exception as e:
        log.warning("fetch_order_book %s: %s", symbol, e)
        return None


# ═══════════════════════════════════════════════════════════════
# ─── IMBALANCE CALCULATION ────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def calculate_imbalance(snap: OrderBookSnapshot, depth: int = 20) -> tuple[float, float, float]:
    """
    يحسب bid/ask imbalance على أعمق 20 مستوى
    
    Returns:
        imbalance: -1.0 (بيع قوي) → +1.0 (شراء قوي)
        bid_total_usdt
        ask_total_usdt
    """
    bid_total = sum(p * q for p, q in snap.bids[:depth])
    ask_total = sum(p * q for p, q in snap.asks[:depth])
    
    total = bid_total + ask_total
    if total == 0:
        return 0.0, 0.0, 0.0
    
    imbalance = (bid_total - ask_total) / total
    return round(imbalance, 4), round(bid_total, 2), round(ask_total, 2)


# ═══════════════════════════════════════════════════════════════
# ─── WALL DETECTION ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def detect_walls(snap: OrderBookSnapshot, depth: int = 50, multiplier: float = 5.0) -> tuple[list, list]:
    """
    يكشف الجدران الضخمة في Order Book
    جدار = حجم أعلى من 5x متوسط الحجم
    
    Returns:
        bid_walls: [(price, qty_usdt, distance_pct, multiplier)]
        ask_walls: مثل bid_walls
    """
    bid_walls = []
    ask_walls = []
    
    bids = snap.bids[:depth]
    asks = snap.asks[:depth]
    mid = snap.mid_price
    
    if not bids or not asks or mid == 0:
        return [], []
    
    # متوسط حجم bids و asks بالـ USDT
    bid_volumes_usdt = [p * q for p, q in bids]
    ask_volumes_usdt = [p * q for p, q in asks]
    
    avg_bid = statistics.mean(bid_volumes_usdt)
    avg_ask = statistics.mean(ask_volumes_usdt)
    
    # كشف Bid Walls
    for price, qty in bids:
        qty_usdt = price * qty
        if qty_usdt > avg_bid * multiplier:
            distance = ((mid - price) / mid) * 100
            mult = qty_usdt / avg_bid
            bid_walls.append({
                "price": price,
                "qty_usdt": round(qty_usdt, 2),
                "distance_pct": round(distance, 3),
                "multiplier": round(mult, 1)
            })
    
    # كشف Ask Walls
    for price, qty in asks:
        qty_usdt = price * qty
        if qty_usdt > avg_ask * multiplier:
            distance = ((price - mid) / mid) * 100
            mult = qty_usdt / avg_ask
            ask_walls.append({
                "price": price,
                "qty_usdt": round(qty_usdt, 2),
                "distance_pct": round(distance, 3),
                "multiplier": round(mult, 1)
            })
    
    return bid_walls, ask_walls


# ═══════════════════════════════════════════════════════════════
# ─── SPOOFING DETECTION ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def detect_spoofing(symbol: str, snapshots: int = 3, interval: float = 1.5) -> dict:
    """
    يكشف Spoofing بأخذ snapshots متعددة
    إذا الجدران تظهر وتختفي بسرعة = spoofing
    
    Returns:
        {
            "detected": bool,
            "side": "bid"/"ask"/"none",
            "score": 0-1,
            "details": [...]
        }
    """
    result = {
        "detected": False,
        "side": "none",
        "score": 0.0,
        "details": []
    }
    
    captures = []
    for i in range(snapshots):
        snap = await fetch_order_book(symbol, limit=50)
        if snap:
            bid_walls, ask_walls = detect_walls(snap, depth=20, multiplier=4.0)
            captures.append({
                "time": i * interval,
                "bid_walls": bid_walls,
                "ask_walls": ask_walls,
                "mid": snap.mid_price
            })
        if i < snapshots - 1:
            await asyncio.sleep(interval)
    
    if len(captures) < 2:
        return result
    
    # تحليل: هل هناك جدران ظهرت ثم اختفت؟
    bid_spoofs = 0
    ask_spoofs = 0
    
    # نقارن آخر snapshot مع السابقين
    last = captures[-1]
    for prev in captures[:-1]:
        # bid walls اختفت؟
        for pw in prev["bid_walls"]:
            still_exists = any(
                abs(lw["price"] - pw["price"]) / pw["price"] < 0.001
                for lw in last["bid_walls"]
            )
            if not still_exists and pw["multiplier"] > 5:
                bid_spoofs += 1
        
        # ask walls اختفت؟
        for pw in prev["ask_walls"]:
            still_exists = any(
                abs(lw["price"] - pw["price"]) / pw["price"] < 0.001
                for lw in last["ask_walls"]
            )
            if not still_exists and pw["multiplier"] > 5:
                ask_spoofs += 1
    
    total_spoofs = bid_spoofs + ask_spoofs
    
    if total_spoofs >= 2:
        result["detected"] = True
        result["score"] = min(1.0, total_spoofs / 5)
        if bid_spoofs > ask_spoofs:
            result["side"] = "bid"  # تلاعب لرفع السعر
        elif ask_spoofs > bid_spoofs:
            result["side"] = "ask"  # تلاعب لخفض السعر
        else:
            result["side"] = "both"
    
    result["details"] = {"bid_spoofs": bid_spoofs, "ask_spoofs": ask_spoofs}
    return result


# ═══════════════════════════════════════════════════════════════
# ─── ICEBERG DETECTION ────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def detect_iceberg(symbol: str, snapshots: int = 4, interval: float = 1.0) -> dict:
    """
    Iceberg: جدار يتجدد فوراً بعد تنفيذ جزء منه
    يدل على mm بحجم ضخم لا يريد إظهاره
    """
    result = {"detected": False, "side": "none", "price": 0.0}
    
    captures = []
    for i in range(snapshots):
        snap = await fetch_order_book(symbol, limit=20)
        if snap:
            captures.append(snap)
        if i < snapshots - 1:
            await asyncio.sleep(interval)
    
    if len(captures) < 3:
        return result
    
    # نبحث عن: نفس السعر بكميات متشابهة عبر snapshots
    for level in range(5):  # أعلى 5 مستويات
        # bid side
        bid_prices = []
        bid_qtys = []
        for snap in captures:
            if level < len(snap.bids):
                bid_prices.append(snap.bids[level][0])
                bid_qtys.append(snap.bids[level][1])
        
        if len(set(bid_prices)) == 1 and len(bid_qtys) >= 3:
            # نفس السعر بالضبط عبر 3+ snapshots
            avg_qty = statistics.mean(bid_qtys)
            std = statistics.stdev(bid_qtys) if len(bid_qtys) > 1 else 0
            if avg_qty > 0 and std / avg_qty < 0.15:  # حجم ثابت تقريباً
                # iceberg محتمل
                if avg_qty * bid_prices[0] > 50_000:  # > $50K
                    result["detected"] = True
                    result["side"] = "bid"
                    result["price"] = bid_prices[0]
                    return result
        
        # ask side
        ask_prices = []
        ask_qtys = []
        for snap in captures:
            if level < len(snap.asks):
                ask_prices.append(snap.asks[level][0])
                ask_qtys.append(snap.asks[level][1])
        
        if len(set(ask_prices)) == 1 and len(ask_qtys) >= 3:
            avg_qty = statistics.mean(ask_qtys)
            std = statistics.stdev(ask_qtys) if len(ask_qtys) > 1 else 0
            if avg_qty > 0 and std / avg_qty < 0.15:
                if avg_qty * ask_prices[0] > 50_000:
                    result["detected"] = True
                    result["side"] = "ask"
                    result["price"] = ask_prices[0]
                    return result
    
    return result


# ═══════════════════════════════════════════════════════════════
# ─── LIQUIDITY POOLS ──────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def detect_liquidity_pools(snap: OrderBookSnapshot) -> tuple[list, list]:
    """
    يكتشف تجمعات السيولة (مناطق stops محتملة)
    
    على Order Book، التجمعات تظهر كـ:
    - عدة جدران صغيرة قريبة من بعض
    - حجم تراكمي عالي في منطقة محددة
    """
    above = []  # تجمعات فوق السعر (stops للـ shorts)
    below = []  # تجمعات تحت السعر (stops للـ longs)
    
    mid = snap.mid_price
    if mid == 0: return [], []
    
    # نقسم Order Book إلى bins بـ 0.5% فروقات
    bid_bins = {}
    ask_bins = {}
    
    for price, qty in snap.bids[:50]:
        dist_pct = round(((mid - price) / mid) * 100, 1)  # 0.1% precision
        bid_bins[dist_pct] = bid_bins.get(dist_pct, 0) + (price * qty)
    
    for price, qty in snap.asks[:50]:
        dist_pct = round(((price - mid) / mid) * 100, 1)
        ask_bins[dist_pct] = ask_bins.get(dist_pct, 0) + (price * qty)
    
    # نأخذ أعلى 3 تجمعات في كل اتجاه
    if bid_bins:
        avg_bid = statistics.mean(bid_bins.values())
        for dist, vol in sorted(bid_bins.items(), key=lambda x: x[1], reverse=True)[:3]:
            if vol > avg_bid * 3:
                price = mid * (1 - dist / 100)
                below.append({
                    "price": round(price, 6),
                    "distance_pct": dist,
                    "volume_usdt": round(vol, 2)
                })
    
    if ask_bins:
        avg_ask = statistics.mean(ask_bins.values())
        for dist, vol in sorted(ask_bins.items(), key=lambda x: x[1], reverse=True)[:3]:
            if vol > avg_ask * 3:
                price = mid * (1 + dist / 100)
                above.append({
                    "price": round(price, 6),
                    "distance_pct": dist,
                    "volume_usdt": round(vol, 2)
                })
    
    return above, below


# ═══════════════════════════════════════════════════════════════
# ─── PRESSURE SCORE ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def calculate_pressure(
    imbalance: float,
    bid_walls: list,
    ask_walls: list,
    spoofing: dict,
    iceberg: dict
) -> tuple[float, str, float]:
    """
    يحسب pressure score النهائي
    
    Returns:
        score: -1 (SHORT) → +1 (LONG)
        direction: LONG / SHORT / NEUTRAL
        confidence: 0-1
    """
    score = 0.0
    factors = 0
    
    # 1. Imbalance (الأهم)
    score += imbalance * 0.4
    factors += 1
    
    # 2. Walls
    bid_wall_strength = sum(w["multiplier"] for w in bid_walls) / 10 if bid_walls else 0
    ask_wall_strength = sum(w["multiplier"] for w in ask_walls) / 10 if ask_walls else 0
    
    if bid_wall_strength > ask_wall_strength:
        score += min(0.3, bid_wall_strength * 0.05)
    else:
        score -= min(0.3, ask_wall_strength * 0.05)
    factors += 1
    
    # 3. Spoofing
    if spoofing["detected"]:
        # spoof في bid = تلاعب لرفع السعر زائف → الحقيقة SHORT
        if spoofing["side"] == "bid":
            score -= 0.2
        elif spoofing["side"] == "ask":
            score += 0.2
        factors += 1
    
    # 4. Iceberg
    if iceberg["detected"]:
        # iceberg bid = mm يجمع → LONG قادمة
        if iceberg["side"] == "bid":
            score += 0.15
        elif iceberg["side"] == "ask":
            score -= 0.15
        factors += 1
    
    # نطبّع
    score = max(-1.0, min(1.0, score))
    
    # الاتجاه
    if score > 0.15:
        direction = "LONG"
    elif score < -0.15:
        direction = "SHORT"
    else:
        direction = "NEUTRAL"
    
    confidence = min(1.0, abs(score) * 2)
    
    return round(score, 3), direction, round(confidence, 3)


# ═══════════════════════════════════════════════════════════════
# ─── FULL ANALYSIS ────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def analyze_order_book(symbol: str, check_spoofing: bool = True) -> Optional[OrderBookAnalysis]:
    """
    التحليل الشامل لـ Order Book
    
    Returns: OrderBookAnalysis كاملة
    """
    # 1. Snapshot أساسي
    snap = await fetch_order_book(symbol, limit=100)
    if not snap:
        return None
    
    analysis = OrderBookAnalysis(
        symbol=symbol,
        timestamp=time.time()
    )
    
    # 2. Imbalance
    imb, bid_total, ask_total = calculate_imbalance(snap)
    analysis.imbalance = imb
    analysis.bid_total_usdt = bid_total
    analysis.ask_total_usdt = ask_total
    
    # 3. Walls
    bid_walls, ask_walls = detect_walls(snap)
    analysis.bid_walls = bid_walls
    analysis.ask_walls = ask_walls
    
    # 4. Spoofing (يأخذ ~5 ثوانٍ)
    if check_spoofing:
        spoofing = await detect_spoofing(symbol, snapshots=3, interval=1.5)
    else:
        spoofing = {"detected": False, "side": "none", "score": 0.0}
    
    analysis.spoofing_detected = spoofing["detected"]
    analysis.spoofing_side = spoofing["side"]
    analysis.spoofing_score = spoofing["score"]
    
    # 5. Iceberg (يأخذ ~4 ثوانٍ)
    if check_spoofing:
        iceberg = await detect_iceberg(symbol, snapshots=4, interval=1.0)
    else:
        iceberg = {"detected": False, "side": "none", "price": 0.0}
    
    analysis.iceberg_detected = iceberg["detected"]
    analysis.iceberg_side = iceberg["side"]
    analysis.iceberg_price = iceberg["price"]
    
    # 6. Liquidity Pools
    above, below = detect_liquidity_pools(snap)
    analysis.liquidity_pools_above = above
    analysis.liquidity_pools_below = below
    
    # 7. Pressure Score
    score, direction, conf = calculate_pressure(imb, bid_walls, ask_walls, spoofing, iceberg)
    analysis.pressure_score = score
    analysis.pressure_direction = direction
    analysis.pressure_confidence = conf
    
    # 8. Verdict
    analysis.safe_for_long = True
    analysis.safe_for_short = True
    reasons = []
    
    if imb < -0.4:
        analysis.safe_for_long = False
        reasons.append(f"OB imbalance ضد LONG ({imb:+.2f})")
    if imb > 0.4:
        analysis.safe_for_short = False
        reasons.append(f"OB imbalance ضد SHORT ({imb:+.2f})")
    
    if spoofing["detected"] and spoofing["score"] > 0.6:
        if spoofing["side"] == "bid":
            analysis.safe_for_long = False
            reasons.append("Spoofing على bid (فخ LONG)")
        elif spoofing["side"] == "ask":
            analysis.safe_for_short = False
            reasons.append("Spoofing على ask (فخ SHORT)")
    
    # جدار قريب جداً في طريق الإشارة
    for w in bid_walls:
        if w["distance_pct"] < 0.3 and w["multiplier"] > 8:
            analysis.safe_for_short = False
            reasons.append(f"جدار شراء قوي عند {w['distance_pct']:.2f}%")
            break
    
    for w in ask_walls:
        if w["distance_pct"] < 0.3 and w["multiplier"] > 8:
            analysis.safe_for_long = False
            reasons.append(f"جدار بيع قوي عند {w['distance_pct']:.2f}%")
            break
    
    analysis.rejection_reason = " | ".join(reasons)
    
    return analysis


# ═══════════════════════════════════════════════════════════════
# ─── INTEGRATION HELPER ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def validate_signal_with_order_book(symbol: str, direction: str, fast: bool = False) -> tuple[bool, str, dict]:
    """
    يتحقق من إشارة بناءً على Order Book
    
    Args:
        symbol: العملة
        direction: "LONG" أو "SHORT"
        fast: إذا True، يتخطى spoofing/iceberg (سريع)
    
    Returns:
        (approved, reason, full_analysis_dict)
    """
    analysis = await analyze_order_book(symbol, check_spoofing=not fast)
    if not analysis:
        return False, "فشل جلب Order Book", {}
    
    # الفحوصات
    if direction == "LONG":
        if not analysis.safe_for_long:
            return False, analysis.rejection_reason, _to_dict(analysis)
        if analysis.pressure_direction == "SHORT" and analysis.pressure_confidence > 0.4:
            return False, f"Order Book ضد LONG (pressure {analysis.pressure_score:+.2f})", _to_dict(analysis)
    
    elif direction == "SHORT":
        if not analysis.safe_for_short:
            return False, analysis.rejection_reason, _to_dict(analysis)
        if analysis.pressure_direction == "LONG" and analysis.pressure_confidence > 0.4:
            return False, f"Order Book ضد SHORT (pressure {analysis.pressure_score:+.2f})", _to_dict(analysis)
    
    return True, f"✅ OB يدعم ({analysis.pressure_score:+.2f})", _to_dict(analysis)


def _to_dict(a: OrderBookAnalysis) -> dict:
    return {
        "imbalance": a.imbalance,
        "pressure_score": a.pressure_score,
        "pressure_direction": a.pressure_direction,
        "bid_walls_count": len(a.bid_walls),
        "ask_walls_count": len(a.ask_walls),
        "spoofing": a.spoofing_detected,
        "spoofing_side": a.spoofing_side,
        "iceberg": a.iceberg_detected,
        "liquidity_above": len(a.liquidity_pools_above),
        "liquidity_below": len(a.liquidity_pools_below),
        "safe_long": a.safe_for_long,
        "safe_short": a.safe_for_short,
    }


# ═══════════════════════════════════════════════════════════════
# ─── CLI ──────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def cli_test():
    import sys, json
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    
    print(f"\n🔍 Analyzing {symbol}...\n")
    
    analysis = await analyze_order_book(symbol, check_spoofing=True)
    if not analysis:
        print("❌ Failed to fetch order book")
        return
    
    print(f"═══ Order Book Analysis: {symbol} ═══")
    print(f"Imbalance: {analysis.imbalance:+.3f} ({analysis.bid_total_usdt:,.0f} bid vs {analysis.ask_total_usdt:,.0f} ask)")
    print(f"Pressure: {analysis.pressure_score:+.3f} → {analysis.pressure_direction} (conf {analysis.pressure_confidence:.2f})")
    print(f"\nBid Walls ({len(analysis.bid_walls)}):")
    for w in analysis.bid_walls[:3]:
        print(f"  ${w['qty_usdt']:>10,.0f} @ {w['price']} ({w['distance_pct']:+.2f}%, {w['multiplier']:.1f}x)")
    print(f"\nAsk Walls ({len(analysis.ask_walls)}):")
    for w in analysis.ask_walls[:3]:
        print(f"  ${w['qty_usdt']:>10,.0f} @ {w['price']} ({w['distance_pct']:+.2f}%, {w['multiplier']:.1f}x)")
    print(f"\nSpoofing: {'🚨 DETECTED' if analysis.spoofing_detected else '✅ Clean'}")
    if analysis.spoofing_detected:
        print(f"  Side: {analysis.spoofing_side}, Score: {analysis.spoofing_score:.2f}")
    print(f"Iceberg: {'🚨 DETECTED' if analysis.iceberg_detected else '✅ None'}")
    if analysis.iceberg_detected:
        print(f"  Side: {analysis.iceberg_side} @ {analysis.iceberg_price}")
    
    print(f"\nVerdict:")
    print(f"  Safe for LONG:  {'✅' if analysis.safe_for_long else '❌'}")
    print(f"  Safe for SHORT: {'✅' if analysis.safe_for_short else '❌'}")
    if analysis.rejection_reason:
        print(f"  Reason: {analysis.rejection_reason}")


if __name__ == "__main__":
    asyncio.run(cli_test())
