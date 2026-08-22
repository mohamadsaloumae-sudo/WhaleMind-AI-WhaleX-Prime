"""💬 خدمة العملاء — ردود ذكية فورية + تحويل للأدمن."""
import sqlite3
import time
import logging
from fastapi import APIRouter, Request
from pydantic import BaseModel

log = logging.getLogger("support")
router = APIRouter()
DB = "/opt/whalex/db/whalex.db"

KB = [
    (("درج", "grade", "تصنيف"), 3,
     "🏅 <b>درجات الإشارة</b>\nS = أقوى إشارة (توافق كامل بين المؤشرات)\nA = قوية جداً\nB = متوسطة\n\nالمدير الآلي يفتح صفقات للدرجتين S و A فقط.",
     "🏅 <b>Signal grades</b>\nS = strongest (full indicator alignment)\nA = very strong\nB = moderate\n\nThe auto-manager only opens trades on S and A."),
    (("رادار", "radar", "كيف يعمل", "how", "النظام", "يشتغل", "system"), 2,
     "⚡ <b>ثلاثة رادارات مستقلة</b>\n• Predator — يراقب عملات مستقرة لونغ وشورت\n• WhaleX Short — يصطاد القمة عند بداية الهبوط\n• WhaleX Long — يصطاد بداية الموجة الصاعدة\nكل إشارة تمرّ ببوابات فحص صارمة قبل إرسالها.",
     "⚡ <b>Three independent radars</b>\n• Predator — scans stable pairs, long and short\n• WhaleX Short — catches tops as the drop begins\n• WhaleX Long — catches the start of an upward wave\nEvery signal passes strict screening gates first."),
    (("سبوت", "spot", "فرق", "difference", "فيوتشر", "futures"), 2,
     "🪙 <b>السبوت</b>: شراء فعلي بلا رافعة — مخاطرة أقل، أرباح 2-5%\n⚡ <b>الفيوتشر</b>: عقود برافعة — أرباح أكبر ومخاطرة أكبر\nلكل سوق رادار ومدير صفقات مستقل.",
     "🪙 <b>Spot</b>: real purchase, no leverage — lower risk, 2-5% gains\n⚡ <b>Futures</b>: leveraged contracts — bigger gains, bigger risk\nEach market has its own radar and position manager."),
    (("ميم", "meme"), 2,
     "🐸 <b>رادار الميم</b> يفحص بخمس طبقات:\n1) سيولة وحجم وزخم حقيقي\n2) فحص العقد (honeypot / mint / سيولة مقفلة)\n3) توزيع الحاملين وشبكات الداخليين\n4) إثبات الشراء على البلوكشين\n5) تنقيط 85+ للنخبة فقط.",
     "🐸 <b>Meme radar</b> screens in five layers:\n1) Real liquidity, volume and momentum\n2) Contract checks (honeypot / mint / locked liquidity)\n3) Holder distribution and insider networks\n4) On-chain proof of genuine buying\n5) Score 85+ for elite setups only."),
    (("لا تصل", "لا توجد", "no signal", "متوقف", "قليل", "ما في", "بطيء", "why no"), 2,
     "🔍 <b>قلّة الإشارات طبيعية</b>: الفحص صارم ولا يمرّ إلا ما اجتاز كل البوابات.\nتأكد أنك في السوق الصحيح (فيوتشر/سبوت/ميم) — لكل سوق إشاراته وجرسه.",
     "🔍 <b>Few signals is normal</b>: screening is strict and only fully-qualified setups pass.\nCheck you're on the right market tab (Futures/Spot/Meme) — each has its own signals and bell."),
    (("باينانس", "binance", "ربط", "مفتاح", "api", "حساب", "connect"), 2,
     "🔗 <b>ربط باينانس</b>: من صفحة التداول أدخل مفتاح API والسر بصلاحيات القراءة والتداول (بلا سحب)، ثم فعّل التداول الآلي واضبط مبلغ كل صفقة.",
     "🔗 <b>Connecting Binance</b>: in the Trading page add your API key and secret with read + trade permissions (no withdrawals), then enable auto-trading and set your amount per trade."),
    (("وقف", "خسار", "stop", "مخاطر", "risk", "loss"), 2,
     "🛡️ <b>إدارة المخاطر</b>: وقف خسارة لكل صفقة، قفل ربح متدرّج يحمي المكسب فور تحقّقه، وإغلاق فوري عند انقلاب السوق ضد الصفقة.",
     "🛡️ <b>Risk management</b>: a stop-loss on every trade, tiered profit-locking that protects gains as they appear, and an immediate exit when the market flips against the position."),
    (("ربح", "profit", "هدف", "target", "جني", "take"), 2,
     "🎯 <b>جني الأرباح</b>: أهداف متدرّجة مع قفل تلقائي — كلما ارتفع الربح ارتفع مستوى الحماية، فلا يتبخّر المكسب عند الارتداد.",
     "🎯 <b>Taking profit</b>: tiered targets with automatic locking — as profit climbs, so does the protected floor, so gains don't evaporate on a pullback."),
    (("اشتراك", "subscription", "سعر", "price", "دفع", "باقة", "plan"), 2,
     "💳 <b>الاشتراك</b>: تفاصيل الباقات وطرق الدفع في صفحة الاشتراك داخل التطبيق.",
     "💳 <b>Subscription</b>: plans and payment methods are in the Subscription page inside the app."),
    (("اشعار", "إشعار", "notification", "جرس", "صوت", "bell", "sound"), 2,
     "🔔 <b>الإشعارات</b>: لكل سوق جرسه ورسائله. الصوت يرنّ عند كل إشارة أو حدث من المدير، ويمكن كتمه من أيقونة الصوت أعلى الشاشة.",
     "🔔 <b>Notifications</b>: each market has its own bell and feed. A chime plays on every signal or manager event, and you can mute it from the sound icon in the header."),
    (("رافعة", "leverage"), 2,
     "⚙️ <b>الرافعة</b>: تبدأ منخفضة وترتفع تلقائياً عند تأكّد الاتجاه (هرمية)، لتقليل المخاطرة في البداية.",
     "⚙️ <b>Leverage</b>: starts low and scales up automatically once the move is confirmed (pyramiding), keeping early risk small."),
    (("لغة", "language", "english", "عربي", "arabic"), 2,
     "🌐 <b>اللغة</b>: بدّلها من الأيقونة أعلى الشاشة — كل شيء يتبعها، حتى نص المشاركة.",
     "🌐 <b>Language</b>: switch it from the header icon — everything follows, including the share text."),
    (("مشاركة", "share", "دعوة", "صديق", "invite"), 2,
     "📤 <b>المشاركة</b>: أيقونة المشاركة أعلى الشاشة ترسل رابط التطبيق مع نبذة، بلغتك الحالية.",
     "📤 <b>Sharing</b>: the share icon in the header sends the app link with a short pitch, in your current language."),
    (("صفقات مفتوحة", "live", "مفتوح", "الحيه", "الحية", "open trades", "positions"), 2,
     "📊 <b>الصفقات المفتوحة</b>: صفحة مستقلة في الشريط السفلي تعرض كل صفقة حيّة بربحها اللحظي وقمتها وعمرها، محدَّثة كل ثانية.",
     "📊 <b>Open positions</b>: a dedicated tab in the bottom bar showing every live trade with its running PnL, peak and age, refreshed every second."),
]

