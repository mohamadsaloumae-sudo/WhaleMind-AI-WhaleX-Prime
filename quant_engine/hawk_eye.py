# ═══════════════════════════════════════════════════════════════
# ─── HAWK EYE — عين الصقر — قراءة بنية السوق متعددة الأطر ───────
# ═══════════════════════════════════════════════════════════════
# الفلسفة:
#   يقرأ العملة على 3 طبقات زمنية ليفهم "قصتها الكاملة":
#     • شهري (سنتان) → القصة الكبرى: من أين أتت؟
#     • يومي (شهر)   → المرحلة الحالية (تجميع/صعود/توزيع/هبوط)
#     • 4h (أسبوع)   → الدعم/المقاومة الفعّالة القريبة
#   ثم يحدد:
#     • هل السعر عند قمة/قاع تاريخي؟
#     • هل هذه "قمة جديدة للانعكاس" أم "قمة ضمن صعود مستمر"؟
#     • هل كسر مستوى (breakout/breakdown) أم لمسه (انعكاس)؟
#
# يُدمج في ob_reversal_detector لإعطاء سياق قبل قرار الانعكاس.
# ═══════════════════════════════════════════════════════════════

from __future__ import annotations
import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# ─── الإعدادات ───
SWING_LOOKBACK = 5          # شمعة لكل جانب لتحديد swing high/low
LEVEL_PROXIMITY_PCT = 0.8   # ±0.8% = "عند المستوى"
BREAK_CONFIRM_PCT = 0.5     # كسر بـ +0.5% فوق المستوى = اختراق مؤكد


@dataclass
class MarketStructure:
    symbol: str = ""
    phase: str = "UNKNOWN"          # ACCUMULATION / MARKUP / DISTRIBUTION / MARKDOWN / RANGE
    trend_daily: str = "NEUTRAL"    # UP / DOWN / NEUTRAL
    trend_monthly: str = "NEUTRAL"

    # المستويات
    nearest_resistance: float = 0.0
    nearest_support: float = 0.0
    resistance_distance_pct: float = 0.0   # بُعد السعر عن المقاومة
    support_distance_pct: float = 0.0

    # الموقع الحالي
    at_resistance: bool = False     # عند مقاومة (±proximity)
    at_support: bool = False        # عند دعم
    broke_resistance: bool = False  # كسر المقاومة لأعلى (breakout)
    broke_support: bool = False     # كسر الدعم لأسفل (breakdown)

    # القمم/القيعان التاريخية
    period_high: float = 0.0        # أعلى قمة في الفترة
    period_low: float = 0.0         # أدنى قاع
    near_period_high: bool = False  # قرب القمة التاريخية
    near_period_low: bool = False   # قرب القاع التاريخي

    note: str = ""


def _find_swings(candles: list, lookback: int = SWING_LOOKBACK):
    """يجد القمم (swing highs) والقيعان (swing lows) المحلية."""
    highs, lows = [], []
    n = len(candles)
    for i in range(lookback, n - lookback):
        hi = candles[i].high
        lo = candles[i].low
        # قمة محلية: أعلى من كل الجيران
        is_high = all(hi >= candles[j].high for j in range(i - lookback, i + lookback + 1) if j != i)
        is_low = all(lo <= candles[j].low for j in range(i - lookback, i + lookback + 1) if j != i)
        if is_high:
            highs.append((i, hi))
        if is_low:
            lows.append((i, lo))
    return highs, lows


