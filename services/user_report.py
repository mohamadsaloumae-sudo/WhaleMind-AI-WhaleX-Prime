"""📊 تقرير أداء المشترك — من user_trades لا من الرادار.

يُظهر ما حدث في محفظته هو: عدد الصفقات · نسبة الفوز ·
الربح الخام · الرسوم · والصافي — مفصولاً بين فيوتشر وسبوت.
"""
import sqlite3
import time

DB = "/opt/whalex/db/whalex.db"


def _range(days=7, frm=None, to=None):
    """يُعيد (من، الى) بالثواني. التاريخ بصيغة YYYY-MM-DD."""
    import datetime as _d
    now = int(time.time())
    if frm or to:
        try:
            a = (int(_d.datetime.strptime(frm, "%Y-%m-%d").timestamp())
                 if frm else 0)
            b = (int(_d.datetime.strptime(to, "%Y-%m-%d").timestamp()) + 86399
                 if to else now)
            return a, b
        except Exception:
            pass
    return now - days * 86400, now


def stats(user_id, days=7, frm=None, to=None):
    """احصاءات المشترك — بمدّة او بمدى تاريخيّ."""
    since, until = _range(days, frm, to)
    out = {"days": days, "markets": {}, "total": {}}
    try:
        c = sqlite3.connect(DB)
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT market, pnl_pct, pnl_usdt, commission, net_usdt "
            "FROM user_trades WHERE user_id=? AND status='closed' "
            "AND closed_at > ? AND closed_at <= ?",
            (str(user_id), since, until))]
        opn = [dict(r) for r in c.execute(
            "SELECT market, symbol FROM user_trades "
            "WHERE user_id=? AND status='open'", (str(user_id),))]
        c.close()
    except Exception:
        return out

    def agg(rs):
        if not rs:
            return {"n": 0, "wins": 0, "win_rate": 0.0, "gross": 0.0,
                    "fees": 0.0, "net": 0.0, "best": 0.0, "worst": 0.0}
        w = [r for r in rs if (r["pnl_pct"] or 0) > 0]
        g = sum(float(r["pnl_usdt"] or 0) for r in rs)
        f = sum(float(r["commission"] or 0) for r in rs)
        n = sum(float(r["net_usdt"] if r["net_usdt"] is not None
                      else (r["pnl_usdt"] or 0)) for r in rs)
        p = [float(r["pnl_pct"] or 0) for r in rs]
        return {"n": len(rs), "wins": len(w),
                "win_rate": round(len(w) / len(rs) * 100, 1),
                "gross": round(g, 2), "fees": round(f, 2),
                "net": round(n, 2), "best": round(max(p), 2),
                "worst": round(min(p), 2)}

    for mk in ("futures", "spot"):
        sub = [r for r in rows if (r["market"] or "futures") == mk]
        d = agg(sub)
        d["open"] = len([o for o in opn if (o["market"] or "futures") == mk])
        out["markets"][mk] = d
    out["total"] = agg(rows)
    out["total"]["open"] = len(opn)
    return out


def _name(user_id):
    try:
        c = sqlite3.connect(DB)
        r = c.execute("SELECT username, email FROM users WHERE id=?",
                      (str(user_id),)).fetchone()
        c.close()
        if r and r[0]:
            return str(r[0]).split("@")[0]
        if r and r[1]:
            return str(r[1]).split("@")[0]
    except Exception:
        pass
    return "صديقنا"


PERIODS = {"today": (1, "اليوم"), "week": (7, "هذا الاسبوع"),
           "month": (30, "هذا الشهر"), "all": (3650, "منذ البداية")}


def text(user_id, days=7, ar=True, period=None, frm=None, to=None):
    """نصّ جاهز للارسال عبر البوت. frm/to اختياريّان YYYY-MM-DD."""
    label = None
    if period and period in PERIODS:
        days, label = PERIODS[period]
    if frm or to:
        label = "من %s الى %s" % (frm or "البداية", to or "اليوم")
    s = stats(user_id, days, frm, to)
    t = s["total"]
    if not t.get("n") and not t.get("open"):
        return ("👋 أهلاً <b>%s</b>\n\n📊 لا صفقات في %s."
                % (_name(user_id), label or ("آخر %d أيام" % days)))
    L = []
    L.append("👋 أهلاً <b>%s</b>\n" % _name(user_id))
    L.append("📊 <b>تقرير أدائك — %s</b>\n"
             % (label or ("آخر %d أيام" % days)))
    for mk, name in (("futures", "⚡ العقود الآجلة"), ("spot", "🪙 الفوريّ")):
        d = s["markets"][mk]
        if not d["n"] and not d["open"]:
            continue
        L.append("<b>%s</b>" % name)
        L.append("  الصفقات المغلقة: %d" % d["n"])
        if d["n"]:
            L.append("  الرابحة: %d (%.0f%%)" % (d["wins"], d["win_rate"]))
            L.append("  الربح الخام: %+.2f$" % d["gross"])
            if d["fees"]:
                L.append("  رسوم المنصّة: -%.2f$" % d["fees"])
            L.append("  <b>الصافي: %+.2f$</b>" % d["net"])
            L.append("  الأفضل: %+.2f%% · الأسوأ: %+.2f%%"
                     % (d["best"], d["worst"]))
        if d["open"]:
            L.append("  مفتوحة الآن: %d" % d["open"])
        L.append("")
    L.append("━━━━━━━━━━━━━━")
    L.append("<b>الإجمالي: %+.2f$</b> من %d صفقة"
             % (t["net"], t["n"]))
    if t["fees"]:
        L.append("إجمالي الرسوم: %.2f$" % t["fees"])
    L.append("\n<i>الأرقام من حسابك على المنصّة — لا من محاكاة.</i>")
    return "\n".join(L)


