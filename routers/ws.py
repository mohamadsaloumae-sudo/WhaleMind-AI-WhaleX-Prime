"""
WhaleMind-Prime-Core — ws.py
═══════════════════════════════════════════════════════════════════
معمارية Redis Pub/Sub — بدون أي عنق زجاجة

المشكلة القديمة:
  كل مستخدم → while True → get_all_prices() × 1000 مستخدم = انهيار

الحل الجديد:
  مهمة مركزية واحدة → Redis Publish
  كل مستخدم → Redis Subscribe → يستقبل فقط بدون عمل

التدفق:
  price_broadcaster() ──→ Redis "whalex:prices"
                                    ↓
  client1 ──subscribe──→ يستقبل فوراً
  client2 ──subscribe──→ يستقبل فوراً
  client3 ──subscribe──→ يستقبل فوراً
  (1000 مستخدم = نفس الحمل على السيرفر)

Fallback: إذا Redis غير متاح → asyncio.Queue محلي (يعمل تلقائياً)
═══════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import asyncio, json, logging, time
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger("whalex.ws")
router = APIRouter()

# ═══════════════════════════════════════════════════════════════
# ─── REDIS MANAGER — مع Fallback تلقائي ────────────────────────
# ═══════════════════════════════════════════════════════════════

class RedisManager:
    """
    يدير اتصال Redis مع fallback لـ asyncio.Queue
    إذا Redis غير متاح → يعمل محلياً بدون أي تغيير في الكود
    """
    PRICES_CHANNEL = "whalex:prices"
    SIGNALS_CHANNEL = "whalex:signals"

    def __init__(self):
        self._redis = None
        self._pubsub = None
        self._available = False
        self._local_queue: asyncio.Queue = asyncio.Queue(maxsize=50)

    async def connect(self):
        try:
            import redis.asyncio as aioredis
            self._redis = await aioredis.from_url(
                "redis://localhost:6379",
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            await self._redis.ping()
            self._available = True
            log.info("✅ Redis متصل — Pub/Sub مفعّل")
        except Exception as e:
            self._available = False
            log.warning("⚠️ Redis غير متاح (%s) — Fallback إلى Local Queue", e)

    async def publish(self, channel: str, data: dict):
        msg = json.dumps(data, ensure_ascii=False)
        if self._available and self._redis:
            try:
                await self._redis.publish(channel, msg)
                return
            except Exception as e:
                log.debug("Redis publish error: %s", e)
        # Fallback
        try:
            self._local_queue.put_nowait({"channel": channel, "data": data})
        except asyncio.QueueFull:
            pass  # تجاهل إذا ممتلئة

    async def subscribe_prices(self):
        """Generator — يعيد الأسعار عند وصولها"""
        if self._available and self._redis:
            try:
                pubsub = self._redis.pubsub()
                await pubsub.subscribe(self.PRICES_CHANNEL, self.SIGNALS_CHANNEL)
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            yield json.loads(message["data"])
                        except:
                            pass
                return
            except Exception as e:
                log.warning("Redis subscribe error: %s — Fallback", e)

        # Fallback — Local Queue
        while True:
            try:
                item = await asyncio.wait_for(self._local_queue.get(), timeout=5.0)
                yield item["data"]
            except asyncio.TimeoutError:
                continue

    @property
    def is_available(self):
        return self._available


# Singleton
redis_mgr = RedisManager()

# ═══════════════════════════════════════════════════════════════
# ─── CLIENT REGISTRY — بدون while True لكل مستخدم ─────────────
# ═══════════════════════════════════════════════════════════════

class ClientRegistry:
    """
    إدارة المستخدمين المتصلين:
    - كل مستخدم يُسجَّل هنا فقط
    - البث يأتي من المهمة المركزية
    - لا while True لكل مستخدم
    """
    def __init__(self):
        self._clients: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def add(self, ws_id: str, ws: WebSocket):
        async with self._lock:
            self._clients[ws_id] = ws
        log.info("WS connected: %s — total: %d", ws_id, len(self._clients))

    async def remove(self, ws_id: str):
        async with self._lock:
            self._clients.pop(ws_id, None)
        log.info("WS disconnected: %s — total: %d", ws_id, len(self._clients))

    async def send_to_user(self, user_id: str, data: dict):
        """🔒 إرسال موجّه — ردّ الدعم يخصّ صاحبه وحده لا كل المتصلين."""
        if not self._clients or not user_id:
            return
        msg = json.dumps(data, ensure_ascii=False)
        async with self._lock:
            snap = list(self._clients.items())
        for wid, ws in snap:
            if str(user_id) not in str(wid):
                continue
            try:
                await ws.send_text(msg)
            except Exception:
                pass

    async def broadcast(self, data: dict):
        """
        بث لكل المتصلين دفعة واحدة — non-blocking
        المتصلون الميتون يُحذفون تلقائياً
        """
        if not self._clients:
            return

        msg = json.dumps(data, ensure_ascii=False)
        dead = []

        async with self._lock:
            clients_snapshot = list(self._clients.items())

        # إرسال متوازٍ لكل المستخدمين
        async def send_one(ws_id: str, ws: WebSocket):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws_id)

        await asyncio.gather(
            *[send_one(wid, ws) for wid, ws in clients_snapshot],
            return_exceptions=True
        )

        # تنظيف الاتصالات الميتة
        if dead:
            async with self._lock:
                for ws_id in dead:
                    self._clients.pop(ws_id, None)
            log.debug("Cleaned %d dead connections", len(dead))

    @property
    def count(self) -> int:
        return len(self._clients)


# Singleton
registry = ClientRegistry()


@router.get("/api/notifications")
async def get_notifications(limit: int = 50, market: str = "futures"):
    """يرجع آخر الإشعارات المخزّنة (للجرس عند فتح الصفحة)"""
    import sqlite3
    conn = sqlite3.connect("/opt/whalex/db/whalex.db")
    try:
        conn.execute("ALTER TABLE notifications ADD COLUMN market TEXT DEFAULT 'futures'")
        conn.commit()
    except Exception:
        pass
    rows = conn.execute(
        "SELECT id, event, message, message_en, created_at FROM notifications "
        "WHERE COALESCE(market,'futures')=? ORDER BY id DESC LIMIT ?",
        (market, limit)
    ).fetchall()
    conn.close()
    return {
        "notifications": [
            {"id": r[0], "event": r[1], "message": r[2], "message_en": r[3], "created_at": r[4]}
            for r in rows
        ]
    }

@router.get("/api/test-bell")
async def test_bell():
    """مسار اختبار مؤقّت — يبثّ إشعاراً تجريبياً للجرس"""
    await registry.broadcast({
        "event": "test",
        "message": "🐋 اختبار الجرس — WhaleX Prime يعمل!",
        "data": {},
    })
    return {"sent": True, "clients": len(registry._clients) if hasattr(registry, "_clients") else "?"}

# ═══════════════════════════════════════════════════════════════
# ─── PRICE BROADCASTER — مهمة مركزية واحدة ─────────────────────
# ═══════════════════════════════════════════════════════════════

_broadcaster_started = False

async def price_broadcaster():
    """
    المهمة المركزية الوحيدة لجلب الأسعار:
    - تعمل مرة واحدة فقط عند إقلاع السيرفر
    - تجلب الأسعار كل 3 ثوانٍ مرة واحدة لكل العالم
    - تنشر عبر Redis → يستقبل كل المتصلين فوراً

    المبدأ: 1 استدعاء API × عدد لانهائي من المستخدمين
    """
    global _broadcaster_started
    if _broadcaster_started:
        return
    _broadcaster_started = True

    log.info("Price Broadcaster started — WhaleMind-Prime-Core")

    while True:
        try:
            from services.prices import get_all_prices
            prices = get_all_prices()

            if prices:
                payload = {
                    "event": "prices",
                    "data": prices,
                    "ts": int(time.time())
                }
                # نشر عبر Redis (أو Local Queue كـ fallback)
                await redis_mgr.publish(redis_mgr.PRICES_CHANNEL, payload)

        except Exception as e:
            log.error("Broadcaster error: %s", e)

        await asyncio.sleep(3)


async def redis_to_ws_relay():
    """
    يستقبل من Redis ويبث لكل المتصلين عبر WebSocket
    هذه الدالة تعمل كـ relay بين Redis وبين العملاء
    """
    log.info("Redis→WS Relay started")
    async for data in redis_mgr.subscribe_prices():
        try:
            if registry.count > 0:
                await registry.broadcast(data)
        except Exception as e:
            log.error("Relay error: %s", e)


async def start_broadcaster():
    """
    نقطة تشغيل المهام المركزية — تُستدعى مرة واحدة عند إقلاع السيرفر
    """
    await redis_mgr.connect()
    asyncio.create_task(price_broadcaster(), name="price_broadcaster")
    asyncio.create_task(redis_to_ws_relay(), name="redis_ws_relay")
    log.info("WhaleMind-Prime-Core WS services started")


# ═══════════════════════════════════════════════════════════════
# ─── WEBSOCKET ENDPOINT ─────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def _uid_from_token(tok: str) -> str:
    """🔑 معرّف المستخدم من رمز الدخول — لتوجيه الرسائل الخاصّة."""
    if not tok:
        return ""
    try:
        from jose import jwt as _jwt
        from core.config import get_settings
        p = _jwt.decode(tok, get_settings().secret_key, algorithms=["HS256"])
        return str(p.get("sub") or "")
    except Exception:
        return ""


@router.websocket("/ws/live")
async def ws_live(ws: WebSocket, token: str = ""):
    """
    اتصال المستخدم — بدون أي عمل حقيقي هنا:
    1. قبول الاتصال
    2. إرسال snapshot فوري للأسعار الحالية
    3. التسجيل في Registry
    4. الانتظار (ping/pong فقط) — البيانات تأتي من المهمة المركزية

    لا get_all_prices() هنا → لا bottleneck
    """
    _uid = _uid_from_token(token)
    ws_id = (f"u:{_uid}:{int(time.time() * 1000)}" if _uid
             else f"client_{int(time.time() * 1000)}_{id(ws)}")

    await ws.accept()
    await registry.add(ws_id, ws)

    # إرسال snapshot فوري للأسعار الحالية
    try:
        from services.prices import get_all_prices
        prices = get_all_prices()
        if prices:
            await ws.send_text(json.dumps({
                "event": "prices",
                "data": prices,
                "ts": int(time.time())
            }))
    except Exception as e:
        log.debug("Initial snapshot error: %s", e)

    try:
        # المستخدم ينتظر فقط — البيانات تأتيه من Redis Relay
        # ping/pong للحفاظ على الاتصال
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
                # إذا أرسل المستخدم شيئاً (مثل subscribe لرمز معين)
                if msg:
                    await _handle_client_message(ws_id, ws, msg)
            except asyncio.TimeoutError:
                # ping للتأكد من أن الاتصال حي
                await ws.send_text(json.dumps({"event": "ping", "ts": int(time.time())}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.debug("WS %s error: %s", ws_id, e)
    finally:
        await registry.remove(ws_id)


async def _handle_client_message(ws_id: str, ws: WebSocket, msg: str):
    """
    معالجة رسائل المستخدم (اختياري):
    - subscribe: الاشتراك في رمز معين
    - pong: رد على ping
    """
    try:
        data = json.loads(msg)
        event = data.get("event", "")

        if event == "pong":
            pass  # تجاهل — الاتصال حي

        elif event == "subscribe":
            # المستخدم يريد متابعة رمز معين
            symbol = data.get("symbol", "")
            if symbol:
                log.debug("WS %s subscribed to %s", ws_id, symbol)
                await ws.send_text(json.dumps({
                    "event": "subscribed",
                    "symbol": symbol
                }))

    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# ─── SIGNAL BROADCASTER — إرسال الإشارات لكل المتصلين ──────────
# ═══════════════════════════════════════════════════════════════

async def broadcast_signal(sig: dict):
    """
    إرسال إشارة جديدة لكل المتصلين عبر Redis
    يُستدعى من service.py عند صدور إشارة جديدة
    """
    payload = {
        "event": "signal",
        "data": sig,
        "ts": int(time.time())
    }
    # نشر عبر Redis → يصل لكل المتصلين فوراً
    await redis_mgr.publish(redis_mgr.SIGNALS_CHANNEL, payload)
    # بث مباشر أيضاً للمتصلين الحاليين
    await registry.broadcast(payload)
    log.info("Signal broadcast: %s %s to %d clients",
             sig.get("symbol"), sig.get("direction"), registry.count)


async def broadcast(data: dict):
    """دالة عامة للبث — تُستدعى من أي مكان"""
    await redis_mgr.publish(redis_mgr.PRICES_CHANNEL, data)
    await registry.broadcast(data)