def _classify_trend(candles: list) -> str:
    """
    يحدد الاتجاه بمنطق هجين:
      1. تأكيد قوي: تتابع القمم/القيعان (HH+HL صعود، LH+LL هبوط)
      2. احتياطي: مقارنة متوسط أول ثلث بآخر ثلث (يكتشف الاتجاه العام)
    """
    if len(candles) < 9:
        return "NEUTRAL"

    closes = [c.close for c in candles]

    # ─ المؤكّد القوي: القمم/القيعان ─
    highs, lows = _find_swings(candles)
    if len(highs) >= 2 and len(lows) >= 2:
        lh = [h[1] for h in highs[-3:]]
        ll = [l[1] for l in lows[-3:]]
        higher_highs = all(lh[i] <= lh[i+1] for i in range(len(lh)-1))
        higher_lows = all(ll[i] <= ll[i+1] for i in range(len(ll)-1))
        lower_highs = all(lh[i] >= lh[i+1] for i in range(len(lh)-1))
        lower_lows = all(ll[i] >= ll[i+1] for i in range(len(ll)-1))
        if higher_highs and higher_lows:
            return "UP"
        if lower_highs and lower_lows:
            return "DOWN"

    # ─ الاحتياطي: مقارنة أول ثلث بآخر ثلث + عتبة ±3% ─
    third = max(3, len(closes) // 3)
    first_avg = sum(closes[:third]) / third
    last_avg = sum(closes[-third:]) / third
    change_pct = (last_avg - first_avg) / first_avg * 100 if first_avg else 0

    if change_pct > 3.0:
        return "UP"
    if change_pct < -3.0:
        return "DOWN"
    return "NEUTRAL"


def _nearest_levels(candles: list, price: float):
    """يجد أقرب مقاومة فوق السعر وأقرب دعم تحته من القمم/القيعان."""
    highs, lows = _find_swings(candles)
    # المقاومات = القمم فوق السعر الحالي
    resistances = sorted([h[1] for h in highs if h[1] > price])
    # الدعوم = القيعان تحت السعر الحالي
    supports = sorted([l[1] for l in lows if l[1] < price], reverse=True)

    nearest_res = resistances[0] if resistances else 0.0
    nearest_sup = supports[0] if supports else 0.0
    return nearest_res, nearest_sup


async def read_market_structure(symbol: str, fetch_klines_fn) -> MarketStructure:
    """
    عين الصقر: يقرأ بنية السوق على 3 أطر زمنية.
    fetch_klines_fn: دالة جلب الشموع (تُمرَّر من engine لتفادي الاستيراد الدائري).
    """
    ms = MarketStructure(symbol=symbol)

    try:
        # ─ الطبقة 1: يومي (30 يوم) — المرحلة + المستويات الرئيسية ─
        daily = await fetch_klines_fn(symbol, "1d", 35)
        if len(daily) < 15:
            ms.note = "بيانات يومية غير كافية"
            return ms

        price = daily[-1].close
        ms.trend_daily = _classify_trend(daily)

        # القمم/القيعان التاريخية (يومي)
        d_highs = [c.high for c in daily]
        d_lows = [c.low for c in daily]
        ms.period_high = max(d_highs)
        ms.period_low = min(d_lows)
        ms.near_period_high = (ms.period_high - price) / price * 100 < 2.0 if price else False
        ms.near_period_low = (price - ms.period_low) / price * 100 < 2.0 if price else False

        # ─ الطبقة 2: شهري (24 شهر) — القصة الكبرى ─
        monthly = await fetch_klines_fn(symbol, "1M", 24)
        if len(monthly) >= 6:
            ms.trend_monthly = _classify_trend(monthly)

        # ─ الطبقة 3: 4h (آخر ~7 أيام = 42 شمعة) — المستويات الفعّالة ─
        h4 = await fetch_klines_fn(symbol, "4h", 50)
        levels_source = h4 if len(h4) >= 20 else daily
        res, sup = _nearest_levels(levels_source, price)
        ms.nearest_resistance = res
        ms.nearest_support = sup
        if res > 0:
            ms.resistance_distance_pct = (res - price) / price * 100
        if sup > 0:
            ms.support_distance_pct = (price - sup) / price * 100

        # ─ تحديد الموقع: عند مستوى؟ كسره؟ ─
        if res > 0 and abs(ms.resistance_distance_pct) <= LEVEL_PROXIMITY_PCT:
            ms.at_resistance = True
        if sup > 0 and abs(ms.support_distance_pct) <= LEVEL_PROXIMITY_PCT:
            ms.at_support = True

        # كسر المقاومة (breakout): السعر تجاوز أعلى قمة 4h بهامش
        recent_high = max(c.high for c in levels_source[:-1]) if len(levels_source) > 1 else price
        recent_low = min(c.low for c in levels_source[:-1]) if len(levels_source) > 1 else price
        if price > recent_high * (1 + BREAK_CONFIRM_PCT / 100):
            ms.broke_resistance = True
        if price < recent_low * (1 - BREAK_CONFIRM_PCT / 100):
            ms.broke_support = True

        # ─ تصنيف المرحلة (Wyckoff مبسّط) ─
        ms.phase = _classify_phase(ms)

        ms.note = (f"{ms.phase} | يومي:{ms.trend_daily} شهري:{ms.trend_monthly} | "
                   f"مقاومة:{res:.4g}({ms.resistance_distance_pct:+.1f}%) "
                   f"دعم:{sup:.4g}({ms.support_distance_pct:+.1f}%)")

    except Exception as e:
        ms.note = f"خطأ: {e}"
        log.debug("read_market_structure %s: %s", symbol, e)

    return ms


def _classify_phase(ms: MarketStructure) -> str:
    """
    يصنّف المرحلة من اتجاهي اليومي والشهري + الموقع:
      MARKUP       — صعود مؤكد (لا شورت، الصعود مستمر)
      MARKDOWN     — هبوط مؤكد (لا لونغ، الهبوط مستمر)
      DISTRIBUTION — قمة بعد صعود (شورت محتمل — توزيع قبل انهيار)
      ACCUMULATION — قاع بعد هبوط (لونغ محتمل — تجميع قبل صعود)
      RANGE        — عرضي
    """
    d = ms.trend_daily
    if d == "UP":
        # صعود + قرب قمة تاريخية = ربما بداية توزيع
        if ms.near_period_high:
            return "MARKUP"   # ما زال صاعداً (القمة جزء من الصعود)
        return "MARKUP"
    if d == "DOWN":
        if ms.near_period_low:
            return "MARKDOWN"
        return "MARKDOWN"
    # NEUTRAL يومي → نطاق: تجميع أو توزيع حسب الموقع
    if ms.near_period_high:
        return "DISTRIBUTION"   # عرضي قرب القمة = توزيع
    if ms.near_period_low:
        return "ACCUMULATION"   # عرضي قرب القاع = تجميع
    return "RANGE"


def evaluate_reversal_context(ms: MarketStructure, direction: str) -> tuple[float, str]:
    """
    يقيّم: هل سياق البنية يدعم إشارة الانعكاس؟
    يُرجع (modifier, reason):
      modifier > 1.0 → السياق يقوّي الإشارة
      modifier < 1.0 → السياق يضعفها
      modifier = 0.0 → السياق يلغيها (breakout/ضد البنية)
    """
    if direction == "SHORT":
        # إلغاء: breakout صاعد (كسر مقاومة = ليس انعكاساً)
        if ms.broke_resistance:
            return 0.0, "كسر المقاومة (breakout صاعد) — ليس انعكاساً"
        # إلغاء: صعود مستمر قوي + ليس عند مقاومة
        if ms.phase == "MARKUP" and not ms.at_resistance:
            return 0.6, "صعود مستمر (MARKUP) — شورت ضد الاتجاه (ثقة مُضعّفة)"
        # تقوية: عند مقاومة + مرحلة توزيع = انعكاس مثالي
        if ms.at_resistance and ms.phase == "DISTRIBUTION":
            return 1.3, "عند مقاومة + توزيع — انعكاس قوي 🦅"
        # تقوية: عند مقاومة في هبوط = pullback مثالي للشورت
        if ms.at_resistance and ms.phase == "MARKDOWN":
            return 1.25, "عند مقاومة في هبوط — pullback مثالي"
        # تقوية متوسطة: هبوط مستمر
        if ms.phase == "MARKDOWN":
            return 1.1, "هبوط مستمر — يدعم الشورت"
        return 1.0, "سياق محايد"

    else:  # LONG
        if ms.broke_support:
            return 0.0, "كسر الدعم (breakdown هابط) — ليس انعكاساً"
        if ms.phase == "MARKDOWN" and not ms.at_support:
            return 0.6, "هبوط مستمر (MARKDOWN) — لونغ ضد الاتجاه (ثقة مُضعّفة)"
        if ms.at_support and ms.phase == "ACCUMULATION":
            return 1.3, "عند دعم + تجميع — انعكاس قوي 🦅"
        if ms.at_support and ms.phase == "MARKUP":
            return 1.25, "عند دعم في صعود — pullback مثالي"
        if ms.phase == "MARKUP":
            return 1.1, "صعود مستمر — يدعم اللونغ"
        return 1.0, "سياق محايد"
