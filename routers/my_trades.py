"""📒 صفقات المشترك — تنفيذه هو لا اشارات النظام.

مقيس 17 سبتمبر: SYNUSDT نُفّذت للمشترك بـ0.20469 وبطاقة التفاصيل
تعرض 0.19936 (سعر الاشارة)، فيرى سعرا لم يدخل به ونسبة لا تطابق
حسابه على المنصّة.

والسبب ان صفحة الصفقات تقرأ signals/history — وهو اشارات النظام
المشتركة بين كل المستخدمين. وهذا المسار مستقل تماما: يقرأ تنفيذ
هذا المشترك وحده، فلا يمسّ الرئيسية ولا اي شاشة اخرى.

الفيوتشر: user_trades · السبوت: spot_positions_multi
والصافي من real_net (تسوية المنصّة) ان توفّر.
"""
import sqlite3
import logging
from fastapi import APIRouter, Depends, Query

from routers.auth import get_current_user

log = logging.getLogger("my_trades")
router = APIRouter(prefix="/api/mytrades", tags=["MyTrades"])
DB = "/opt/whalex/db/whalex.db"

_DAY = ("(strftime('%s','now','+4 hours','start of day','-4 hours'))")


@router.get("/history")
def history(market: str = Query("futures"), days: int = Query(1),
            user=Depends(get_current_user)):
    uid = user["sub"]
    since = "%s - %d" % (_DAY, max(0, days - 1) * 86400)
    out = []
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        c.row_factory = sqlite3.Row
        if market == "spot":
            rows = [dict(r) for r in c.execute(
                "SELECT symbol, entry, exit_price, qty, spend, pnl_pct, ts, "
                "closed_ts, real_net, real_fee, exchange "
                "FROM spot_positions_multi WHERE user_id=? AND status='closed' "
                "AND closed_ts IS NOT NULL AND closed_ts >= " + since +
                " ORDER BY closed_ts DESC LIMIT 300", (uid,))]
            for x in rows:
                net = x["real_net"]
                if net is None:
                    net = float(x["spend"] or 0) * float(x["pnl_pct"] or 0) / 100
                out.append({
                    "symbol": x["symbol"], "direction": "LONG",
                    "entry": x["entry"], "exit_price": x["exit_price"],
                    "qty": x["qty"], "leverage": 1,
                    "pnl_pct": x["pnl_pct"], "net_usdt": round(float(net), 4),
                    "commission": x["real_fee"],
                    "opened_at": x["ts"], "closed_at": x["closed_ts"],
                    "is_win": bool(float(net) > 0),
                    "radar": "🪙 رادار السبوت", "tier": "SP",
                    "exchange": x["exchange"], "close_reason": "spot_exit",
                    "duration_min": round(((x["closed_ts"] or 0) -
                                           (x["ts"] or 0)) / 60, 1),
                })
        else:
            rows = [dict(r) for r in c.execute(
                "SELECT symbol, direction, entry, exit_price, qty, leverage, "
                "pnl_pct, net_usdt, real_net, commission, real_fee, opened_at, "
                "closed_at, close_reason FROM user_trades "
                "WHERE user_id=? AND market='futures' AND closed_at IS NOT NULL "
                "AND closed_at >= " + since +
                " ORDER BY closed_at DESC LIMIT 300", (uid,))]
            for x in rows:
                net = x["real_net"] if x["real_net"] is not None else x["net_usdt"]
                fee = x["real_fee"] if x["real_fee"] is not None else x["commission"]
                out.append({
                    "symbol": x["symbol"], "direction": x["direction"],
                    "entry": x["entry"], "exit_price": x["exit_price"],
                    "qty": x["qty"], "leverage": x["leverage"],
                    "pnl_pct": x["pnl_pct"],
                    "net_usdt": round(float(net or 0), 4),
                    "commission": fee,
                    "opened_at": x["opened_at"], "closed_at": x["closed_at"],
                    "is_win": bool(float(net or 0) > 0),
                    "radar": "⚡ تنفيذ حقيقيّ", "tier": "LIVE",
                    "exchange": "binance",
                    "close_reason": x["close_reason"],
                    "duration_min": round(((x["closed_at"] or 0) -
                                           (x["opened_at"] or 0)) / 60, 1),
                })
        c.close()
    except Exception as e:
        log.warning("mytrades %s: %s", uid[:8], str(e)[:70])
        return {"history": [], "error": str(e)[:70]}

    w = [r for r in out if r["is_win"]]
    return {
        "history": out,
        "summary": {
            "trades": len(out), "wins": len(w), "losses": len(out) - len(w),
            "win_rate": round(len(w) * 100 / len(out), 1) if out else 0,
            "net_usd": round(sum(r["net_usdt"] for r in out), 2),
            "fees_usd": round(sum(float(r["commission"] or 0) for r in out), 2),
        },
    }
