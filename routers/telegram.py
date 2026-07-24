from fastapi import APIRouter, Request
from core.config import get_settings
from services.telegram import TG, set_webhook

router = APIRouter(prefix="/telegram", tags=["Telegram"])

@router.post("/webhook")
async def webhook(request: Request):
    try:
        update = await request.json()
        # 🔎 كشف معرّفات القنوات: يسجّل أي قناة/مجموعة يستقبل منها
        try:
            import logging as _lg
            for _k in ("channel_post", "edited_channel_post", "message", "my_chat_member"):
                _ch = ((update.get(_k) or {}).get("chat") or {})
                if _ch.get("id") and str(_ch.get("type")) in ("channel", "supergroup", "group"):
                    _lg.getLogger("telegram").info(
                        "🔎 قناة: id=%s | نوع=%s | العنوان=%s",
                        _ch.get("id"), _ch.get("type"), _ch.get("title"))
        except Exception:
            pass
        await TG.handle_update(update)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.post("/setup-webhook")
async def setup():
    s = get_settings()
    if not s.telegram_bot_token:
        return {"error": "TELEGRAM_BOT_TOKEN not set"}
    base = s.telegram_mini_app_url.rstrip("/")
    url = f"{base}/telegram/webhook"
    result = await set_webhook(url)
    return {"webhook_url": url, "result": result}

@router.get("/info")
def info():
    s = get_settings()
    return {
        "bot_token_set": bool(s.telegram_bot_token),
        "channel_futures": bool(s.telegram_channel_futures),
        "channel_spot": bool(s.telegram_channel_spot),
        "channel_meme": bool(s.telegram_channel_meme),
        "admin_set": bool(s.telegram_admin_chat_id),
        "mini_app_url": s.telegram_mini_app_url,
    }
