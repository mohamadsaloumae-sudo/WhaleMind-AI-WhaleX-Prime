"""🔔 إشعارات مفصولة لكل سوق — فيوتشر / سبوت / ميم."""
import sqlite3
import time
import re
import logging

log = logging.getLogger("notifier")
DB = "/opt/whalex/db/whalex.db"


def _ensure():
    try:
        c = sqlite3.connect(DB)
        c.execute("CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY, event TEXT, message TEXT, message_en TEXT, created_at INTEGER)")
        try:
            c.execute("ALTER TABLE notifications ADD COLUMN market TEXT DEFAULT 'futures'")
        except Exception:
            pass
        c.commit(); c.close()
    except Exception as e:
        log.debug("ensure: %s", e)


async def push_note(market: str, event: str, message: str, message_en: str = None):
    """يحفظ الإشعار لسوقه ويبثّه حياً."""
    clean = re.sub(r"<[^>]+>", "", message or "").strip()
    clean_en = re.sub(r"<[^>]+>", "", message_en).strip() if message_en else None
    _ensure()
    try:
        c = sqlite3.connect(DB)
        c.execute("INSERT INTO notifications (event, message, message_en, created_at, market) VALUES (?,?,?,?,?)",
                  (event, clean, clean_en, int(time.time()), market))
        c.commit(); c.close()
    except Exception as e:
        log.debug("save: %s", e)
    try:
        from routers.ws import registry
        _pro_only = event in ("signal", "opened", "closed", "position_closed",
                              "sl_warning", "trailing_active", "alert")
        await registry.broadcast({"event": event, "market": market, "pro_only": _pro_only,
                                  "message": clean,
                                  "message_en": clean_en, "data": {}})
    except Exception as e:
        log.debug("ws: %s", e)
