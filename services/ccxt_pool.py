"""🏊 مجمع عملاء ccxt — عميل واحد لكل (منصّة، نوع).

🔴 تسريب مقيس: كل وحدة كانت تُنشئ عملاءها وتستدعي load_markets().
   وأسواق باينانس وحدها 4,597 سوقاً تشغل 192 ميجابايت، وبناة الكون
   يُعيدون البناء دورياً لسبع منصّات — أي 1.3 جيجابايت تُخصَّص وتُهمَل
   في كل دورة. وبايثون لا يُعيد الذاكرة المحرّرة للنظام تلقائياً،
   فتنمو من 1,471 إلى 2,805 ميجابايت في أربع دقائق.

   والحلّ: مجمع واحد + تحرير دوريّ للذاكرة المفكوكة.
"""
import gc
import logging

log = logging.getLogger("ccxt_pool")
_POOL: dict = {}


def get(exchange: str, kind: str = "spot", timeout: int = 20000):
    """عميل مشترك — يُبنى مرّة واحدة وتُحمَّل أسواقه مرّة واحدة."""
    key = f"{exchange}:{kind}"
    c = _POOL.get(key)
    if c is not None:
        return c
    import ccxt
    opts = {"defaultType": kind}
    if exchange == "okx":
        opts["fetchMarkets"] = [kind]
    c = getattr(ccxt, exchange)({"enableRateLimit": True,
                                 "timeout": timeout, "options": opts})
    _POOL[key] = c
    log.info("🏊 عميل جديد: %s (%s) — المجموع %d", exchange, kind, len(_POOL))
    return c


def markets(exchange: str, kind: str = "swap") -> dict:
    """أسواق المنصّة — تُحمَّل مرّة واحدة وتبقى."""
    c = get(exchange, kind)
    if not c.markets:
        c.load_markets()
    return c.markets or {}


def trim():
    """يُعيد الذاكرة المفكوكة إلى النظام — بايثون لا يفعلها وحده."""
    n = gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass
    return n
