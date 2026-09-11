"""🔍 تشخيص ما لم يُفتح — لا نخفيه بل نعالجه.

كل اشارة فشل تنفيذها لها سبب مسجل في auto_trade_logs. نجمعها
بالسبب، ونقيس اين وصل السعر بعدها لنعرف: كم كلفنا كل سبب.

مقيس 11 سبتمبر: 48 اشارة لم تُنفذ، صافيها +32.1% — اي فاتنا ربح.
والاسباب: 63 منعا برصيد صفر · 38 عملة غير مدرجة · 4 عابرة.
"""
import re
import time
import sqlite3
import logging
import collections
from fastapi import APIRouter

log = logging.getLogger("admin_missed")
router = APIRouter(prefix="/api/admin", tags=["admin-missed"])
DB = "/opt/whalex/db/whalex.db"
ML = "/opt/whalex/ml_training.db"


def _norm(msg: str) -> tuple:
    """يوحّد رسالة الخطأ الى فئة + نص قابل للفهم + هل هو قابل للعلاج."""
    m = str(msg or "").strip()
    if "margin_guard" in m:
        return ("رصيد غير كافٍ", "المشترك فعّل التداول الآليّ ورصيده صفر", "user")
    if "لا حساب مربوط" in m:
        sym = (re.search(r"فيه (\S+)", m) or [None, "?"])[1]
        return ("عملة غير مدرجة", f"{sym} غير موجودة على منصّة أي مشترك", "coverage")
    if "auto_trade_disabled" in m:
        return ("التداول معطّل", "المشترك أوقف التداول الآليّ", "user")
    if "-2015" in m or "Invalid API-key" in m:
        return ("مفاتيح مرفوضة", "المفاتيح أو عنوان الخادم غير مصرّح", "keys")
    if "-1003" in m or "too many requests" in m.lower():
        return ("حدّ الطلبات", "تجاوزنا حدّ باينانس مؤقّتاً", "system")
    if "timeout" in m.lower() or "no fill" in m.lower():
        return ("لم يُملأ الأمر", "الأمر الحدّيّ لم يجد سعراً", "system")
    if "تعذّر جلب المراكز" in m:
        return ("تعذّر القراءة", "فشل جلب المراكز من المنصّة", "system")
    if "hourly_cap" in m or "سقف ساعيّ" in m:
        return ("السقف الساعيّ", "بلغنا حدّ ثلاث صفقات في الساعة", "design")
    return ("أخرى", m[:70] or "بلا رسالة", "unknown")


FIXABLE = {
    "user": "يُعالَج بتنبيه المشترك",
    "coverage": "يُعالَج بتوسيع المنصّات أو تصفية العملة",
    "keys": "يُعالَج بإرشاد المشترك لتصحيح المفاتيح",
    "system": "عطل تقنيّ عندنا — يحتاج إصلاحاً",
    "design": "قرار تصميميّ مقصود",
    "unknown": "يحتاج فحصاً",
}


def missed(user_id: str = "", days: int = 7) -> dict:
    since = time.strftime("%Y-%m-%dT%H:%M:%S",
                          time.localtime(time.time() - days * 86400))
    c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    c.row_factory = sqlite3.Row
    q = ("SELECT * FROM auto_trade_logs WHERE executed=0 AND created_at >= ?")
    a = [since]
    if user_id:
        q += " AND user_id=?"
        a.append(user_id)
    q += " ORDER BY id DESC LIMIT 2000"
    rows = [dict(r) for r in c.execute(q, a)]

    ok = c.execute(
        "SELECT COUNT(*) FROM auto_trade_logs WHERE executed=1 AND created_at >= ?"
        + (" AND user_id=?" if user_id else ""),
        tuple(a)).fetchone()[0]
    c.close()

    # نتيجة كل اشارة من سجل النظام
    m = sqlite3.connect("file:%s?mode=ro" % ML, uri=True)
    res = {}
    for sym, d, pnl, ts in m.execute(
            "SELECT symbol, direction, pnl_pct, timestamp FROM training_signals "
            "WHERE pnl_pct IS NOT NULL AND timestamp >= ?",
            (int(time.time()) - days * 86400,)):
        res.setdefault((sym, str(d).upper()), []).append((ts, pnl))
    m.close()

    def outcome(r):
        try:
            t = int(time.mktime(time.strptime(
                str(r["created_at"])[:19], "%Y-%m-%dT%H:%M:%S")))
        except Exception:
            return None
        hits = res.get((r["signal_symbol"], str(r["signal_direction"]).upper()), [])
        near = [p for ts, p in hits if abs(ts - t) < 900]
        return near[0] if near else None

    groups = collections.defaultdict(lambda: {"n": 0, "pnl": 0.0, "wins": 0,
                                              "resolved": 0, "samples": []})
    for r in rows:
        cat, desc, kind = _norm(r.get("error_message"))
        g = groups[cat]
        g["n"] += 1
        g["desc"] = desc
        g["kind"] = kind
        g["fix"] = FIXABLE.get(kind, "")
        p = outcome(r)
        if p is not None:
            g["resolved"] += 1
            g["pnl"] += p
            if p > 0:
                g["wins"] += 1
        if len(g["samples"]) < 6:
            g["samples"].append({
                "symbol": r["signal_symbol"],
                "direction": r["signal_direction"],
                "at": str(r["created_at"])[:19].replace("T", " "),
                "user": str(r["user_id"])[:8],
                "pnl_pct": p,
            })

    out = []
    for cat, g in sorted(groups.items(), key=lambda x: -x[1]["n"]):
        out.append({
            "reason": cat, "desc": g.get("desc", ""), "kind": g.get("kind", ""),
            "fix": g.get("fix", ""), "count": g["n"], "resolved": g["resolved"],
            "win_rate": round(g["wins"] * 100 / g["resolved"], 1) if g["resolved"] else None,
            "pnl_sum": round(g["pnl"], 1),
            "cost_usd": round(g["pnl"] / 100 * 25, 2),
            "samples": g["samples"],
        })

    tot_pnl = sum(x["pnl_sum"] for x in out)
    return {
        "days": days,
        "executed": ok,
        "failed": len(rows),
        "exec_rate": round(ok * 100 / max(1, ok + len(rows)), 1),
        "missed_pnl_pct": round(tot_pnl, 1),
        "missed_usd": round(tot_pnl / 100 * 25, 2),
        "reasons": out,
        "generated_at": int(time.time()),
    }


@router.get("/missed")
async def api_missed(user_id: str = "", days: int = 7):
    try:
        return missed(user_id, days)
    except Exception as e:
        log.error("missed: %s", e)
        return {"error": str(e)[:150], "reasons": []}
