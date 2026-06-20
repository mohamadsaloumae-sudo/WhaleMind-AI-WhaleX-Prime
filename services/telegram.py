from __future__ import annotations
import asyncio, logging
from typing import Any, Dict, Optional
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
from core.config import get_settings

log = logging.getLogger("telegram")
TG_API = "https://api.telegram.org/bot{token}/{method}"

async def _call(method: str, payload: Dict[str, Any]) -> Optional[dict]:
    s = get_settings()
    if not s.telegram_bot_token or not HAS_HTTPX:
        return None
    url = TG_API.format(token=s.telegram_bot_token, method=method)
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url, json=payload)
            j = r.json()
            if not j.get("ok"):
                log.error("TG %s رفض: %s", method, j.get("description"))
            return j
    except Exception as e:
        log.error("TG %s خطأ: %s", method, e)
        return None

async def send_message(chat_id: str, text: str, reply_markup=None) -> Optional[dict]:
    p: Dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup:
        p["reply_markup"] = reply_markup
    return await _call("sendMessage", p)

async def set_webhook(url: str):
    return await _call("setWebhook", {"url": url, "allowed_updates": ["message"], "drop_pending_updates": True})

async def set_commands():
    return await _call("setMyCommands", {"commands": [
        {"command": "start",   "description": "فتح WhaleX Prime"},
        {"command": "status",  "description": "حالة الرادارات"},
        {"command": "signals", "description": "آخر الإشارات"},
        {"command": "demo",    "description": "حساب الديمو"},
        {"command": "help",    "description": "المساعدة"},
    ]})

def _kb():
    """للمحادثات الخاصة — web_app مدعوم"""
    s = get_settings()
    u = s.telegram_mini_app_url or ""
    if not u:
        return {}
    return {"inline_keyboard": [[{"text": "فتح WhaleX Prime", "web_app": {"url": u}}]]}

def _kb_channel():
    """للقنوات — url فقط (web_app غير مدعوم)"""
    s = get_settings()
    u = s.telegram_mini_app_url or ""
    if not u:
        return {}
    return {"inline_keyboard": [[{"text": "🐋 فتح WhaleX Prime", "url": u}]]}

from datetime import datetime, timezone, timedelta

UAE_TZ = timezone(timedelta(hours=4))

def signal_msg(s: dict) -> str:
    """التصميم النهائي — مضغوط وأنيق"""
    radar = s.get("radar_type", "futures").upper()
    sym   = s.get("symbol", "")
    dir_  = s.get("direction", "")
    grade = s.get("grade", "B")
    conf  = s.get("confidence", 0)
    score = s.get("score", 0)
    entry = s.get("entry", 0)
    sl    = s.get("sl", 0)
    tp1   = s.get("tp1", 0)
    tp2   = s.get("tp2", 0)
    tp3   = s.get("tp3", 0)
    lev   = s.get("leverage", 1)
    import html as _html
    strats_raw = s.get("strategies", "")
    _strats0 = strats_raw if isinstance(strats_raw, list) else (strats_raw.split("\n") if strats_raw else [])
    # تهريب HTML: أسماء استراتيجيات فيها رموز مثل (K<D) تكسر parse_mode=HTML وتُفشل البطاقة
    strats = [_html.escape(str(x)) for x in _strats0]

    funding = s.get("funding_rate", 0)
    oi_change = s.get("open_interest_change", 0)
    btc_trend = s.get("btc_trend", "NEUTRAL")
    mtf_15m = s.get("mtf_15m", "NEUTRAL")
    mtf_1h  = s.get("mtf_1h", "NEUTRAL")
    mtf_4h  = s.get("mtf_4h", "NEUTRAL")
    rr_tp1 = s.get("rr_tp1", 0)
    rr_tp2 = s.get("rr_tp2", 0)
    rr_tp3 = s.get("rr_tp3", 0)
    accuracy = s.get("accuracy", 75.0)
    strat_count = s.get("strategy_count", len(strats))

    # ─ النجوم الذهبية ─
    stars_map = {
        "S": "🌟🌟🌟🌟🌟",
        "A": "🌟🌟🌟🌟",
        "B": "🌟🌟🌟",
        "C": "🌟🌟",
    }
    stars = stars_map.get(grade, "🌟🌟🌟")

    # ─ التوقيت ─
    now_uae = datetime.now(UAE_TZ).strftime("%H:%M • %d/%m/%Y")

    # ─ النسب ─
    def pct(target):
        if entry == 0: return 0
        return (abs(target - entry) / entry) * 100

    sl_pct  = pct(sl)
    tp1_pct = pct(tp1)
    tp2_pct = pct(tp2)
    tp3_pct = pct(tp3)

    # ─ تنسيق السعر ─
    def fmt(v):
        if v >= 1000: return f"{v:.2f}"
        if v >= 1:    return f"{v:.4f}"
        return f"{v:.6f}"

    # ─ MTF ─
    def mtf_ok(t, direction):
        required = "BULLISH" if direction == "LONG" else "BEARISH"
        return "✅" if t == required else ("⚪" if t == "NEUTRAL" else "❌")

    mtf_line = f"{mtf_ok(mtf_15m, dir_)} 15m  {mtf_ok(mtf_1h, dir_)} 1H  {mtf_ok(mtf_4h, dir_)} 4H"

    # ─ BTC ─
    btc_emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "⚪"}.get(btc_trend, "⚪")

    # ─ Direction ─
    if dir_ == "LONG":
        dir_line = "🟢 <b>LONG</b>"
    else:
        dir_line = "🔴 <b>SHORT</b>"

    # ─ Strategies top 4 ─
    strat_text = " • ".join([s.strip() for s in strats[:4]])

    msg = f"""🐋 <b>WhaleX Prime</b>  •  {stars}
━━━━━━━━━━━━━━━━━━━━━
💎 <b><code>{sym}</code></b>
{dir_line}  •  ⚡ Cross <b>{lev:.0f}x</b>
🏆 Grade <b>{grade}</b>  •  Score {score:.1f}  •  ثقة {conf:.0f}%

🛒 الدخول:  <code>{fmt(entry)}</code>
🛑 الوقف:    <code>{fmt(sl)}</code>  ({sl_pct:.2f}%)
🥇 TP1:     <code>{fmt(tp1)}</code>  ({tp1_pct:.1f}% • 1:{rr_tp1})
🥈 TP2:     <code>{fmt(tp2)}</code>  ({tp2_pct:.1f}% • 1:{rr_tp2})
🚀 TP3:     <code>{fmt(tp3)}</code>  ({tp3_pct:.1f}% • 1:{rr_tp3})

📊 {strat_count}/13: {strat_text}

🛡 MTF: {mtf_line}
{btc_emoji} BTC: <b>{btc_trend}</b>  •  Funding: <code>{funding:+.3f}%</code>  •  OI: <code>{oi_change:+.1f}%</code>
🎯 الدقة التاريخية: <b>{accuracy:.1f}%</b>
🛡 <b>Quant Engine V3</b> ✅

⏱ <i>{now_uae} • UTC+4</i>
<i>⚠️ ليست نصيحة مالية — DYOR</i>"""

    return msg

