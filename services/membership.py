"""🎟️ عضوية القنوات — روابط مؤقتة بمدة الاشتراك + تذكيرات + إغلاق تلقائي."""
import asyncio
import sqlite3
import time
import logging
from datetime import datetime

log = logging.getLogger("membership")
DB = "/opt/whalex/db/whalex.db"

# سلّم التذكير بالساعات
REMINDERS = (48, 24, 12, 6, 1)


def _channels():
    """القنوات المفعّلة من الإعدادات."""
    out = []
    try:
        from core.config import get_settings
        s = get_settings()
        for attr, name in (("telegram_channel_futures", "الفيوتشر"),
                           ("telegram_spot_channel_id", "السبوت"),
                           ("telegram_channel_meme", "الميم")):
            v = getattr(s, attr, "") or ""
            if str(v).strip():
                out.append((str(v).strip(), name))
    except Exception as e:
        log.warning("channels: %s", e)
    if not out:
        out = [("-1003936494458", "السبوت"), ("-1003918596088", "الميم")]
    return out


def _init():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS channel_invites(
        id INTEGER PRIMARY KEY, user_id TEXT, chat_id TEXT, name TEXT,
        invite_link TEXT, expires_at INTEGER, created_at INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sub_reminders(
        user_id TEXT, hours INTEGER, sent_at INTEGER, PRIMARY KEY(user_id, hours))""")
    c.commit(); c.close()


async def _tg(method: str, payload: dict):
    """نداء مباشر لواجهة تيليجرام."""
    try:
        from core.config import get_settings
        import httpx
        token = get_settings().telegram_bot_token
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
            return r.json()
    except Exception as e:
        log.warning("tg %s: %s", method, e)
        return None


async def issue_links(user_id: str, expires_ts: int):
    """ينشئ روابط دعوة صالحة حتى نهاية الاشتراك (استخدام واحد)."""
    _init()
    out = []
    for chat_id, name in _channels():
        res = await _tg("createChatInviteLink", {
            "chat_id": chat_id,
            "expire_date": int(expires_ts),
            "member_limit": 1,
            "name": f"WhaleX {user_id[:8]}",
        })
        link = ((res or {}).get("result") or {}).get("invite_link")
        if not link:
            log.warning("invite fail %s: %s", name, str(res)[:120])
            continue
        try:
            c = sqlite3.connect(DB)
            c.execute("INSERT INTO channel_invites(user_id,chat_id,name,invite_link,expires_at,created_at) VALUES(?,?,?,?,?,?)",
                      (user_id, chat_id, name, link, int(expires_ts), int(time.time())))
            c.commit(); c.close()
        except Exception as e:
            log.warning("save invite: %s", e)
        out.append({"name": name, "link": link})
    return out


def get_links(user_id: str):
    _init()
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        rows = c.execute("SELECT name, invite_link, expires_at FROM channel_invites "
                         "WHERE user_id=? AND expires_at > ? ORDER BY id DESC", (user_id, int(time.time()))).fetchall()
        c.close()
        seen, out = set(), []
        for r in rows:
            if r["name"] in seen:
                continue
            seen.add(r["name"])
            out.append(dict(r))
        return out
    except Exception:
        return []


def _is_admin(uid) -> bool:
    """الأدمن لا يُطرد أبداً."""
    try:
        from core.config import get_settings
        s = get_settings()
        for a in ("admin_chat_id", "telegram_admin_id", "admin_id", "owner_id"):
            v = getattr(s, a, None)
            if v and str(v).strip() and str(v).strip() == str(uid).strip():
                return True
    except Exception:
        pass
    return False


async def revoke_access(user_id: str):
    """إلغاء الروابط وإخراج العضو من كل القنوات (يمكنه العودة بعد التجديد)."""
    if _is_admin(user_id):
        log.info("🎟️ تخطّي الأدمن %s — لا طرد", user_id)
        return
    tg_id = None
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        r = c.execute("SELECT telegram_id FROM users WHERE id=? OR telegram_id=?", (user_id, user_id)).fetchone()
        tg_id = (dict(r).get("telegram_id") if r else None) or user_id
        rows = c.execute("SELECT chat_id, invite_link FROM channel_invites WHERE user_id=?", (user_id,)).fetchall()
        c.close()
    except Exception:
        rows = []
        tg_id = user_id
    for r in rows:
        d = dict(r)
        await _tg("revokeChatInviteLink", {"chat_id": d["chat_id"], "invite_link": d["invite_link"]})
    if tg_id and not _is_admin(tg_id):
        for chat_id, _ in _channels():
            await _tg("banChatMember", {"chat_id": chat_id, "user_id": int(str(tg_id)) if str(tg_id).lstrip("-").isdigit() else tg_id})
            await asyncio.sleep(0.4)
            await _tg("unbanChatMember", {"chat_id": chat_id, "user_id": int(str(tg_id)) if str(tg_id).lstrip("-").isdigit() else tg_id, "only_if_banned": True})


async def _notify(user_id: str, msg: str):
    try:
        from services.notifier import push_note
        await push_note("futures", "subscription", msg)
    except Exception:
        pass
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        r = c.execute("SELECT telegram_id FROM users WHERE id=? OR telegram_id=?", (user_id, user_id)).fetchone()
        c.close()
        tg = dict(r).get("telegram_id") if r else None
        if tg:
            from services.telegram import send_message
            await send_message(str(tg), msg)
    except Exception:
        pass


def _reminded(user_id: str, hours: int) -> bool:
    try:
        c = sqlite3.connect(DB)
        r = c.execute("SELECT 1 FROM sub_reminders WHERE user_id=? AND hours=?", (user_id, hours)).fetchone()
        c.close()
        return bool(r)
    except Exception:
        return False


def _mark(user_id: str, hours: int):
    try:
        c = sqlite3.connect(DB)
        c.execute("INSERT OR REPLACE INTO sub_reminders(user_id,hours,sent_at) VALUES(?,?,?)",
                  (user_id, hours, int(time.time())))
        c.commit(); c.close()
    except Exception:
        pass


def _clear_reminders(user_id: str):
    try:
        c = sqlite3.connect(DB)
        c.execute("DELETE FROM sub_reminders WHERE user_id=?", (user_id,))
        c.commit(); c.close()
    except Exception:
        pass


async def lifecycle_loop():
    """يفحص كل الاشتراكات: تذكيرات متدرّجة ثم إغلاق."""
    _init()
    log.info("🎟️ Subscription lifecycle started")
    while True:
        try:
            c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
            rows = c.execute("SELECT user_id, MAX(expires_at) AS exp FROM subscriptions GROUP BY user_id").fetchall()
            c.close()
            now = datetime.utcnow()
            for r in rows:
                d = dict(r)
                uid, exp = d.get("user_id"), d.get("exp")
                if not uid or not exp:
                    continue
                try:
                    exp_dt = datetime.fromisoformat(str(exp)) if not isinstance(exp, datetime) else exp
                except Exception:
                    continue
                left_h = (exp_dt - now).total_seconds() / 3600
                if left_h <= 0:
                    # لا نلمس الاشتراكات المنتهية منذ زمن (تفادي طرد جماعي تاريخي)
                    if left_h < -168:
                        continue
                    if _is_admin(uid):
                        continue
                    if not _reminded(uid, 0):
                        _mark(uid, 0)
                        await revoke_access(uid)
                        await _notify(uid, "🔒 <b>انتهى اشتراكك</b>\nأُغلق الوصول للقنوات والتطبيق.\nجدّد الآن لاستعادة كل الخدمات فوراً.")
                        log.info("🎟️ انتهى اشتراك %s — أُغلق الوصول", uid)
                    continue
                _clear_active = False
                for h in REMINDERS:
                    if left_h <= h and not _reminded(uid, h):
                        _mark(uid, h)
                        txt = ("⏰ <b>تذكير تجديد</b>\n"
                               f"يتبقّى على انتهاء اشتراكك: <b>{int(left_h) if left_h >= 1 else 1} ساعة</b>\n"
                               "جدّد قبل الانتهاء لتبقى قنواتك والتطبيق مفتوحة بلا انقطاع.")
                        await _notify(uid, txt)
                        break
        except Exception as e:
            log.warning("lifecycle: %s", e)
        await asyncio.sleep(600)
