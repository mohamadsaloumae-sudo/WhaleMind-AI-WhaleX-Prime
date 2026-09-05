"""📅 السجل الزمني — أرباح وخسائر كل نظام شهرياً ويومياً."""
import datetime
import sqlite3
from collections import defaultdict

from fastapi import APIRouter, Depends, Query

from routers.auth import get_current_user

router = APIRouter(prefix="/api/history", tags=["History"])

# نظام → (قاعدة، جدول، عمود الوقت، عمود الربح، تصفية إضافية)
# ⚠️ الفيوتشر يُصفّى بـresult IN (win, loss) لاستبعاد الصفقات الظلّية
#    (shadow_sl · shadow_tp1 · shadow_timeout) — وهي تتبّع للتعلّم لا
#    تداول حقيقيّ. ومقيس: مع الظلّية 3,354 صفقة بـ+478.3%، وبدونها
#    1,938 صفقة بـ+841.0%. وهذا ما تعرضه صفحة الإحصاء، فالرقمان
#    يجب أن يتّفقا — رقمان مختلفان يهدمان الثقة.
# 📊 نفس مرشّح services/stats_core — الظلّية لا تُعرَض ولا تُحسَب.
#   كان هذا الملفّ يستعمل result IN ('win','loss') وحده، فتظهر
#   الظلّية في السجلّ الزمنيّ وتختفي من المراكز: -87% مقابل +483%
#   لنفس الشهر. والمشترك لا يعرف أيّهما يُصدّق.
_F_FUT = ("result IS NOT NULL AND result NOT LIKE 'shadow%' "
          "AND result NOT IN ('void','shadow_hidden') AND pnl_pct > -9")
_F_SPOT = "pnl_pct > -9"
_F_MEME = "status = 'closed' AND pnl_pct > -9"

SYSTEMS = {
    "futures": ("/opt/whalex/ml_training.db", "training_signals", "closed_at",
                "pnl_pct", _F_FUT),
    "spot": ("/opt/whalex/db/whalex.db", "spot_results", "ts", "pnl_pct",
             _F_SPOT),
    "meme": ("/opt/whalex/db/memecoin.db", "meme_signals", "closed_ts",
             "pnl_pct", _F_MEME),
}

LABELS = {"futures": "Futures", "spot": "Spot", "meme": "Memecoins"}
TZ_OFFSET = 4 * 3600


# 🪙 السبوت: جدولان لا يتداخلان — spot_results من 23 أغسطس،
#    وspot_training يحمل ما قبله (19 يوليو إلى 22 أغسطس، 153 صفقة).
#    والمشترك بينهما صفر، فالجمع يُعيد التاريخ الضائع بلا تكرار.
EXTRA_SOURCES = {
    "spot": [("/opt/whalex/db/whalex.db", "spot_training", "ts", "pnl", "pnl > -9")],
}


def _rows(system):
    cfg = SYSTEMS.get(system)
    if not cfg:
        return []
    db, table, tcol, pcol, extra = cfg
    try:
        c = sqlite3.connect(db)
        q = ("SELECT " + tcol + ", " + pcol + " FROM " + table +
             " WHERE " + pcol + " IS NOT NULL AND " + tcol + " IS NOT NULL"
             " AND " + tcol + " > 0")
        if extra:
            q += " AND " + extra
        out = list(c.execute(q))
        c.close()
        for db2, t2, tc2, pc2, ex2 in EXTRA_SOURCES.get(system, []):
            try:
                c2 = sqlite3.connect(db2)
                q2 = ("SELECT " + tc2 + ", " + pc2 + " FROM " + t2 +
                      " WHERE " + pc2 + " IS NOT NULL AND " + tc2 + " > 0")
                if ex2:
                    q2 += " AND " + ex2
                out += list(c2.execute(q2))
                c2.close()
            except Exception:
                pass
        return out
    except Exception:
        return []


