"""🎁 التجربة المجانية — أسبوع كامل بحماية من الاستغلال.

الحماية ثلاث طبقات:
  • بصمة الجهاز  — نفس الجوّال لا يأخذ تجربتين
  • مفتاح المنصّة — الأقوى: يحتاج حساب تداول موثّق لكل تجربة
  • عنوان IP     — تحذير للإدارة لا رفض (العائلة تشترك فيه)
"""
import hashlib
import logging
import sqlite3
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from routers.auth import get_current_user

router = APIRouter(prefix="/api/trial", tags=["trial"])
log = logging.getLogger("trial")

DB = "/opt/whalex/db/whalex.db"
TRIAL_DAYS = 7


def _init():
    cn = sqlite3.connect(DB)
    cn.execute("""
        CREATE TABLE IF NOT EXISTS trial_guard (
            user_id     TEXT PRIMARY KEY,
            fingerprint TEXT,
            ip          TEXT,
            api_hash    TEXT,
            started_at  INTEGER,
            expires_at  INTEGER
        )
    """)
    for col in ("fingerprint", "ip", "api_hash"):
        cn.execute(f"CREATE INDEX IF NOT EXISTS ix_tg_{col} ON trial_guard({col})")
    cn.commit()
    cn.close()


_init()


def api_fingerprint(api_key: str) -> str:
    """بصمة مفتاح المنصّة — لا نخزّن المفتاح نفسه."""
    return hashlib.sha256(str(api_key or "").encode()).hexdigest()[:32]


@router.get("/status")
async def status(user=Depends(get_current_user)):
    """حالة تجربة المستخدم وأيامها المتبقّية."""
    cn = sqlite3.connect(DB)
    cn.row_factory = sqlite3.Row
    r = cn.execute("SELECT * FROM trial_guard WHERE user_id=?",
                   (str(user["sub"]),)).fetchone()
    cn.close()
    if not r:
        return {"active": False, "used": False, "days_left": 0}
    left = max(0, int((r["expires_at"] - time.time()) / 86400))
    return {
        "active": r["expires_at"] > time.time(),
        "used": True,
        "days_left": left,
        "expires_at": r["expires_at"],
    }


@router.post("/start")
async def start(request: Request, user=Depends(get_current_user)):
    """يبدأ التجربة — يرفض من استهلكها بجهازه أو بمفتاح منصّته."""
    uid = str(user["sub"])
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    fp = str(body.get("fingerprint") or "")[:120]
    ip = (request.client.host if request.client else "") or ""

    cn = sqlite3.connect(DB)
    cn.row_factory = sqlite3.Row

    if cn.execute("SELECT 1 FROM trial_guard WHERE user_id=?", (uid,)).fetchone():
        cn.close()
        raise HTTPException(400, "استُخدمت تجربتك المجانية من قبل")

    # 🔒 بصمة الجهاز
    if fp and cn.execute("SELECT 1 FROM trial_guard WHERE fingerprint=?",
                         (fp,)).fetchone():
        cn.close()
        log.warning("🎁 رفض تجربة: بصمة مكرّرة uid=%s", uid)
        raise HTTPException(400, "هذا الجهاز استخدم تجربة مجانية من قبل")

    # 🔒 مفتاح المنصّة — الأقوى
    api_hash = ""
    try:
        from services.binance_trader import get_credentials
        c = get_credentials(uid)
        if c and c.get("api_key"):
            api_hash = api_fingerprint(c["api_key"])
            if cn.execute("SELECT 1 FROM trial_guard WHERE api_hash=?",
                          (api_hash,)).fetchone():
                cn.close()
                log.warning("🎁 رفض تجربة: مفتاح منصّة مكرّر uid=%s", uid)
                raise HTTPException(400, "حساب المنصّة هذا استخدم تجربة من قبل")
    except HTTPException:
        raise
    except Exception as e:
        log.debug("🎁 فحص المفتاح: %s", e)

    # ⚠️ الـIP: تحذير للإدارة لا رفض
    if ip:
        n = cn.execute("SELECT COUNT(*) FROM trial_guard WHERE ip=?", (ip,)).fetchone()[0]
        if n:
            log.warning("🎁 تنبيه: %d تجربة سابقة من %s (uid=%s)", n, ip, uid)

    now = int(time.time())
    exp = now + TRIAL_DAYS * 86400
    cn.execute("INSERT INTO trial_guard VALUES(?,?,?,?,?,?)",
               (uid, fp, ip, api_hash, now, exp))
    cn.execute("INSERT INTO subscriptions(user_id, plan, expires_at, created_at) "
               "VALUES(?,?,?,?)", (uid, "trial", exp, now))
    cn.execute("UPDATE users SET tier='trial' WHERE id=?", (uid,))
    cn.commit()
    cn.close()
    log.info("🎁 بدأت تجربة %s — %d أيام", uid, TRIAL_DAYS)
    return {"success": True, "days": TRIAL_DAYS, "expires_at": exp}
