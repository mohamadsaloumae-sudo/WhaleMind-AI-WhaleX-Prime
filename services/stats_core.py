"""📊 المصدر الوحيد لكل إحصاء في النظام.

المشكلة: كل صفحة كانت تحسب بشرطها الخاصّ، فصفحة المراكز تُظهر
+451.9% لسبتمبر والسجلّ الزمنيّ -87% لنفس البيانات. والمشترك لا
يعرف أيّهما يُصدّق — وهذا يهدم مصداقية النظام كلّه.

والقاعدة الآن: أي صفحة تريد رقماً تستدعي هذه الدالّة. ولا استعلام
إحصائيّ خارجها إطلاقاً.

وما نستبعده دائماً:
  ① الظلّية (shadow) — 3,717 صفّاً، تتبّع نظريّ لا يُنفَّذ على أي
     منصّة. لا تُعرَض ولا تُحسَب أبداً.
  ② الملغاة (void)
  ③ وما تجاوز وقف 8% — من فترة الوقف المكسور (ATR بلا سقف)،
     569 صفقة بمجموع -7,348%.

والحدود الزمنية بتوقيت الإمارات (+4).
"""
import logging
import sqlite3

log = logging.getLogger("stats_core")

ML = "/opt/whalex/ml_training.db"
WX = "/opt/whalex/db/whalex.db"
MEME = "/opt/whalex/db/memecoin.db"

# 🔒 الشرط الموحَّد — لا يُكرَّر في أي مكان آخر
FUTURES_FILTER = (
    "pnl_pct IS NOT NULL AND closed_at IS NOT NULL "
    "AND result IS NOT NULL "
    "AND result NOT IN ('void','shadow_hidden') "
    "AND result NOT LIKE 'shadow%' "
    "AND pnl_pct > -9"
)
SPOT_FILTER = "pnl_pct IS NOT NULL AND pnl_pct > -9"
MEME_FILTER = "status='closed' AND pnl_pct IS NOT NULL AND pnl_pct > -9"

# الحدود بتوقيت الإمارات
DAY = "strftime('%s','now','+4 hours','start of day','-4 hours')"
MONTH = "strftime('%s','now','+4 hours','start of month','-4 hours')"


def _agg(rows) -> dict:
    """يحسب الملخّص من قائمة أرباح."""
    w = [x for x in rows if x > 0]
    l = [x for x in rows if x <= 0]
    tp = sum(w)
    tl = sum(abs(x) for x in l)
    return {
        "wins_count": len(w), "losses_count": len(l),
        "total_trades": len(rows),
        "total_profit_pct": round(tp, 2),
        "total_loss_pct": round(tl, 2),
        "net_pct": round(tp - tl, 2),
        "win_rate": round(len(w) / len(rows) * 100, 1) if rows else 0.0,
    }


def summary(market: str = "futures", period: str = "month") -> dict:
    """الملخّص الموحَّد. period: day · month · all"""
    try:
        if market == "meme":
            db, col, flt = MEME, "closed_ts", MEME_FILTER
        elif market == "spot":
            db, col, flt = WX, "ts", SPOT_FILTER
        else:
            db, col, flt = ML, "closed_at", FUTURES_FILTER
        tbl = {"meme": "meme_signals", "spot": "spot_results"}.get(
            market, "training_signals")
        where = flt
        if period == "day":
            where += f" AND {col} > {DAY}"
        elif period == "month":
            where += f" AND {col} > {MONTH}"
        c = sqlite3.connect(db)
        rows = [r[0] for r in c.execute(
            f"SELECT pnl_pct FROM {tbl} WHERE {where}")]
        c.close()
        return _agg(rows)
    except Exception as e:
        log.error("ملخّص %s/%s: %s", market, period, e)
        return _agg([])


def daily(market: str = "futures", days: int = 30) -> list:
    """أرباح كل يوم — للسجلّ الزمنيّ. نفس المرشّح تماماً."""
    try:
        if market == "meme":
            db, col, flt, tbl = MEME, "closed_ts", MEME_FILTER, "meme_signals"
        elif market == "spot":
            db, col, flt, tbl = WX, "ts", SPOT_FILTER, "spot_results"
        else:
            db, col, flt, tbl = ML, "closed_at", FUTURES_FILTER, "training_signals"
        c = sqlite3.connect(db)
        rows = c.execute(f"""
            SELECT date({col}, 'unixepoch', '+4 hours') d,
                   COUNT(*) n,
                   SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) w,
                   ROUND(SUM(pnl_pct), 2) net
            FROM {tbl} WHERE {flt}
              AND {col} > strftime('%s','now', '-{int(days)} days')
            GROUP BY d ORDER BY d DESC""").fetchall()
        c.close()
        return [{"date": r[0], "trades": r[1], "wins": r[2],
                 "losses": r[1] - r[2], "net_pct": r[3] or 0.0} for r in rows]
    except Exception as e:
        log.error("يوميّ %s: %s", market, e)
        return []
