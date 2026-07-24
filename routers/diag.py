"""🔬 تشخيص سلامة البيانات — يقارن المخزن الحيّ بمصدر باينانس."""
import logging
from fastapi import APIRouter

log = logging.getLogger("diag")
router = APIRouter()


@router.get("/api/diag/klines")
async def klines_integrity(symbol: str = "BTCUSDT", interval: str = "15m", limit: int = 5):
    """يقارن الشموع المخزّنة بالشموع الحقيقية — يكشف أي انحراف فوراً."""
    out = {"symbol": symbol, "interval": interval, "source": None}

    store_rows = None
    try:
        from quant_engine.ob_stream import get_klines as _ob
        _r = _ob(symbol, interval, limit)
        if _r:
            store_rows = [{"t": x["t"], "o": x["o"], "h": x["h"], "l": x["l"], "c": x["c"]} for x in _r]
            out["source"] = "ob_stream"
    except Exception as e:
        out["ob_error"] = str(e)[:80]

    if store_rows is None:
        try:
            from radars.futures.kline_stream import get as _kg, want as _kw, stats as _ks
            _kw(symbol, interval)
            _r = _kg(symbol, interval, limit)
            out["store_stats"] = _ks()
            if _r:
                store_rows = [{"t": int(x[0]) // 1000, "o": float(x[1]), "h": float(x[2]),
                               "l": float(x[3]), "c": float(x[4])} for x in _r]
                out["source"] = "kline_stream"
        except Exception as e:
            out["store_error"] = str(e)[:80]

    if store_rows is None:
        out["verdict"] = "لا بيانات في المخزن بعد — يعمل بـREST"
        return out

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}")
            real = r.json()
        real_rows = [{"t": int(x[0]) // 1000, "o": float(x[1]), "h": float(x[2]),
                      "l": float(x[3]), "c": float(x[4])} for x in real]
    except Exception as e:
        out["verdict"] = "تعذّر جلب المرجع: " + str(e)[:60]
        return out

    # مقارنة الشمعة المكتملة (ما قبل الأخيرة)
    diffs = []
    for s in store_rows:
        m = next((x for x in real_rows if x["t"] == s["t"]), None)
        if not m:
            continue
        for k in ("o", "h", "l", "c"):
            if m[k] and abs(s[k] - m[k]) / m[k] > 0.0005:
                diffs.append({"t": s["t"], "field": k, "store": s[k], "real": m[k]})
    out["store_count"] = len(store_rows)
    out["real_count"] = len(real_rows)
    out["mismatches"] = diffs[:5]
    out["verdict"] = "✅ المخزن مطابق" if not diffs else f"❌ انحراف في {len(diffs)} قيمة"
    return out
