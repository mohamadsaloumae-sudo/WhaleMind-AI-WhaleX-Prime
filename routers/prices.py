from fastapi import APIRouter
from services.prices import get_all_prices, get_price

router = APIRouter(prefix="/api/prices", tags=["Prices"])

@router.get("/all")
def all_prices():
    return {"prices": get_all_prices()}

@router.get("/live-check")
def live_check():
    from radars.futures.price_stream import _TICK
    import time as _t
    now = _t.time()
    fresh = {k: v for k, v in _TICK.items() if v and (now - v[3]) <= 15}
    return {"tick_total": len(_TICK), "fresh": len(fresh),
            "sample": {k: _TICK[k][0] for k in list(fresh)[:3]}}


@router.get("/{symbol}")
def symbol_price(symbol: str):
    return {"symbol": symbol, "data": get_price(symbol)}
