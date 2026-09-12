"""💰 رأس مال التداول — حقل واحد يضبط كل شيء.

المشترك يحدد كم يريد ان يتداول به من محفظته، والنظام يحسب مبلغ
الصفقة والسقف تلقائيا. ولا يُمسّ ما زاد عن رأس المال المحدد.

المعادلة (مقيسة 12 سبتمبر على 227 صفقة في 7 ايام):
  التزامن ≤6 يغطي 90% من الفتحات · ≤8 يغطي 96%
  فيوتشر: (راس المال − 5%) ÷ 8
  سبوت  : (راس المال − 5%) ÷ 6  بحد ادنى 50$ (الرسوم)
"""
import sqlite3
import logging
from fastapi import APIRouter, Depends, HTTPException
from routers.auth import get_current_user
from pydantic import BaseModel

log = logging.getLogger("capital")
router = APIRouter(prefix="/api/capital", tags=["capital"])
DB = "/opt/whalex/db/whalex.db"

RESERVE = 0.05
FUT_SLOTS = 8
SPOT_SLOTS = 6
# 📊 مقيس: صفقة 10$ ربحها 0.05$ وعمولتها 0.05$ — صفر صافٍ.
#    فالحد الادنى المجدي 20$ في الفيوتشر و50$ في السبوت.
FUT_MIN = 20.0
SPOT_MIN = 50.0


def compute(capital: float, market: str = "futures") -> dict:
    """يحسب المبلغ والسقف من راس المال."""
    cap = max(0.0, float(capital or 0))
    usable = cap * (1 - RESERVE)
    if market == "spot":
        amt = usable / SPOT_SLOTS
        amt = max(SPOT_MIN, round(amt, 1))
        slots = int(usable // amt) if amt > 0 else 0
        ok = usable >= SPOT_MIN
        why = "" if ok else "رأس المال لا يكفي — الحدّ الأدنى للسبوت 50$ للصفقة"
    else:
        amt = round(usable / FUT_SLOTS, 1)
        amt = max(FUT_MIN, amt)
        slots = int(usable // amt) if amt > 0 else 0
        ok = usable >= FUT_MIN
        why = "" if ok else "رأس المال لا يكفي — الحدّ الأدنى 6$ للصفقة"
    return {"ok": ok, "capital": cap, "market": market,
            "amount": round(amt, 1), "slots": max(0, slots),
            "reserve": round(cap * RESERVE, 2),
            "why": why}


class Body(BaseModel):
    capital: float
    market: str = "futures"
    exchange: str = "binance"


@router.get("/preview")
async def preview(capital: float, market: str = "futures"):
    """حساب بلا حفظ — للعرض الحيّ في الواجهة."""
    return compute(capital, market)


@router.get("/current")
async def current(user=Depends(get_current_user)):
    """راس المال المحفوظ لكل منصّة."""
    uid = user["sub"]
    out = []
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        c.row_factory = sqlite3.Row
        for r in c.execute(
                "SELECT exchange, trading_capital, trade_amount_usdt, "
                "max_open_positions, spot_trade_amount, spot_max_positions, "
                "auto_trade_enabled, spot_auto_enabled "
                "FROM user_binance_credentials WHERE user_id=?", (uid,)):
            d = dict(r)
            out.append({
                "exchange": d.get("exchange") or "binance",
                "capital": float(d.get("trading_capital") or 0),
                "futures": {"amount": d.get("trade_amount_usdt"),
                            "slots": d.get("max_open_positions"),
                            "on": bool(d.get("auto_trade_enabled"))},
                "spot": {"amount": d.get("spot_trade_amount"),
                         "slots": d.get("spot_max_positions"),
                         "on": bool(d.get("spot_auto_enabled"))},
            })
        c.close()
    except Exception as e:
        log.warning("current %s: %s", uid[:8], e)
    return {"accounts": out}


@router.post("")
async def set_capital(body: Body, user=Depends(get_current_user)):
    """يحفظ راس المال ويحسب المبلغ والسقف تلقائيا."""
    uid = user["sub"]
    r = compute(body.capital, body.market)
    if not r["ok"]:
        raise HTTPException(400, r["why"])
    ex = (body.exchange or "binance").lower()
    try:
        c = sqlite3.connect(DB, timeout=10)
        row = c.execute(
            "SELECT 1 FROM user_binance_credentials WHERE user_id=? AND exchange=?",
            (uid, ex)).fetchone()
        if not row:
            c.close()
            raise HTTPException(404, "لم تربط هذه المنصّة بعد")
        if body.market == "spot":
            c.execute(
                "UPDATE user_binance_credentials SET trading_capital=?, "
                "spot_trade_amount=?, spot_max_positions=? "
                "WHERE user_id=? AND exchange=?",
                (r["capital"], r["amount"], r["slots"], uid, ex))
        else:
            c.execute(
                "UPDATE user_binance_credentials SET trading_capital=?, "
                "trade_amount_usdt=?, max_open_positions=? "
                "WHERE user_id=? AND exchange=?",
                (r["capital"], r["amount"], r["slots"], uid, ex))
        c.commit()
        c.close()
        log.info("💰 %s %s على %s: راس مال %.0f$ → %.1f$ × %d",
                 uid[:8], body.market, ex, r["capital"], r["amount"], r["slots"])
    except HTTPException:
        raise
    except Exception as e:
        log.error("set_capital %s: %s", uid[:8], e)
        raise HTTPException(500, "تعذّر الحفظ")
    return {"success": True, **r}
