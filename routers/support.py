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
    (("درج", "grade", "تصنيف", "s", "a", "b"), 3,
     "🏅 <b>درجات الإشارة</b>\nS = أقوى إشارة (توافق كامل بين المؤشرات)\nA = قوية جداً\nB = متوسطة\n\nالمدير الآلي يفتح صفقات للدرجتين S و A فقط."),
    (("رادار", "radar", "كيف يعمل", "how", "النظام", "يشتغل"), 2,
     "⚡ <b>ثلاثة رادارات مستقلة</b>\n• Predator — يراقب عملات مستقرة لونغ وشورت\n• WhaleX Short — يصطاد القمة عند بداية الهبوط\n• WhaleX Long — يصطاد بداية الموجة الصاعدة\nكل إشارة تمرّ ببوابات فحص قبل إرسالها."),
    (("سبوت", "spot", "فرق", "difference", "فيوتشر", "futures"), 2,
     "🪙 <b>السبوت</b>: شراء فعلي بلا رافعة — مخاطرة أقل، أرباح 2-5%\n⚡ <b>الفيوتشر</b>: عقود برافعة — أرباح أكبر ومخاطرة أكبر\nلكل سوق رادار ومدير صفقات مستقل."),
    (("ميم", "meme", "عمل", "سولانا", "solana"), 2,
     "🐸 <b>رادار الميم</b> يفحص بخمس طبقات:\n1) سيولة وحجم وزخم حقيقي\n2) فحص العقد (honeypot / mint / سيولة مقفلة)\n3) توزيع الحاملين وشبكات الداخليين\n4) إثبات الشراء على البلوكشين\n5) تنقيط 85+ للنخبة فقط."),
    (("لا تصل", "لا توجد", "no signal", "متوقف", "قليل", "ما في", "بطيء"), 2,
     "🔍 <b>قلّة الإشارات طبيعية</b>: الفحص صارم ولا يمرّ إلا ما اجتاز كل البوابات.\nتأكد أنك في السوق الصحيح (فيوتشر/سبوت/ميم) — لكل سوق إشاراته وجرسه."),
    (("باينانس", "binance", "ربط", "مفتاح", "api", "حساب"), 2,
     "🔗 <b>ربط باينانس</b>: من صفحة التداول أدخل مفتاح API والسر بصلاحيات القراءة والتداول (بلا سحب)، ثم فعّل التداول الآلي واضبط مبلغ كل صفقة."),
    (("وقف", "خسار", "stop", "مخاطر", "risk"), 2,
     "🛡️ <b>إدارة المخاطر</b>: وقف خسارة لكل صفقة، قفل ربح متدرّج يحمي المكسب فور تحقّقه، وإغلاق فوري عند انقلاب السوق ضد الصفقة."),
    (("ربح", "profit", "هدف", "target", "جني"), 2,
     "🎯 <b>جني الأرباح</b>: أهداف متدرّجة مع قفل تلقائي — كلما ارتفع الربح ارتفع مستوى الحماية، فلا يتبخّر المكسب عند الارتداد."),
    (("اشتراك", "subscription", "سعر", "price", "دفع", "باقة"), 2,
     "💳 <b>الاشتراك</b>: تفاصيل الباقات وطرق الدفع في صفحة الاشتراك داخل التطبيق."),
    (("اشعار", "إشعار", "notification", "جرس", "صوت"), 2,
     "🔔 <b>الإشعارات</b>: لكل سوق جرسه ورسائله. الصوت يرنّ عند كل إشارة أو حدث من المدير، ويمكن كتمه من أيقونة الصوت أعلى الشاشة."),
    (("رافعة", "leverage", "x"), 2,
     "⚙️ <b>الرافعة</b>: تبدأ منخفضة وترتفع تلقائياً عند تأكّد الاتجاه (هرمية)، لتقليل المخاطرة في البداية."),
    (("لغة", "language", "english", "عربي"), 2,
     "🌐 <b>اللغة</b>: بدّلها من الأيقونة أعلى الشاشة — كل شيء يتبعها، حتى نص المشاركة."),
    (("مشاركة", "share", "دعوة", "صديق"), 2,
     "📤 <b>المشاركة</b>: أيقونة المشاركة أعلى الشاشة ترسل رابط التطبيق مع نبذة، بلغتك الحالية."),
    (("صفقات مفتوحة", "live", "مفتوح", "الحيه", "الحية"), 2,
     "📊 <b>الصفقات المفتوحة</b>: صفحة مستقلة في الشريط السفلي تعرض كل صفقة حيّة بربحها اللحظي وقمتها وعمرها، محدَّثة كل ثانية."),
]

GREET = ("سلام", "مرحب", "هلا", "اهلا", "أهلا", "hi", "hello", "hey", "صباح", "مساء")
THANKS = ("شكر", "thank", "تسلم", "يعطيك")

MENU = ("💬 <b>كيف أساعدك؟</b>\nاسأل عن أي موضوع:\n\n"
        "• كيف تعمل الرادارات؟\n• ما معنى الدرجات S و A؟\n• ما الفرق بين السبوت والفيوتشر؟\n"
        "• كيف أربط باينانس؟\n• كيف يُدار الوقف وجني الأرباح؟\n• كيف يفحص رادار الميم؟\n"
        "• لماذا الإشارات قليلة؟\n• تفاصيل الاشتراك\n\n"
        "أو اكتب سؤالك بحرّية وسيصل فريق الدعم.")


class Ask(BaseModel):
    message: str
    user_id: str = "guest"


def _init():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS support_messages(
        id INTEGER PRIMARY KEY, user_id TEXT, message TEXT, reply TEXT,
        auto INTEGER DEFAULT 0, created_at INTEGER, replied_at INTEGER)""")
    c.commit(); c.close()


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي"), ("ـ", "")):
        s = s.replace(a, b)
    return s


def _match(text: str):
    t = _norm(text)
    if not t:
        return MENU
    if any(g in t for g in GREET) and len(t) < 25:
        return "👋 أهلاً بك في الدعم الفني!\n\n" + MENU
    if any(g in t for g in THANKS) and len(t) < 25:
        return "🙏 على الرحب والسعة — أي سؤال آخر أنا هنا."
    scored = []
    for keys, weight, answer in KB:
        hits = sum(weight for k in keys if _norm(k) in t)
        if hits:
            scored.append((hits, answer))
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    return "\n\n────────\n\n".join(a for _, a in scored[:2])


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
    return {"reply": None, "auto": False, "menu": MENU}


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
