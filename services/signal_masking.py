"""🔒 إخفاء تفاصيل الإشارات عن غير المشتركين — في الخادم لا الواجهة.

الإخفاء في الواجهة تجميلي: من يفتح /api/signals مباشرةً يرى كل شيء.
الحماية الحقيقية أن الخادم لا يُرسل التفاصيل أصلاً.
"""
import logging
import sqlite3
import time

log = logging.getLogger("masking")
DB = "/opt/whalex/db/whalex.db"
HIDE = ("symbol", "entry", "sl", "tp1", "tp2", "tp3", "address", "url")


def user_plan(uid: str) -> str:
    """paid · trial · free"""
    try:
        cn = sqlite3.connect(DB)
        cn.row_factory = sqlite3.Row
        r = cn.execute(
            "SELECT plan, expires_at FROM subscriptions WHERE user_id=? "
            "ORDER BY expires_at DESC LIMIT 1", (str(uid),)).fetchone()
        t = cn.execute("SELECT tier FROM users WHERE id=?", (str(uid),)).fetchone()
        cn.close()
        if t and str(t[0]).lower() == "admin":
            return "paid"
        if not r or (r["expires_at"] or 0) < time.time():
            return "free"
        return "trial" if str(r["plan"]).lower() == "trial" else "paid"
    except Exception as e:
        log.debug("plan %s: %s", uid, e)
        return "free"


def mask_for(uid: str, rows: list) -> list:
    """يُرجع الإشارات كما هي للمشترك، ومحجوبة التفاصيل لغيره."""
    if user_plan(uid) == "paid":
        return rows
    out = []
    for r in rows:
        d = dict(r)
        for k in HIDE:
            if k in d and d[k] is not None:
                d[k] = "•••••" if isinstance(d[k], str) else None
        d["locked"] = True
        out.append(d)
    return out