GREET = ("سلام", "مرحب", "هلا", "اهلا", "أهلا", "hi", "hello", "hey", "صباح", "مساء")
THANKS = ("شكر", "thank", "تسلم", "يعطيك", "thx")

MENU_AR = ("💬 <b>كيف أساعدك؟</b>\nاسأل عن أي موضوع:\n\n"
           "• كيف تعمل الرادارات؟\n• ما معنى الدرجات S و A؟\n• ما الفرق بين السبوت والفيوتشر؟\n"
           "• كيف أربط باينانس؟\n• كيف يُدار الوقف وجني الأرباح؟\n• كيف يفحص رادار الميم؟\n"
           "• لماذا الإشارات قليلة؟\n• تفاصيل الاشتراك\n\n"
           "أو اكتب سؤالك بحرّية وسيصل فريق الدعم.")

MENU_EN = ("💬 <b>How can I help?</b>\nAsk about any topic:\n\n"
           "• How do the radars work?\n• What do grades S and A mean?\n• Spot vs Futures?\n"
           "• How do I connect Binance?\n• How are stops and profits managed?\n• How does the meme radar screen?\n"
           "• Why are signals few?\n• Subscription details\n\n"
           "Or just type your question and our team will receive it.")


class Ask(BaseModel):
    message: str
    user_id: str = "guest"
    lang: str = "ar"


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