def statement(user_id, days=3650, ar=True, frm=None, to=None):
    """🏦 كشف حساب كامل — كل صفقة بتفاصيلها ثم الاجمالي.

    كالكشف البنكيّ: الرصيد الابتدائيّ · كل حركة · والرصيد النهائيّ.
    """
    since, until = _range(days, frm, to)
    try:
        c = sqlite3.connect(DB)
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT market, symbol, direction, entry, exit_price, qty, "
            "leverage, pnl_pct, pnl_usdt, commission, net_usdt, "
            "close_reason, opened_at, closed_at, status FROM user_trades "
            "WHERE user_id=? AND COALESCE(opened_at,0) > ? "
            "AND COALESCE(opened_at,0) <= ? "
            "ORDER BY COALESCE(opened_at,0) ASC",
            (str(user_id), since, until))]
        c.close()
    except Exception:
        return "تعذّر جلب الكشف."

    nm = _name(user_id)
    if not rows:
        return "👋 أهلاً <b>%s</b>\n\n🏦 لا حركات في حسابك بعد." % nm

    L = ["🏦 <b>كشف حساب — %s</b>" % nm]
    first = min(int(r["opened_at"] or 0) for r in rows)
    L.append("📅 من %s حتى اليوم" % _dt(first))
    L.append("━━━━━━━━━━━━━━━━━━━━\n")

    run = 0.0
    closed = [r for r in rows if r["status"] == "closed"]
    opn = [r for r in rows if r["status"] != "closed"]

    for i, r in enumerate(closed, 1):
        mk = "⚡" if (r["market"] or "futures") == "futures" else "🪙"
        net = float(r["net_usdt"] if r["net_usdt"] is not None
                    else (r["pnl_usdt"] or 0))
        run += net
        L.append("<b>%d. %s %s %s</b>" % (i, mk, r["symbol"],
                                          r["direction"] or ""))
        L.append("   دخول %s ← خروج %s" % (_p(r["entry"]),
                                            _p(r["exit_price"])))
        if r["qty"]:
            L.append("   الكمّية %s%s" % (_p(r["qty"]),
                     (" · رافعة %.0fx" % float(r["leverage"] or 1))
                     if (r["leverage"] or 1) > 1 else ""))
        L.append("   النتيجة %+.2f%% (%+.2f$)"
                 % (float(r["pnl_pct"] or 0), float(r["pnl_usdt"] or 0)))
        if r["commission"]:
            L.append("   رسوم المنصّة -%.4f$" % float(r["commission"]))
        L.append("   <b>الصافي %+.2f$</b> · الرصيد التراكميّ %+.2f$"
                 % (net, run))
        if r["close_reason"]:
            L.append("   السبب: %s" % _reason(r["close_reason"]))
        L.append("   %s ← %s" % (_dt(r["opened_at"]), _dt(r["closed_at"])))
        L.append("")

    if opn:
        L.append("━━━ 🔓 مفتوحة الآن ━━━")
        for r in opn:
            mk = "⚡" if (r["market"] or "futures") == "futures" else "🪙"
            L.append("%s %s %s · دخول %s · %s"
                     % (mk, r["symbol"], r["direction"] or "",
                        _p(r["entry"]), _dt(r["opened_at"])))
        L.append("")

    g = sum(float(r["pnl_usdt"] or 0) for r in closed)
    f = sum(float(r["commission"] or 0) for r in closed)
    w = len([r for r in closed if (r["pnl_pct"] or 0) > 0])
    L.append("━━━━━━━━━━━━━━━━━━━━")
    L.append("<b>📊 الإجمالي</b>")
    L.append("الصفقات المغلقة: %d" % len(closed))
    if closed:
        L.append("الرابحة: %d · الخاسرة: %d (نجاح %.0f%%)"
                 % (w, len(closed) - w, w / len(closed) * 100))
    L.append("الربح الخام: %+.2f$" % g)
    L.append("رسوم المنصّة: -%.2f$" % f)
    L.append("<b>الصافي النهائيّ: %+.2f$</b>" % run)
    if opn:
        L.append("مفتوحة الآن: %d" % len(opn))
    L.append("\n<i>كل رقم من حسابك على المنصّة — لا محاكاة.</i>")
    return "\n".join(L)


def _p(v):
    if v is None:
        return "—"
    try:
        v = float(v)
    except Exception:
        return "—"
    if v == 0:
        return "0"
    return ("%.8f" % v).rstrip("0").rstrip(".") if v < 0.01 else "%.4f" % v


def _dt(ts):
    if not ts:
        return "—"
    import datetime as _d
    return _d.datetime.fromtimestamp(int(ts) + 14400).strftime("%d/%m %H:%M")


_R = {"harvest": "🌾 حصاد", "tp1": "🎯 هدف أوّل", "tp2": "🎯 هدف ثانٍ",
      "tp3": "🎯 هدف ثالث", "sl_hit": "🛑 وقف الخسارة",
      "tactical_exit": "⚡ خروج تكتيكيّ", "early_bleed": "🩸 نزيف مبكّر",
      "flow_flip": "🌊 انقلاب التدفّق", "spot_exit": "🪙 بيع",
      "manual": "✋ يدويّ", "trail": "📉 وقف متحرّك"}


def _reason(k):
    return _R.get(str(k or "").lower().strip(), str(k))
