"""
WhaleMind — Push Notifications Router
إشعارات تصل لشاشة الهاتف حتى والتطبيق مغلق (Web Push)
"""
from fastapi import APIRouter
from pydantic import BaseModel
import sqlite3, json, logging, time, asyncio

log = logging.getLogger("push")
router = APIRouter(prefix="/api/push", tags=["Push"])

PUSH_DB = "/opt/whalex/push_subs.db"
VAPID_PRIVATE = "/opt/whalex/vapid_private.pem"
try:
    VAPID_PUBLIC = open("/opt/whalex/vapid_public.txt").read().strip()
except Exception:
    VAPID_PUBLIC = ""
VAPID_CLAIMS = {"sub": "mailto:mohamadsaloum.ae@gmail.com"}


def _init_db():
    conn = sqlite3.connect(PUSH_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS push_subs (
            endpoint TEXT PRIMARY KEY,
            subscription TEXT NOT NULL,
            created_at INTEGER
        )
    """)
    conn.commit()
    conn.close()

_init_db()


class SubBody(BaseModel):
    subscription: dict


@router.get("/public-key")
async def public_key():
    """الواجهة تطلب المفتاح العام للاشتراك."""
    return {"public_key": VAPID_PUBLIC}


@router.post("/subscribe")
async def subscribe(body: SubBody):
    """حفظ اشتراك جهاز جديد."""
    sub = body.subscription
    endpoint = sub.get("endpoint")
    if not endpoint:
        return {"ok": False, "error": "no endpoint"}
    conn = sqlite3.connect(PUSH_DB)
    conn.execute(
        "INSERT OR REPLACE INTO push_subs (endpoint, subscription, created_at) VALUES (?,?,?)",
        (endpoint, json.dumps(sub), int(time.time()))
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/unsubscribe")
async def unsubscribe(body: SubBody):
    """إلغاء اشتراك جهاز (زرّ الإيقاف)."""
    endpoint = body.subscription.get("endpoint")
    if endpoint:
        conn = sqlite3.connect(PUSH_DB)
        conn.execute("DELETE FROM push_subs WHERE endpoint=?", (endpoint,))
        conn.commit()
        conn.close()
    return {"ok": True}


def _send_all_sync(title: str, body: str):
    """إرسال متزامن لكل الأجهزة (يعمل في executor حتى لا يحجب)."""
    from pywebpush import webpush, WebPushException
    try:
        conn = sqlite3.connect(PUSH_DB)
        rows = conn.execute("SELECT endpoint, subscription FROM push_subs").fetchall()
        conn.close()
    except Exception as e:
        log.error("push db read: %s", e)
        return
    payload = json.dumps({"title": title, "body": body})
    dead = []
    for endpoint, sub_json in rows:
        try:
            webpush(
                subscription_info=json.loads(sub_json),
                data=payload,
                vapid_private_key=VAPID_PRIVATE,
                vapid_claims=dict(VAPID_CLAIMS),
            )
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code in (404, 410):
                dead.append(endpoint)
            else:
                log.debug("push fail %s: %s", endpoint[:40], e)
        except Exception as e:
            log.debug("push err: %s", e)
    if dead:
        try:
            conn = sqlite3.connect(PUSH_DB)
            for ep in dead:
                conn.execute("DELETE FROM push_subs WHERE endpoint=?", (ep,))
            conn.commit()
            conn.close()
        except Exception:
            pass


async def send_push_to_all(title: str, body: str):
    """تُستدعى من مدير الصفقات والإشارات — إرسال Push لكل الأجهزة."""
    try:
        await asyncio.get_event_loop().run_in_executor(None, _send_all_sync, title, body)
    except Exception as e:
        log.debug("send_push_to_all: %s", e)
