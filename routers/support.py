"""💬 خدمة العملاء — ردود ذكية فورية + تحويل للأدمن."""
import sqlite3
import time
import logging
from fastapi import APIRouter
from pydantic import BaseModel

log = logging.getLogger("support")
router = APIRouter()
DB = "/opt/whalex/db/whalex.db"

KB = [
    (("درجة", "grade", "تصنيف"),
     "🏅 درجات الإشارة:\nS = أقوى إشارة (توافق كل المؤشرات) · A = قوية جداً · B = متوسطة.\nالمدير الآلي يفتح صفقات للدرجتين S و A فقط."),
    (("رادار", "radar", "كيف يعمل", "how does", "النظام"),
     "⚡ ثلاثة رادارات مستقلة:\n• Predator — يراقب العملات المستقرة لونغ وشورت\n• WhaleX Short — يصطاد القمم عند بداية الهبوط\n• WhaleX Long — يصطاد بداية الموجة الصاعدة\nكل إشارة تمرّ ببوابات فحص صارمة قبل إرسالها."),
    (("سبوت", "spot", "فرق", "difference"),
     "🪙 السبوت: شراء فعلي للعملة (بلا رافعة، مخاطرة أقل، أرباح 2-5%).\n⚡ الفيوتشر: عقود برافعة (أرباح أكبر ومخاطرة أكبر).\nلكل منهما رادار ومدير صفقات مستقل."),
    (("ميم", "meme"),
     "🐸 رادار الميم كوينز يفحص كل عملة بخمس طبقات:\n1) سيولة وحجم وزخم حقيقي\n2) فحص العقد (honeypot / mint / سيولة مقفلة)\n3) توزيع الحاملين وشبكات الداخليين\n4) إثبات الشراء على البلوكشين\n5) تنقيط 85+ للنخبة فقط."),
    (("لا تصل", "لا توجد", "no signal", "متوقف", "لا يوجد", "قليلة"),
     "🔍 قلّة الإشارات غالباً طبيعية: الفحص صارم ولا يمرّ إلا ما اجتاز كل البوابات.\nتأكد أن الإشعارات مفعّلة، وأنك في السوق الصحيح (فيوتشر/سبوت/ميم) — لكل سوق إشاراته."),
    (("باينانس", "binance", "ربط", "مفتاح", "api"),
     "🔗 الربط من صفحة التداول: أدخل مفتاح API والسر من باينانس بصلاحيات القراءة والتداول (بلا سحب)، ثم فعّل التداول الآلي واضبط مبلغ كل صفقة."),
    (("وقف", "خساره", "خسارة", "stop", "مخاطر"),
     "🛡️ إدارة المخاطر: وقف خسارة لكل صفقة، قفل ربح متدرّج يحمي المكسب فور تحقّقه، وإغلاق فوري عند انقلاب السوق ضد الصفقة."),
    (("اشتراك", "subscription", "سعر", "price", "دفع"),
     "💳 تفاصيل الباقات وطرق الدفع في صفحة الاشتراك داخل التطبيق."),
]


class Ask(BaseModel):
    message: str
    user_id: str = "guest"


def _init():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS support_messages(
        id INTEGER PRIMARY KEY, user_id TEXT, message TEXT, reply TEXT,
        auto INTEGER DEFAULT 0, created_at INTEGER, replied_at INTEGER)""")
    c.commit(); c.close()


def _match(text: str):
    t = (text or "").lower()
    for keys, answer in KB:
        if any(k in t for k in keys):
            return answer
    return None


@router.post("/api/support/ask")
async def ask(body: Ask):
    _init()
    answer = _match(body.message)
    now = int(time.time())
    try:
        c = sqlite3.connect(DB)
        c.execute("INSERT INTO support_messages(user_id,message,reply,auto,created_at,replied_at) VALUES(?,?,?,?,?,?)",
                  (body.user_id, body.message, answer, 1 if answer else 0, now, now if answer else None))
        c.commit(); c.close()
    except Exception as e:
        log.warning("save: %s", e)
    if answer:
        return {"reply": answer, "auto": True}
    try:
        from services.telegram import send_message
        from core.config import get_settings
        _s = get_settings()
        admin = getattr(_s, "admin_chat_id", None) or getattr(_s, "telegram_admin_id", None) or getattr(_s, "admin_id", None)
        if admin:
            await send_message(str(admin), f"💬 <b>سؤال جديد</b>\n<code>{body.user_id}</code>\n\n{body.message}")
    except Exception as e:
        log.warning("escalate: %s", e)
    return {"reply": None, "auto": False}


@router.get("/api/support/history")
async def history(user_id: str = "guest", limit: int = 50):
    _init()
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        rows = c.execute("SELECT message,reply,auto,created_at,replied_at FROM support_messages "
                         "WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
        c.close()
        return {"messages": [dict(r) for r in reversed(rows)]}
    except Exception:
        return {"messages": []}
