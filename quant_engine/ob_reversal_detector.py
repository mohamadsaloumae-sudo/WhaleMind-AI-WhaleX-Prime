"""
WhaleMind OB Reversal Detector V2
═══════════════════════════════════════════════════════════════════
يكتشف انقلاب Order Book القوي كـ TRIGGER لإشارة SHORT/LONG
+ BTC Alignment Layer (طبقة تأكيد، لا فلتر)

الفلسفة:
- 44 عملتنا تتبع BTC بنسبة 90%+
- انقلاب OB على عملة = trigger
- BTC الموافق = يرفع الثقة (تأكيد مزدوج)
- BTC المحايد = الإشارة تبقى عادية
- BTC المعاكس = الثقة تنخفض + تحذير (نادر لكن مهم)
"""

import asyncio
import httpx
import logging
import time
import statistics
from typing import Optional
from dataclasses import dataclass, field

log = logging.getLogger("ob_reversal")

BINANCE_FAPI = "https://fapi.binance.com/fapi/v1"

# ─── إعدادات قابلة للضبط ───────────────────────────────────────
CONFIRM_SNAPSHOTS = 4
CONFIRM_INTERVAL = 20        # 4×20 = 80 ثانية
IMBALANCE_TRIGGER = 0.40
WALL_MULTIPLIER = 6.0
MIN_PRICE_MOVE_PCT = 0.15
PERSISTENCE_REQUIRED = 0.70

# BTC Alignment
BTC_ALIGNMENT_THRESHOLD = 0.15  # imbalance > 0.15 = اتجاه واضح


@dataclass
class OBSnapshot:
    timestamp: float
    mid_price: float
    imbalance: float
    bid_wall_usdt: float
    ask_wall_usdt: float
    bid_wall_price: float
    ask_wall_price: float


@dataclass
class BTCAlignment:
    """تأكيد BTC للإشارة"""
    btc_direction: str = "NEUTRAL"      # SHORT / LONG / NEUTRAL
    btc_imbalance: float = 0.0
    eth_direction: str = "NEUTRAL"
    eth_imbalance: float = 0.0
    alignment: str = ""                  # "CONFIRMED" / "NEUTRAL" / "DIVERGENT"
    confidence_modifier: float = 1.0     # 0.7 → 1.3
    note: str = ""


@dataclass
class OBReversalSignal:
    symbol: str
    detected: bool = False
    direction: str = ""
    confidence: float = 0.0
    grade: str = ""                      # S/A/B
    reason: str = ""

    avg_imbalance: float = 0.0
    persistence_pct: float = 0.0
    price_move_pct: float = 0.0
    wall_confirmed: bool = False
    spoofing_detected: bool = False
    snapshots_count: int = 0

    btc_alignment: Optional[BTCAlignment] = None


# ═══════════════════════════════════════════════════════════════
# ─── FETCH SNAPSHOT ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def fetch_ob_snapshot(symbol: str) -> Optional[OBSnapshot]:
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{BINANCE_FAPI}/depth",
                            params={"symbol": symbol, "limit": 50})
            if r.status_code != 200:
                return None
            d = r.json()
            bids = [(float(p), float(q)) for p, q in d["bids"]]
            asks = [(float(p), float(q)) for p, q in d["asks"]]
            if not bids or not asks:
                return None
            mid = (bids[0][0] + asks[0][0]) / 2
            bid_usdt = sum(p * q for p, q in bids[:20])
            ask_usdt = sum(p * q for p, q in asks[:20])
            total = bid_usdt + ask_usdt
            imbalance = (bid_usdt - ask_usdt) / total if total else 0
            bid_vols = [(p, p * q) for p, q in bids[:50]]
            ask_vols = [(p, p * q) for p, q in asks[:50]]
            max_bid = max(bid_vols, key=lambda x: x[1]) if bid_vols else (0, 0)
            max_ask = max(ask_vols, key=lambda x: x[1]) if ask_vols else (0, 0)
            return OBSnapshot(
                timestamp=time.time(),
                mid_price=mid,
                imbalance=round(imbalance, 4),
                bid_wall_usdt=round(max_bid[1], 2),
                ask_wall_usdt=round(max_ask[1], 2),
                bid_wall_price=max_bid[0],
                ask_wall_price=max_ask[0],
            )
    except Exception as e:
        log.debug("fetch_ob_snapshot %s: %s", symbol, e)
        return None