def _match(text: str, lang: str = "ar"):
    en = lang == "en"
    menu = MENU_EN if en else MENU_AR
    t = _norm(text)
    if not t:
        return menu
    if any(g in t for g in GREET) and len(t) < 25:
        # ترحيب قصير — سرد المواضيع كلها يُربك ولا يُفيد
        return ("👋 Hi! How can I help?" if en
                else "👋 أهلاً بك! كيف أساعدك؟")
    if any(g in t for g in THANKS) and len(t) < 25:
        return "🙏 Anytime — I'm here for any other question." if en else "🙏 على الرحب والسعة — أي سؤال آخر أنا هنا."
    scored = []
    for keys, weight, ar_ans, en_ans in KB:
        hits = sum(weight for k in keys if _norm(k) in t)
        if hits:
            scored.append((hits, en_ans if en else ar_ans))
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    return "\n\n────────\n\n".join(a for _, a in scored[:2])


def _real_uid(request, fallback: str) -> str:
    """🔑 المعرّف من رمز الدخول — الواجهة قد ترسل معرّف زائر."""
    try:
        auth = request.headers.get("authorization") or ""
        tok = auth.replace("Bearer ", "").strip()
        if tok:
            import jwt as _jwt
            from config import settings as _st
            p = _jwt.decode(tok, _st.secret_key, algorithms=["HS256"])
            sub = p.get("sub")
            if sub:
                return str(sub)
    except Exception:
        pass
    return fallback


@router.post("/api/support/ask")
async def ask(body: Ask, request: Request):
    _init()
    body.user_id = _real_uid(request, body.user_id)
    answer = _match(body.message, body.lang)
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
    # اسم صاحب السؤال
    _who = body.user_id
    try:
        from db.database import get_session, User
        _db = get_session()
        _u = _db.query(User).filter(User.id == body.user_id).first()
        _who = getattr(_u, "username", None) or body.user_id
        _db.close()
    except Exception:
        pass

    # 🔔 تنبيه لحظي للأدمن داخل التطبيق
    try:
        from routers.ws import registry
        await registry.broadcast({
            "event": "support_question", "market": "futures", "admin_only": True,
            "message": f"💬 سؤال جديد من {_who}\n\n{body.message[:160]}",
            "message_en": f"💬 New question from {_who}\n\n{body.message[:160]}",
        })
    except Exception as e:
        log.debug("admin ws: %s", e)

    # وتيليجرام
    try:
        from services.telegram import send_message
        from core.config import get_settings
        _s = get_settings()
        admin = (getattr(_s, "telegram_admin_chat_id", None) or getattr(_s, "admin_chat_id", None)
                 or getattr(_s, "telegram_admin_id", None) or getattr(_s, "admin_id", None))
        if admin:
            await send_message(str(admin),
                               f"💬 <b>سؤال جديد يحتاج ردّك</b>\n"
                               f"من: <b>{_who}</b>\n\n{body.message}\n\n"
                               f"↩️ رد عليه من لوحة الإدارة في التطبيق")
    except Exception as e:
        log.warning("escalate: %s", e)
    return {"reply": None, "auto": False, "menu": MENU_EN if body.lang == "en" else MENU_AR}


TOPICS = [
    ("كيف تعمل الرادارات؟", "How do the radars work?"),
    ("ما معنى الدرجات S و A؟", "What do grades S and A mean?"),
    ("الفرق بين السبوت والفيوتشر", "Spot vs Futures"),
    ("كيف يفحص رادار الميم؟", "How does the meme radar screen?"),
    ("كيف أربط باينانس؟", "How do I connect Binance?"),
    ("كيف تُدار المخاطر والوقف؟", "How are risk and stops managed?"),
    ("كيف يتم جني الأرباح؟", "How is profit taken?"),
    ("لماذا الإشارات قليلة؟", "Why are signals few?"),
    ("ما هي الرافعة الهرمية؟", "What is pyramided leverage?"),
    ("تفاصيل الاشتراك", "Subscription details"),
    ("كيف تعمل الإشعارات؟", "How do notifications work?"),
    ("الصفقات المفتوحة", "Open positions"),
]


@router.get("/api/support/topics")
async def topics(lang: str = "ar"):
    en = lang == "en"
    return {"topics": [t[1] if en else t[0] for t in TOPICS]}


