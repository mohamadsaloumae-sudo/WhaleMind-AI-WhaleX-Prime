"""🛡️ بوّابة العمق — تمنع العملات التي ينهار سعرها بأمر صغير.

المشكلة المقيسة: 255 صفقة سبوت بصافي -79.6%، منها 3 كوارث على bingx
تحمل -86.5%:
  FLYAI -43.14% · ALPHAX -23.37% · DEVERSE -20.00%
وبدونها الصافي +18.9% موجب.

والحجم اليوميّ لا يكشف الهشاشة: ALPHAX كانت 4.64M فوق الوسيط وانهارت
38% في دقيقة. أمّا عمق الدفتر قرب السعر فيكشفها فوراً:
  DEVERSE: أفضل شراء 6.6$ فقط · فارق 3.25% · ثم فجوة 12%

ووسيط عمق الشراء (±2%) بالمنصّة:
  bingx 1,026$ (أدنى 7$) · gate 13,467$ · mexc 84,608$
  okx 182,081$ · bybit 536,461$ · binance 1,856,162$

وعتبة 5,000$ تستبعد 9 عملات من 174 (5%): binance 118/118 تبقى،
وbingx 3/9 فقط. فالفلتر يُصيب الهشّ أينما كان لا منصّةً بعينها.
"""
import logging
import time

log = logging.getLogger("depth_gate")

MIN_BID_USD = 5000.0
MAX_SPREAD_PCT = 1.0
NEAR_PCT = 2.0
CACHE_SEC = 300

_CACHE: dict = {}


def measure(ob: dict) -> tuple:
    """يُعيد (عمق الشراء القريب بالدولار، الفارق %)."""
    b = (ob or {}).get("bids") or []
    a = (ob or {}).get("asks") or []
    if not b or not a:
        return 0.0, 99.0
    try:
        bb, ba = float(b[0][0]), float(a[0][0])
        mid = (bb + ba) / 2
        if mid <= 0:
            return 0.0, 99.0
        spread = (ba - bb) / mid * 100
        lo = mid * (1 - NEAR_PCT / 100)
        usd = sum(float(r[0]) * float(r[1]) for r in b if float(r[0]) >= lo)
        return usd, spread
    except Exception:
        return 0.0, 99.0


def verdict(usd: float, spread: float) -> tuple:
    """هل تصلح للتداول؟ يُعيد (نعم/لا، السبب)."""
    if usd < MIN_BID_USD:
        return False, f"عمق ضحل {usd:,.0f}$ (الحدّ {MIN_BID_USD:,.0f}$)"
    if spread > MAX_SPREAD_PCT:
        return False, f"فارق واسع {spread:.2f}%"
    return True, f"عمق {usd:,.0f}$ · فارق {spread:.2f}%"


def cached(symbol: str):
    v = _CACHE.get(symbol)
    if v and (time.time() - v[2]) < CACHE_SEC:
        return v[0], v[1]
    return None


def remember(symbol: str, ok: bool, why: str):
    _CACHE[symbol] = (ok, why, time.time())