# ═══════════════════════════════════════════════════════════════
# ─── BTC ALIGNMENT CHECK (الجديد) ─────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def check_btc_alignment(coin_direction: str) -> BTCAlignment:
    """
    يتحقق من توافق BTC و ETH مع اتجاه الإشارة

    الفلسفة: 44 عملتنا تتبع BTC بـ 90%+
    - BTC موافق → ثقة أعلى (×1.2 إلى ×1.3)
    - BTC محايد → ثقة عادية (×1.0)
    - BTC معاكس → ثقة أقل + تحذير (×0.7) — حدث نادر لكن مهم
    """
    result = BTCAlignment()

    # نجلب OB لـ BTC و ETH بالتوازي
    btc_task = fetch_ob_snapshot("BTCUSDT")
    eth_task = fetch_ob_snapshot("ETHUSDT")
    btc_snap, eth_snap = await asyncio.gather(btc_task, eth_task)

    if btc_snap:
        result.btc_imbalance = btc_snap.imbalance
        if btc_snap.imbalance < -BTC_ALIGNMENT_THRESHOLD:
            result.btc_direction = "SHORT"
        elif btc_snap.imbalance > BTC_ALIGNMENT_THRESHOLD:
            result.btc_direction = "LONG"
        else:
            result.btc_direction = "NEUTRAL"

    if eth_snap:
        result.eth_imbalance = eth_snap.imbalance
        if eth_snap.imbalance < -BTC_ALIGNMENT_THRESHOLD:
            result.eth_direction = "SHORT"
        elif eth_snap.imbalance > BTC_ALIGNMENT_THRESHOLD:
            result.eth_direction = "LONG"
        else:
            result.eth_direction = "NEUTRAL"

    # ─ تحليل التوافق ─
    btc_match = result.btc_direction == coin_direction
    eth_match = result.eth_direction == coin_direction
    btc_opposite = (
        (coin_direction == "SHORT" and result.btc_direction == "LONG") or
        (coin_direction == "LONG" and result.btc_direction == "SHORT")
    )

    if btc_match and eth_match:
        result.alignment = "CONFIRMED"
        result.confidence_modifier = 1.3
        result.note = f"BTC + ETH يؤكدان {coin_direction} — تأكيد مزدوج قوي"
    elif btc_match:
        result.alignment = "CONFIRMED"
        result.confidence_modifier = 1.2
        result.note = f"BTC يؤكد {coin_direction}"
    elif btc_opposite:
        result.alignment = "DIVERGENT"
        result.confidence_modifier = 0.7
        result.note = f"⚠️ BTC في اتجاه معاكس ({result.btc_direction}) — العملة منحازة"
    else:
        result.alignment = "NEUTRAL"
        result.confidence_modifier = 1.0
        result.note = f"BTC محايد — الإشارة على قوتها الذاتية"

    return result


