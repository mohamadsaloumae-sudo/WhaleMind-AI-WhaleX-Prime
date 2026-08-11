"""🔬📈 WhaleX Long v2 — منطق «نضوب الرافعة» (Leverage Exhaustion)

بديل «صيد القاع» الذي خسر -228% على 424 صفقة.
القياس: القاع العميق فوز 26% (-99.8%) · RSI<38 فوز 24% (-101.2%) · ob_pressure>0.3 فوز 59% (+22%)

الطبقات الأربع (كلها إلزامية):
  1) شلال تصفية طويلة: السعر ↓ و OI ↓ معاً
  2) نضوب مؤكَّد: OI توقّف + السعر استقرّ
  3) امتصاص في العمق: ضغط>0.3 + جدار شراء حقيقي
  4) استسلام: تمويل سلبي
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field

log = logging.getLogger("whalex_long_v2")

CASCADE_OI_DROP = -3.0
CASCADE_PRICE_DROP = -4.0
EXHAUST_OI_STALL = 1.0
STABILIZE_BARS = 2
MIN_OB_PRESSURE = 0.30
MIN_BUY_WALL_USDT = 50_000
MAX_FUNDING = 0.0
MIN_RSI = 38.0
MIN_VOLUME_USD = 5_000_000
SCAN_INTERVAL = 60
COOLDOWN_SEC = 1800

_last_signal: dict = {}

LV2_STATS: dict = {}
_LV2_KEYS = ("checked", "no_data", "dead_vol", "no_cascade", "not_exhausted",
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
    import httpx
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get("https://fapi.binance.com/futures/data/openInterestHist",
                            params={"symbol": symbol, "period": "15m", "limit": 12})
            if r.status_code != 200:
                return []
            return [float(x["sumOpenInterest"]) for x in r.json()]
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
    cascade = (oi_change <= CASCADE_OI_DROP) and (price_drop <= CASCADE_PRICE_DROP)
    exhausted = oi_recent > -EXHAUST_OI_STALL
    return cascade, exhausted, oi_change, oi_recent, price_drop


def _stabilized(candles) -> bool:
    if len(candles) < STABILIZE_BARS + 2:
        return False
    lows = [c.low for c in candles[-(STABILIZE_BARS + 2):]]
    return min(lows[2:]) >= min(lows[:2])


async def evaluate_symbol(symbol: str):
    from radars.futures.engine import (
        fetch_klines_async, rsi as _rsi, range_position,
        get_funding_rate, get_oi_change,
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

    try:
        from quant_engine.order_book_analyzer import analyze_order_book
        ob = await analyze_order_book(symbol, check_spoofing=True)
    except Exception as e:
        log.debug("ob error %s: %s", symbol, e); ob = None
    if not ob:
        _hit("no_absorption"); return None
    r.ob_pressure = float(getattr(ob, "pressure_score", 0.0) or 0.0)
    if r.ob_pressure < MIN_OB_PRESSURE or not getattr(ob, "safe_for_long", True):
        _hit("no_absorption"); return None
    try:
        walls = getattr(ob, "bid_walls", None) or []
        _vals = []
        for w in walls:
            try:
                _vals.append(float(w[1]))
            except Exception:
                continue
        r.buy_wall_usdt = max(_vals) if _vals else 0.0
    except Exception:
        r.buy_wall_usdt = 0.0
    if r.buy_wall_usdt < MIN_BUY_WALL_USDT:
        _hit("weak_wall"); return None
    r.reasons.append(f"امتصاص: ضغط {r.ob_pressure:+.2f} · جدار ${r.buy_wall_usdt:,.0f}")

    try:
        from quant_engine.delta_engine import fetch_klines as _dk, calculate_cvd, detect_absorption
        kl = await _dk(symbol, "15m", 50)
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