@router.get("/api/admin/support/pending")
async def pending(limit: int = 50):
    """الأسئلة التي لم يجب عنها النظام — للأدمن."""
    _init()
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        rows = c.execute("SELECT id,user_id,message,created_at FROM support_messages "
                         "WHERE (reply IS NULL OR reply='') ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        c.close()
        out = []
        for r in rows:
            d = dict(r)
            try:
                from db.database import get_session, User
                _db = get_session()
                _u = _db.query(User).filter(User.id == d["user_id"]).first()
                d["username"] = getattr(_u, "username", None) if _u else None
                _db.close()
            except Exception:
                d["username"] = None
            out.append(d)
        return {"pending": out}
    except Exception:
        return {"pending": []}


class ReplyBody(BaseModel):
    msg_id: int
    reply: str


@router.post("/api/admin/support/reply")
async def admin_reply(body: ReplyBody):
    """رد الأدمن — يُحفظ ويصل المستخدم فوراً."""
    _init()
    uid = None
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        row = c.execute("SELECT user_id FROM support_messages WHERE id=?", (body.msg_id,)).fetchone()
        uid = dict(row).get("user_id") if row else None
        c.execute("UPDATE support_messages SET reply=?, replied_at=? WHERE id=?",
                  (body.reply, int(time.time()), body.msg_id))
        c.commit(); c.close()
        # ⚡ دفع فوريّ للعميل — بلا انتظار استطلاع
        try:
            from routers.ws import registry
            await registry.send_to_user(uid, {
                "event": "support_reply", "user_id": uid,
                "reply": body.reply, "msg_id": body.msg_id,
            })
        except Exception as _we:
            log.debug("ws reply: %s", _we)
    except Exception as e:
        log.warning("reply: %s", e)
        return {"ok": False}
    if uid:
        try:
            from routers.ws import registry
            await registry.broadcast({"event": "admin_dm", "market": "futures", "target_user": uid,
                                      "message": "💬 رد الدعم الفني:\n" + body.reply,
                                      "message_en": "💬 Support reply:\n" + body.reply})
        except Exception:
            pass
        try:
            c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
            r = c.execute("SELECT telegram_id FROM users WHERE id=?", (uid,)).fetchone()
            c.close()
            tg = dict(r).get("telegram_id") if r else None
            if tg:
                from services.telegram import send_message
                await send_message(str(tg), "💬 <b>رد الدعم الفني</b>\n\n" + body.reply)
        except Exception:
            pass
    return {"ok": True, "user_id": uid}


@router.get("/api/support/history")
async def history(request: Request, user_id: str = "guest", limit: int = 50):
    _init()
    user_id = _real_uid(request, user_id)
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        rows = c.execute("SELECT message,reply,auto,created_at,replied_at FROM support_messages "
                         "WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
        c.close()
        return {"messages": [dict(r) for r in reversed(rows)]}
    except Exception:
        return {"messages": []}


@router.get("/api/admin/support/threads")
async def threads():
    """قائمة المحادثات — كل مستخدم مرّة واحدة باسمه."""
    _init()
    try:
        c = sqlite3.connect(DB)
        c.row_factory = sqlite3.Row
        rows = c.execute("""
            SELECT user_id,
                   COUNT(*) AS total,
                   SUM(CASE WHEN reply IS NULL OR reply='' THEN 1 ELSE 0 END) AS waiting,
                   MAX(created_at) AS last_at,
                   (SELECT message FROM support_messages m2
                     WHERE m2.user_id = m.user_id ORDER BY m2.id DESC LIMIT 1) AS last_msg
              FROM support_messages m
             GROUP BY user_id
             ORDER BY waiting DESC, last_at DESC
        """).fetchall()
        c.close()
        out = []
        for r in rows:
            d = dict(r)
            try:
                from db.database import get_session, User
                _db = get_session()
                _u = _db.query(User).filter(User.id == d["user_id"]).first()
                d["username"] = (getattr(_u, "username", None)
                                 or getattr(_u, "email", None)) if _u else None
                _db.close()
            except Exception:
                d["username"] = None
            if not d["username"]:
                # 🔎 معرّف قصير قديم؟ نبحث عنه في ملفّات المستخدم
                try:
                    _c2 = sqlite3.connect(DB)
                    _r2 = _c2.execute(
                        "SELECT u.username FROM users u "
                        "JOIN user_profiles p ON p.user_id=u.id "
                        "WHERE p.user_id LIKE ? LIMIT 1",
                        (str(d["user_id"]) + "%",)).fetchone()
                    _c2.close()
                    if _r2:
                        d["username"] = _r2[0]
                except Exception:
                    pass
            if not d["username"]:
                d["username"] = "زائر " + str(d["user_id"])[:6]
            out.append(d)
        return {"threads": out}
    except Exception as e:
        log.warning("threads: %s", e)
        return {"threads": []}


@router.get("/api/admin/support/thread")
async def thread(user_id: str, limit: int = 60):
    """محادثة مستخدم واحد كاملةً."""
    _init()
    try:
        c = sqlite3.connect(DB)
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT id,message,reply,auto,created_at,replied_at "
            "FROM support_messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit)).fetchall()
        c.close()
        return {"messages": [dict(r) for r in reversed(rows)]}
    except Exception:
        return {"messages": []}
