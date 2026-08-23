"""📏 قيمة مستويات دفتر الأوامر — بحجم العقد الصحيح.

مقيس على مكسي:
  PEPE contractSize=10,000,000 → الساذج $0 والصحيح $7,763  (خطأ ×10م)
  SHIB contractSize=1,000      → الساذج $5.6 والصحيح $5,599 (خطأ ×1000)
  BTC  contractSize=0.0001     → الساذج $107 مليار والصحيح $10.7م (خطأ ÷10آلاف)

النِّسَب تنجو (العامل يُلغى بالقسمة) — لكن العمق المطلق والجدران
تُقاس خطأً، وعليها تُبنى قرارات الخروج.
السبوت لا يتأثّر: contractSize = None على كل المنصّات.
"""
import logging
log = logging.getLogger("ob_value")
_CS_CACHE = {}


def contract_size(exchange: str, symbol: str, futures: bool = True) -> float:
    """حجم العقد — 1 للسبوت ولكل ما لا يُعرَف."""
    if not futures:
        return 1.0
    k = f"{exchange}:{symbol}"
    if k in _CS_CACHE:
        return _CS_CACHE[k]
    cs = 1.0
    try:
        import ccxt
        opts = {"defaultType": "swap"}
        if exchange == "okx":
            opts["fetchMarkets"] = ["swap"]
        c = getattr(ccxt, exchange)({"enableRateLimit": True, "timeout": 20000,
                                     "options": opts})
        m = c.load_markets()
        u = symbol.upper()
        base = u[:-4] if u.endswith("USDT") else u
        for cand in (f"{base}/USDT:USDT", f"{base}/USDT"):
            if cand in m:
                cs = float(m[cand].get("contractSize") or 1) or 1.0
                break
    except Exception as e:
        log.debug("contract_size %s/%s: %s", exchange, symbol, e)
    _CS_CACHE[k] = cs
    return cs


def levels_usd(rows, cs: float = 1.0, top: int = 0) -> float:
    """مجموع قيمة المستويات — يقبل [سعر,كمية] و[سعر,كمية,إضافات]."""
    sel = rows[:top] if top else rows
    tot = 0.0
    for r in sel:
        if len(r) < 2:
            continue
        tot += float(r[0]) * float(r[1]) * cs
    return tot


def level_values(rows, cs: float = 1.0, top: int = 0) -> list:
    sel = rows[:top] if top else rows
    return [float(r[0]) * float(r[1]) * cs for r in sel if len(r) >= 2]


def imbalance(bids, asks, cs: float = 1.0, top: int = 10) -> float:
    b = levels_usd(bids, cs, top)
    a = levels_usd(asks, cs, top)
    return ((b - a) / (b + a)) if (b + a) > 0 else 0.0


def wall_ratio(rows, cs: float = 1.0, top: int = 40) -> float:
    v = level_values(rows, cs, top)
    if not v:
        return 0.0
    avg = sum(v) / len(v)
    return (max(v) / avg) if avg > 0 else 0.0