# ═══════════════════════════════════════════════════════════════
# ─── MAIN DETECTOR ────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def detect_ob_reversal(symbol: str, check_btc: bool = True) -> OBReversalSignal:
    """يكتشف انقلاب Order Book مؤكَّد + توافق BTC"""
    result = OBReversalSignal(symbol=symbol)

    # ─ اللقطة الأولى ─
    first = await fetch_ob_snapshot(symbol)
    if not first:
        return result

    if abs(first.imbalance) < IMBALANCE_TRIGGER:
        return result

    initial_direction = "SHORT" if first.imbalance < 0 else "LONG"
    log.info("🔍 OB Reversal candidate: %s %s (imb %.2f) — confirming...",
             symbol, initial_direction, first.imbalance)

    # ─ لقطات التأكيد ─
    snapshots = [first]
    for i in range(CONFIRM_SNAPSHOTS - 1):
        await asyncio.sleep(CONFIRM_INTERVAL)
        snap = await fetch_ob_snapshot(symbol)
        if snap:
            snapshots.append(snap)

    result.snapshots_count = len(snapshots)
    if len(snapshots) < 3:
        result.reason = "لقطات غير كافية"
        return result

    # ─ التحقق 1: الاستمرارية ─
    confirming = 0
    for snap in snapshots:
        snap_dir = "SHORT" if snap.imbalance < 0 else "LONG"
        if snap_dir == initial_direction and abs(snap.imbalance) >= IMBALANCE_TRIGGER * 0.7:
            confirming += 1
    persistence = confirming / len(snapshots)
    result.persistence_pct = round(persistence * 100, 1)
    result.avg_imbalance = round(statistics.mean([s.imbalance for s in snapshots]), 4)

    if persistence < PERSISTENCE_REQUIRED:
        result.reason = f"الانقلاب غير مستمر ({result.persistence_pct:.0f}%) — spoofing محتمل"
        result.spoofing_detected = True
        log.info("🚫 OB Reversal rejected: %s — spoofing", symbol)
        return result

    # ─ التحقق 2: حركة السعر ─
    first_price = snapshots[0].mid_price
    last_price = snapshots[-1].mid_price
    price_move = (last_price - first_price) / first_price * 100
    result.price_move_pct = round(price_move, 3)

    if initial_direction == "SHORT":
        if price_move > -MIN_PRICE_MOVE_PCT:
            result.reason = f"السعر لم يتحرك هبوطاً ({price_move:+.2f}%) — انتظار"
            return result
    else:
        if price_move < MIN_PRICE_MOVE_PCT:
            result.reason = f"السعر لم يتحرك صعوداً ({price_move:+.2f}%) — انتظار"
            return result

    # ─ التحقق 3: ثبات الجدار ─
    if initial_direction == "SHORT":
        walls = [s.ask_wall_usdt for s in snapshots]
    else:
        walls = [s.bid_wall_usdt for s in snapshots]
    avg_wall = statistics.mean(walls)
    if avg_wall > 0:
        wall_stability = statistics.stdev(walls) / avg_wall
        result.wall_confirmed = wall_stability < 0.5

    # ─ التحقق 4 (الجديد): BTC Alignment ─
    base_confidence = persistence * 0.5
    base_confidence += min(abs(price_move) / 0.5, 1.0) * 0.3
    base_confidence += 0.2 if result.wall_confirmed else 0
    base_confidence = min(base_confidence, 1.0)

    if check_btc and symbol not in ("BTCUSDT", "ETHUSDT"):
        # نتحقق من توافق BTC (لا نفعل ذلك لـ BTC/ETH نفسهما)
        log.info("🔄 Checking BTC alignment for %s %s...", symbol, initial_direction)
        btc_align = await check_btc_alignment(initial_direction)
        result.btc_alignment = btc_align

        # نطبّق modifier على الثقة
        final_confidence = base_confidence * btc_align.confidence_modifier
        final_confidence = min(final_confidence, 1.0)

        # تنبيه: إذا BTC معاكس بقوة، نضع حد أدنى للقبول
        if btc_align.alignment == "DIVERGENT" and final_confidence < 0.5:
            result.reason = f"BTC معاكس + ثقة منخفضة — إلغاء"
            return result
    else:
        final_confidence = base_confidence

    # ─ القرار النهائي ─
    result.detected = True
    result.direction = initial_direction
    result.confidence = round(final_confidence, 3)

    # ─ Grading ─
    if result.btc_alignment and result.btc_alignment.alignment == "CONFIRMED" and final_confidence >= 0.85:
        result.grade = "S"  # تأكيد مزدوج + ثقة عالية
    elif final_confidence >= 0.75:
        result.grade = "A"
    elif final_confidence >= 0.60:
        result.grade = "B"
    else:
        result.grade = "C"

    # ─ Reason ─
    parts = [
        f"OB انقلب {result.persistence_pct:.0f}%",
        f"حركة {price_move:+.2f}%",
        f"جدار {'ثابت' if result.wall_confirmed else 'متذبذب'}",
    ]
    if result.btc_alignment:
        parts.append(result.btc_alignment.note)
    result.reason = " | ".join(parts)

    log.info("✅ OB REVERSAL %s: %s %s (Grade %s, conf %.0f%%) — %s",
             "CONFIRMED" if result.grade in ("S", "A") else "DETECTED",
             symbol, initial_direction, result.grade,
             result.confidence * 100, result.reason)

    return result


