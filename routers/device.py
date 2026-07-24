"""📱 قفل الجهاز الواحد — جلسة واحدة نشطة لكل حساب."""
import sqlite3
import time
import logging
from fastapi import APIRouter, Depends
from routers.auth import get_current_user
from pydantic import BaseModel

log = logging.getLogger("device")
router = APIRouter()
DB = "/opt/whalex/db/whalex.db"


def _init():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS active_devices(
        user_id TEXT PRIMARY KEY, device_id TEXT, ua TEXT,
        last_seen INTEGER, since INTEGER)""")
    c.commit(); c.close()


class DevBody(BaseModel):
    user_id: str
    device_id: str
    ua: str = ""


@router.post("/api/device/register")
async def register(body: DevBody, user=Depends(get_current_user)):
    """يسجّل الجهاز الحالي ويُبطل أي جهاز سابق."""
    _init()
    body.user_id = user.get("sub") or body.user_id
    now = int(time.time())
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        row = c.execute("SELECT device_id FROM active_devices WHERE user_id=?", (body.user_id,)).fetchone()
        prev = dict(row).get("device_id") if row else None
        replaced = bool(prev and prev != body.device_id)
        c.execute("INSERT OR REPLACE INTO active_devices(user_id,device_id,ua,last_seen,since) VALUES(?,?,?,?,?)",
                  (body.user_id, body.device_id, body.ua[:180], now, now))
        c.commit(); c.close()
    except Exception as e:
        log.warning("register: %s", e)
        return {"ok": True, "replaced": False}
    if replaced:
        try:
            from routers.ws import registry
            await registry.broadcast({
                "event": "device_kick", "market": "futures",
                "target_device": prev, "user_id": body.user_id,
                "message": "🔒 تم فتح حسابك على جهاز آخر — أُغلقت الجلسة هنا.",
                "message_en": "🔒 Your account was opened on another device — this session was closed.",
            })
        except Exception as e:
            log.debug("kick broadcast: %s", e)
        log.info("📱 جهاز جديد لـ %s — أُبطل السابق", body.user_id)
    return {"ok": True, "replaced": replaced}


@router.get("/api/device/check")
async def check(device_id: str, user=Depends(get_current_user)):
    """هل هذا الجهاز ما زال الجلسة المعتمدة؟"""
    _init()
    user_id = user.get("sub")
    if not user_id:
        return {"valid": True}
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        row = c.execute("SELECT device_id FROM active_devices WHERE user_id=?", (user_id,)).fetchone()
        c.close()
        if not row:
            return {"valid": True}
        cur = dict(row).get("device_id")
        if cur and cur != device_id:
            return {"valid": False, "reason": "another_device"}
        try:
            c = sqlite3.connect(DB)
            c.execute("UPDATE active_devices SET last_seen=? WHERE user_id=?", (int(time.time()), user_id))
            c.commit(); c.close()
        except Exception:
            pass
        return {"valid": True}
    except Exception:
        return {"valid": True}