def _bucket(rows, fmt):
    g = defaultdict(lambda: {"trades": 0, "wins": 0, "gross_win": 0.0,
                             "gross_loss": 0.0, "net": 0.0,
                             "best": None, "worst": None})
    for t, p in rows:
        try:
            t = int(t)
            if t > 1e12:
                t //= 1000
            p = float(p)
        except Exception:
            continue
        k = datetime.datetime.utcfromtimestamp(t + TZ_OFFSET).strftime(fmt)
        d = g[k]
        d["trades"] += 1
        d["net"] += p
        if p > 0:
            d["wins"] += 1
            d["gross_win"] += p
        else:
            d["gross_loss"] += p
        d["best"] = p if d["best"] is None else max(d["best"], p)
        d["worst"] = p if d["worst"] is None else min(d["worst"], p)
    return g


def _now_local():
    return datetime.datetime.utcnow() + datetime.timedelta(seconds=TZ_OFFSET)


def _shape(k, d, live_key=None):
    """live_key: المفتاح الذي يُعدّ جارياً (اليوم أو الشهر الحاليّ)."""
    n = d["trades"] or 1
    return {
        "period": k,
        # 🔴 اليوم أو الشهر الجاري لم يكتمل — نُعلّمه ولا نُخفيه،
        #    فالمستخدم يرى ما يجري ويعرف أنه غير نهائيّ.
        "live": bool(live_key and k == live_key),
        "trades": d["trades"],
        "wins": d["wins"],
        "losses": d["trades"] - d["wins"],
        "win_rate": round(d["wins"] * 100 / n, 1),
        "gross_win": round(d["gross_win"], 2),
        "gross_loss": round(d["gross_loss"], 2),
        "net": round(d["net"], 2),
        "avg": round(d["net"] / n, 2),
        "best": round(d["best"], 2) if d["best"] is not None else None,
        "worst": round(d["worst"], 2) if d["worst"] is not None else None,
    }


@router.get("/monthly")
def monthly(system: str = Query("futures"), user=Depends(get_current_user)):
    """أداء كل شهر لنظام واحد."""
    g = _bucket(_rows(system), "%Y-%m")
    _cm = _now_local().strftime("%Y-%m")
    months = [_shape(k, g[k], _cm) for k in sorted(g, reverse=True)]
    return {"system": system, "label": LABELS.get(system, system), "months": months}


@router.get("/daily")
def daily(system: str = Query("futures"),
          month: str = Query(...),
          user=Depends(get_current_user)):
    """أيام شهر واحد لنظام واحد."""
    g = _bucket(_rows(system), "%Y-%m-%d")
    _td = _now_local().strftime("%Y-%m-%d")
    days = [_shape(k, g[k], _td) for k in sorted(g, reverse=True) if k.startswith(month)]
    tot = {
        "trades": sum(d["trades"] for d in days),
        "wins": sum(d["wins"] for d in days),
        "net": round(sum(d["net"] for d in days), 2),
    }
    return {"system": system, "label": LABELS.get(system, system),
            "month": month, "days": days, "total": tot}


@router.get("/summary")
def summary(user=Depends(get_current_user)):
    """ملخص كل الأنظمة — للصفحة الرئيسية."""
    now = datetime.datetime.utcnow() + datetime.timedelta(seconds=TZ_OFFSET)
    this_month = now.strftime("%Y-%m")
    today = now.strftime("%Y-%m-%d")
    out = []
    for name in SYSTEMS:
        rows = _rows(name)
        gm = _bucket(rows, "%Y-%m")
        gd = _bucket(rows, "%Y-%m-%d")
        out.append({
            "system": name,
            "label": LABELS.get(name, name),
            "today": _shape(today, gd[today]) if today in gd else None,
            "month": _shape(this_month, gm[this_month]) if this_month in gm else None,
            "months_available": len(gm),
        })
    return {"systems": out, "month": this_month, "today": today}