class TelegramService:
    def __init__(self): self._running = False

    async def setup(self):
        s = get_settings()
        if not s.telegram_bot_token:
            log.warning("TELEGRAM_BOT_TOKEN not set")
            return
        await set_commands()
        log.info("Telegram bot ready")
        if s.telegram_admin_chat_id:
            await send_message(s.telegram_admin_chat_id,
                "🟢 <b>WhaleX Prime online</b>\n"
                "Futures Radar ✅\nSpot Radar ✅\nMeme Radar ✅\nTelegram Bridge ✅",
                reply_markup=_kb())

    async def handle_update(self, update: dict):
        msg = update.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = msg.get("text", "").strip()
        name = msg.get("from", {}).get("first_name", "مستخدم")
        if not text or not chat_id:
            return
        if text.startswith("/start"):
            await send_message(chat_id,
                f"👋 <b>اهلاً {name}!</b>\n\n"
                "🐋 <b>WhaleX Prime</b>\n"
                "منصة تداول ذكية متكاملة\n\n"
                "• 3 رادارات: Futures / Spot / Meme\n"
                "• محفظة متعددة الشبكات\n"
                "• AI مساعد للتداول\n"
                "• Demo Account $10,000\n\n"
                "/signals - آخر الإشارات\n"
                "/status - حالة الرادارات\n"
                "/demo - حساب الديمو",
                reply_markup=_kb())
        elif text.startswith("/status"):
            await send_message(chat_id,
                "📊 <b>حالة WhaleX Prime</b>\n\n"
                "🔴 Futures Radar: <b>نشط</b>\n"
                "🟡 Spot Radar: <b>نشط</b>\n"
                "🟣 Meme Radar: <b>نشط</b>\n"
                "🤖 AI Assistant: <b>نشط</b>",
                reply_markup=_kb())
        elif text.startswith("/help"):
            await send_message(chat_id,
                "/start - رسالة الترحيب\n"
                "/signals - آخر الإشارات\n"
                "/status - حالة الرادارات\n"
                "/demo - إحصائيات الديمو",
                reply_markup=_kb())

    async def broadcast_signal(self, sig: dict):
        s = get_settings()
        radar = sig.get("radar_type", "futures")
        channel = {
            "futures": s.telegram_channel_futures,
            "spot":    s.telegram_channel_spot,
            "meme":    s.telegram_channel_meme,
        }.get(radar, "")
        if channel:
            await send_message(channel, signal_msg(sig), reply_markup=_kb_channel())

TG = TelegramService()