# ═══════════════════════════════════════════════════════════════
# ─── INTEGRATION HELPER ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def scan_for_ob_signals(symbols: list) -> list:
    """يفحص قائمة عملات ويرجع الإشارات المكتشفة"""
    signals = []
    for symbol in symbols:
        result = await detect_ob_reversal(symbol)
        if result.detected and result.grade in ("S", "A"):
            signals.append(result)
    return signals



# ═══════════════════════════════════════════════════════════════
# ─── QUICK SCAN (للـ pre-filter) ──────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def quick_scan(symbol: str) -> Optional[str]:
    """
    فحص سريع (لقطة واحدة) — مرشّح أم لا؟
    Returns: "SHORT"/"LONG"/None
    """
    snap = await fetch_ob_snapshot(symbol)
    if not snap:
        return None
    if abs(snap.imbalance) >= IMBALANCE_TRIGGER:
        return "SHORT" if snap.imbalance < 0 else "LONG"
    return None


# ═══════════════════════════════════════════════════════════════
# ─── CLI ──────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def cli_test():
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    symbol = sys.argv[1] if len(sys.argv) > 1 else "AVAXUSDT"
    print(f"\n🔍 OB Reversal Detection: {symbol}")
    print(f"⏱  سيأخذ ~{(CONFIRM_SNAPSHOTS-1)*CONFIRM_INTERVAL} ثانية + BTC check...\n")

    result = await detect_ob_reversal(symbol)

    print(f"\n═══ النتيجة ═══")
    print(f"Detected: {'✅ نعم' if result.detected else '❌ لا'}")
    if result.detected:
        print(f"Direction: {result.direction}")
        print(f"Grade: {result.grade}")
        print(f"Confidence: {result.confidence:.0%}")
    print(f"Snapshots: {result.snapshots_count}")
    print(f"Avg Imbalance: {result.avg_imbalance:+.3f}")
    print(f"Persistence: {result.persistence_pct:.0f}%")
    print(f"Price Move: {result.price_move_pct:+.3f}%")
    print(f"Wall Confirmed: {'✅' if result.wall_confirmed else '❌'}")
    print(f"Spoofing: {'🚨 نعم' if result.spoofing_detected else '✅ لا'}")

    if result.btc_alignment:
        print(f"\n═══ BTC Alignment ═══")
        print(f"BTC: {result.btc_alignment.btc_direction} (imb {result.btc_alignment.btc_imbalance:+.2f})")
        print(f"ETH: {result.btc_alignment.eth_direction} (imb {result.btc_alignment.eth_imbalance:+.2f})")
        print(f"Alignment: {result.btc_alignment.alignment}")
        print(f"Modifier: ×{result.btc_alignment.confidence_modifier}")
        print(f"Note: {result.btc_alignment.note}")

    print(f"\nReason: {result.reason}")


if __name__ == "__main__":
    asyncio.run(cli_test())
