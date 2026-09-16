"""💬 خدمة العملاء — ردود ذكية فورية + تحويل للأدمن."""
import sqlite3
import time
import logging
from fastapi import APIRouter, Request, UploadFile, File
from pydantic import BaseModel

log = logging.getLogger("support")
router = APIRouter()
DB = "/opt/whalex/db/whalex.db"

KB = [
    (("درج", "grade", "تصنيف"), 3,
     "🏅 <b>درجات الإشارة</b>\nS = أقوى إشارة (توافق كامل بين المؤشرات)\nA = قوية جداً\nB = متوسطة\n\nالمدير الآلي يفتح صفقات للدرجتين S و A فقط.",
     "🏅 <b>Signal grades</b>\nS = strongest (full indicator alignment)\nA = very strong\nB = moderate\n\nThe auto-manager only opens trades on S and A."),
    (("رادار", "radar", "كيف يعمل", "how", "النظام", "يشتغل", "system"), 2,
     "🐋 <b>ويل إكس — ثلاثة أنظمة</b>\n\n"
     "⚡ <b>العقود الآجلة</b>\n"
     "رادارات: WhaleX Predator · Predator MX · WhaleX Short · WhaleX Long\n"
     "مع الحارس (Guardian) لفحص كل إشارة، ونموذج ذكاء اصطناعيّ يتعلّم من النتائج.\n"
     "التداول الآليّ يعمل على سبع منصّات.\n\n"
     "🪙 <b>الفوريّ (Spot)</b>\n"
     "رادار WhaleX Spot — شراء فعليّ بلا رافعة، وتداول آليّ على سبع منصّات.\n\n"
     "🐸 <b>الميم كوينز</b>\n"
     "رادار WhaleX Meme — إشارات فتح وإغلاق فقط حالياً، والتداول الآليّ قادم قريباً.\n\n"
     "والنظام مخصّص للعملات الرقمية.",
     "🐋 <b>WhaleX — three systems</b>\n\n"
     "⚡ <b>Futures</b>\n"
     "Radars: WhaleX Predator · Predator MX · WhaleX Short · WhaleX Long\n"
     "With Guardian screening every signal, and an AI model that learns from outcomes.\n"
     "Auto-trading runs on seven exchanges.\n\n"
     "🪙 <b>Spot</b>\n"
     "WhaleX Spot radar — real purchases, no leverage, auto-trading on seven exchanges.\n\n"
     "🐸 <b>Memecoins</b>\n"
     "WhaleX Meme radar — entry and exit signals only for now; auto-trading coming soon.\n\n"
     "The system covers crypto markets."),
    (("سبوت", "spot", "فرق", "difference", "فيوتشر", "futures"), 2,
     "🐋 <b>أنظمة ويل إكس الثلاثة</b>\n\n"
     "🪙 <b>الفوريّ (Spot)</b>\n"
     "شراء فعليّ للعملة بلا رافعة. آليّ بالكامل: يفتح الصفقة ويديرها حتى "
     "الإغلاق، بوقف خسارة وقفل ربح متحرّك يحمي مكسبك فور تحقّقه. "
     "مخاطرة أقلّ، وأرباح 2-5% عادةً.\n\n"
     "⚡ <b>العقود الآجلة (Futures)</b>\n"
     "عقود برافعة، صعوداً وهبوطاً. آليّ بالكامل أيضاً: فتح وإدارة وإغلاق، "
     "مع وقف لكل صفقة وقفل ربح متدرّج وخروج فوريّ عند انقلاب السوق. "
     "أرباح أكبر ومخاطرة أكبر.\n\n"
     "والنظامان يعملان على سبع منصّات.\n\n"
     "🐸 <b>الميم كوينز</b>\n"
     "إشارات دخول وخروج فقط حالياً — والتداول الآليّ قادم قريباً.",
     "🐋 <b>WhaleX — three systems</b>\n\n"
     "🪙 <b>Spot</b>\nReal purchases, no leverage. Fully automated: opens, "
     "manages and closes each trade, with a stop-loss and a trailing profit "
     "lock that protects gains as they appear. Lower risk, typically 2-5%.\n\n"
     "⚡ <b>Futures</b>\nLeveraged contracts, long and short. Also fully "
     "automated, with a stop on every trade, tiered profit locking and an "
     "immediate exit when the market flips. Bigger gains, bigger risk.\n\n"
     "Both run on seven exchanges.\n\n"
     "🐸 <b>Memecoins</b>\nEntry and exit signals only for now — auto-trading "
     "coming soon.",),
    (("لا تصل", "لا توجد", "no signal", "متوقف", "قليل", "ما في", "بطيء", "why no"), 2,
     "🔍 <b>عدد الإشارات يتبع السوق</b>\n"
     "في الأسواق الهادئة تقلّ الفرص الجيّدة، وفي المتحرّكة تكثر. "
     "ونحن لا نفتح صفقة إلا حين تتوفّر شروطها كاملة — فالانتظار "
     "أفضل من دخول ضعيف.\n\n"
     "وتأكّد أنك في السوق الصحيح (فيوتشر/سبوت/ميم) — لكلٍّ إشاراته.",
     "🔍 <b>Signal count follows the market</b>\n"
     "Quiet markets offer fewer good setups; active ones offer more. "
     "We only open when every condition is met — waiting beats a weak entry."
     "\n\nAlso check you're on the right tab (Futures/Spot/Meme).",),
    (("باينانس", "binance", "ربط", "مفتاح", "api", "حساب", "connect"), 2,
     "🔗 <b>ربط حسابك</b>\n\n"
     "① استخرج مفاتيح API من حسابك على المنصّة (باينانس أو غيرها) "
     "بصلاحيات القراءة والتداول فقط — بلا سحب.\n\n"
     "② افتح <b>المزيد ← دليل المستخدم</b> داخل التطبيق واقرأ الخطوات "
     "بالتفصيل.\n\n"
     "③ وللشرح المصوَّر كاملاً، شاهد الفيديو المثبَّت في قناتنا:\n"
     "https://t.me/whalexprime\n\n"
     "④ ثم أدخل المفتاح والسرّ في صفحة التداول، وفعّل التداول الآليّ "
     "واضبط مبلغ كل صفقة.",
     "🔗 <b>Connecting your account</b>\n\n"
     "① Create API keys on your exchange (Binance or others) with read + "
     "trade permissions only — no withdrawals.\n\n"
     "② Open <b>More ← User Guide</b> in the app for the full steps.\n\n"
     "③ For a full video walkthrough, see the pinned post in our channel:\n"
     "https://t.me/whalexprime\n\n"
     "④ Then enter your key and secret in the Trading page, enable "
     "auto-trading and set your amount per trade.",),
    (("وقف", "خسار", "stop", "مخاطر", "risk", "loss"), 2,
     "🛡️ <b>إدارة المخاطر</b>: وقف خسارة لكل صفقة، قفل ربح متدرّج يحمي المكسب فور تحقّقه، وإغلاق فوري عند انقلاب السوق ضد الصفقة.",
     "🛡️ <b>Risk management</b>: a stop-loss on every trade, tiered profit-locking that protects gains as they appear, and an immediate exit when the market flips against the position."),
    (("ربح", "profit", "هدف", "target", "جني", "take"), 2,
     "🎯 <b>جني الأرباح</b>: أهداف متدرّجة مع قفل تلقائي — كلما ارتفع الربح ارتفع مستوى الحماية، فلا يتبخّر المكسب عند الارتداد.",
     "🎯 <b>Taking profit</b>: tiered targets with automatic locking — as profit climbs, so does the protected floor, so gains don't evaporate on a pullback."),
    (("اقل مبلغ", "أقل مبلغ", "ادنى مبلغ", "أدنى مبلغ", "كم لازم",
      "كم احط", "كم أحط", "كم اضيف", "كم أضيف", "كم يكفي", "بكم ابدا",
      "بكم أبدأ", "راس مال", "رأس مال", "الحد الادنى", "الحد الأدنى",
      "minimum", "how much", "capital", "start with"), 3,
     "💰 <b>الحدّ الأدنى: 300$</b>\n"
     "وأقلّ صفقة في الفوريّ: 50$\n\n"
     "<b>لماذا هذا الحدّ؟</b>\n"
     "عائد النظام يتراوح بين <b>30% و50% شهرياً</b> حسب حركة السوق، "
     "واشتراك البوت <b>100$ شهرياً</b> ثابت لا يتغيّر مهما كان رصيدك.\n\n"
     "<b>وهذا يعني:</b>\n\n"
     "• برصيد <b>100$</b> — لو حصلت على الـ50% كاملة تربح <b>50$</b>، "
     "ورسوم البوت 100$ ⇒ تخرج خاسراً 50$\n\n"
     "• برصيد <b>200$</b> — الـ50% تعطيك <b>100$</b>، "
     "ورسوم البوت 100$ ⇒ تتعادل بلا ربح\n\n"
     "• برصيد <b>300$</b> — الـ50% تعطيك <b>150$</b>، "
     "ورسوم البوت 100$ ⇒ يبقى لك 50$\n\n"
     "• برصيد <b>500$</b> — الـ50% تعطيك <b>250$</b>، "
     "ورسوم البوت 100$ ⇒ يبقى لك 150$\n\n"
     "• برصيد <b>1000$</b> — الـ50% تعطيك <b>500$</b>، "
     "ورسوم البوت 100$ ⇒ يبقى لك 400$\n\n"
     "⚠️ وفي الشهر الهادئ (30%) يرتفع الحدّ المجدي: "
     "الـ300$ تعطي 90$ والاشتراك 100$.\n"
     "لذلك <b>باقة الثلاثة أشهر (270$ = 90$ شهرياً)</b> أنسب لمن "
     "رصيده 300-400$.\n\n"
     "📌 وكلّما كبر رصيدك، صغرت حصّة الاشتراك من أرباحك.",
     "💰 <b>Minimum: $300</b>\nSmallest spot trade: $50\n\n"
     "<b>Why this minimum?</b>\n"
     "Returns range between <b>30% and 50% monthly</b> depending on market "
     "conditions, while the bot subscription is a fixed <b>$100/month</b> "
     "regardless of your balance.\n\n"
     "<b>Which means:</b>\n\n"
     "• With <b>$100</b> — a full 50% earns you <b>$50</b>, "
     "and the bot costs $100 ⇒ you end up $50 down\n\n"
     "• With <b>$200</b> — 50% earns <b>$100</b>, bot costs $100 ⇒ break-even\n\n"
     "• With <b>$300</b> — 50% earns <b>$150</b>, bot costs $100 ⇒ you keep $50\n\n"
     "• With <b>$500</b> — 50% earns <b>$250</b>, bot costs $100 ⇒ you keep $150\n\n"
     "• With <b>$1000</b> — 50% earns <b>$500</b>, bot costs $100 ⇒ you keep $400\n\n"
     "⚠️ In a quiet month (30%) the viable floor rises: $300 yields $90 "
     "against a $100 fee.\nSo the <b>3-month plan ($270 = $90/month)</b> "
     "suits balances of $300-400 better.\n\n"
     "📌 The bigger your balance, the smaller the subscription's share "
     "of your profit."),
    (("اشتراك", "subscription", "سعر", "price", "دفع", "باقة", "plan"), 2,
     "💳 <b>الاشتراك</b>\n\n"
     "• شهر واحد: <b>100$</b>\n"
     "• ثلاثة أشهر: <b>270$</b>\n\n"
     "<b>طريقة الاشتراك:</b>\n"
     "① في التطبيق اضغط <b>الثلاث نقاط</b> أعلى الشاشة ← <b>الاشتراكات</b>\n"
     "② انسخ عنوان المحفظة من هناك\n"
     "⚠️ انتبه: العنوان على شبكة <b>TRC20 (ترون)</b> — أي تحويل على شبكة "
     "أخرى يضيع.\n"
     "③ حوّل المبلغ من محفظتك على باينانس بنفس الشبكة\n"
     "④ بعد التحويل، احضر رقم المعاملة (TxID):\n"
     "   في باينانس افتح <b>المحفظة ← السجلّ ← السحب</b>، اضغط على عملية "
     "السحب، وانسخ <b>TxID</b>\n"
     "⑤ الصقه في صفحة الاشتراكات واضغط ترقية — وتُفعَّل باقتك.",
     "💳 <b>Subscription</b>\n\n"
     "• 1 month: <b>$100</b>\n• 3 months: <b>$270</b>\n\n"
     "<b>How to subscribe:</b>\n"
     "① In the app tap the <b>three dots</b> at the top ← <b>Subscriptions</b>\n"
     "② Copy the wallet address shown\n"
     "⚠️ Note: the address is on the <b>TRC20 (Tron)</b> network — transfers "
     "on any other network will be lost.\n"
     "③ Send the amount from your Binance wallet on the same network\n"
     "④ Then get your transaction ID (TxID):\n"
     "   In Binance open <b>Wallet ← History ← Withdrawals</b>, tap the "
     "withdrawal and copy the <b>TxID</b>\n"
     "⑤ Paste it in the Subscriptions page and tap upgrade.",),
    (("اشعار", "إشعار", "notification", "جرس", "صوت", "bell", "sound"), 2,
     "🔔 <b>الإشعارات</b>: لكل سوق جرسه ورسائله. الصوت يرنّ عند كل إشارة أو حدث من المدير، ويمكن كتمه من أيقونة الصوت أعلى الشاشة.",
     "🔔 <b>Notifications</b>: each market has its own bell and feed. A chime plays on every signal or manager event, and you can mute it from the sound icon in the header."),
    (("رافعة", "leverage"), 2,
     "⚙️ <b>الرافعة</b>: يضبطها النظام لكل إشارة حسب مسافة الوقف — كلّما ضاق الوقف ارتفعت الرافعة والعكس. وتختارها أنت من إعدادات التداول الآليّ.",
     "⚙️ <b>Leverage</b>: set per signal from the stop distance — a tighter stop allows higher leverage and vice versa. You choose your own cap in auto-trading settings."),
    (("كشف", "تقرير", "حساب", "statement", "report", "ارباحي", "أرباحي"), 3,
     "🏦 <b>كشف حسابك</b>: اطلبه من خدمة العملاء ويصلك في البوت وهنا — كل صفقة بتاريخها وسعر دخولها وخروجها ورسومها وصافيها، مع الإجمالي.\nوالأرقام من حسابك على المنصّة مباشرة، لا محاكاة.",
     "🏦 <b>Your statement</b>: request it from support and it arrives in the bot and here — every trade with its dates, entry, exit, fees and net, plus totals.\nFigures come straight from your exchange account, not a simulation."),
    (("لم تفتح", "لم تُفتح", "ما فتحت", "didn\'t open", "not opened", "فاتني"), 2,
     "🚦 <b>الإشارة وصلت ولم تُفتح</b> — أسباب محتملة:\n• رصيدك لا يكفي لحجم الصفقة\n• السعر تحرّك بعيداً عن نقطة الدخول، فتجنّبنا دخولاً سيّئاً\n• صلاحيات مفتاح المنصّة ناقصة\n• أو العملة غير متاحة على منصّتك\nوكل محاولة مسجّلة، وخدمة العملاء تطّلع على السبب الدقيق.",
     "🚦 <b>Signal arrived but no trade opened</b> — possible reasons:\n• Insufficient balance for the position size\n• Price moved too far from entry, so we skipped a poor fill\n• Missing API key permissions\n• Or the pair isn\'t listed on your exchange\nEvery attempt is logged and support can see the exact reason."),
    (("رسوم", "عمولة", "fees", "commission"), 2,
     "💵 <b>الرسوم</b>: رسوم المنصّة نفسها (باينانس وغيرها) تُخصم من صفقتك، وويل إكس لا يأخذ نسبة من أرباحك.\nوكشف حسابك يُظهر رسوم كل صفقة والصافي بعدها.",
     "💵 <b>Fees</b>: your exchange's own trading fees are deducted per trade; WhaleX takes no cut of your profits.\nYour statement shows the fee on each trade and the net after it."),
    (("كم صفقة", "عدد الصفقات", "كم اشارة", "كم إشارة", "يوميا", "يومياً",
      "how many trades", "per day"), 2,
     "📈 <b>عدد الصفقات يتبع السوق</b>\n"
     "في الأيام المتحرّكة تكثر الفرص، وفي الهادئة تقلّ. "
     "ولا نفتح صفقة إلا حين تكتمل شروطها — فلا نعد برقم ثابت.\n"
     "والأهمّ جودة الصفقة لا عددها.",
     "📈 <b>Trade count follows the market</b>\n"
     "Active days bring more setups, quiet days fewer. We only open when "
     "every condition is met, so we don't promise a fixed number.\n"
     "Quality matters more than quantity."),
    (("يدوي", "يدويّ", "بنفسي", "اتداول", "أتداول", "manual", "myself",
      "same account"), 2,
     "✋ <b>التداول اليدويّ مع البوت</b>\n"
     "تستطيع ذلك، لكن انتبه:\n"
     "• احتفظ برصيد كافٍ ليعمل البوت — فصفقاتك اليدوية تستهلك الهامش\n"
     "• لا تُغلق صفقات البوت يدوياً، فهو يديرها بوقف وأهداف\n"
     "• والأنظف: حساب منفصل لكلٍّ.",
     "✋ <b>Manual trading alongside the bot</b>\nYou can, but note:\n"
     "• Keep enough free balance for the bot — your manual trades consume "
     "margin\n• Don't close the bot's positions manually; it manages them "
     "with stops and targets\n• Cleanest setup: a separate account for each."),
    (("ايقاف", "إيقاف", "اوقف", "أوقف", "توقيف", "stop bot", "pause",
      "disable", "اطفاء", "إطفاء"), 2,
     "⏸️ <b>إيقاف التداول الآليّ</b>\n"
     "من صفحة <b>التداول الآليّ</b> أطفئ المفتاح — يتوقّف فتح صفقات جديدة "
     "فوراً.\n\n"
     "⚠️ وصفقاتك المفتوحة تبقى تحت إدارة النظام حتى تُغلق بشروطها، "
     "فلا تُترك بلا حماية.\n"
     "ولإغلاق فوريّ لصفقة بعينها، استخدم زرّ الإغلاق في صفحة صفقاتي.",
     "⏸️ <b>Pausing auto-trading</b>\nIn the <b>Auto-Trading</b> page turn "
     "the switch off — new trades stop immediately.\n\n"
     "⚠️ Open positions stay under management until they close on their own "
     "terms, so nothing is left unprotected.\n"
     "To close one now, use the close button in My Trades."),
    (("انتهى اشتراكي", "انتهاء الاشتراك", "خلص الاشتراك", "expired",
      "subscription ends", "بعد الانتهاء"), 2,
     "⏳ <b>عند انتهاء اشتراكك</b>\n"
     "• يتوقّف فتح الصفقات الجديدة\n"
     "• ويتوقّف النظام عن إدارة صفقاتك — فأدِرها بنفسك على منصّتك\n"
     "• وسجلّك وكشف حسابك يبقيان محفوظين بالكامل\n"
     "• وبمجرّد التجديد يعود كل شيء تلقائياً بلا إعداد.",
     "⏳ <b>When your subscription ends</b>\n"
     "• New trades stop opening\n• The system stops managing your positions "
     "— handle them yourself on the exchange\n• Your history and statement "
     "stay fully saved\n• On renewal everything resumes automatically."),
    (("امان", "أمان", "امن", "آمن", "safe", "security", "تسرق", "مفاتيحي",
      "بياناتي", "خطر"), 2,
     "🔒 <b>أمان حسابك</b>\n"
     "• مفاتيحك مشفّرة في قاعدتنا ولا تظهر لأحد\n"
     "• نطلب صلاحية <b>القراءة والتداول فقط</b> — بلا صلاحية سحب، "
     "فلا يستطيع أحد تحويل أموالك حتى لو أراد\n"
     "• أموالك تبقى في حسابك على المنصّة ولا تمرّ بنا إطلاقاً\n"
     "• وتستطيع إلغاء المفاتيح من منصّتك في أي لحظة.",
     "🔒 <b>Account security</b>\n• Your keys are encrypted in our database "
     "and shown to no one\n• We request <b>read + trade only</b> — no "
     "withdrawal permission, so no one can move your funds\n• Your money "
     "stays in your exchange account and never passes through us\n"
     "• You can revoke the keys from your exchange at any moment."),
    (("منصات", "منصّات", "اي منصه", "أي منصة", "exchanges", "which exchange",
      "بايبت", "bybit", "okx", "bitget", "gate", "mexc", "bingx"), 2,
     "🌐 <b>سبع منصّات مدعومة</b>\n"
     "Binance · Bybit · OKX · Bitget · Gate.io · MEXC · BingX\n\n"
     "تربط ما شئت منها، وكل إشارة تُنفَّذ على منصّتها الصحيحة. "
     "وبعض العملات حصريّة على منصّة بعينها — فمن يربط أكثر، تصله إشارات أكثر.",
     "🌐 <b>Seven supported exchanges</b>\n"
     "Binance · Bybit · OKX · Bitget · Gate.io · MEXC · BingX\n\n"
     "Connect as many as you like; each signal executes on its own exchange. "
     "Some pairs are exclusive to one venue — connecting more means "
     "receiving more signals."),
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
    media: str = ""


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
            from core.config import get_settings
            p = _jwt.decode(tok, get_settings().secret_key, algorithms=["HS256"])
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
    # 📎 مرفق بلا نصّ — لا ردّ آليّ، يصل الإدارة مباشرةً
    answer = "" if (body.media and not body.message.strip()) \
        else _match(body.message, body.lang)
    now = int(time.time())
    try:
        c = sqlite3.connect(DB)
        c.execute("INSERT INTO support_messages(user_id,message,reply,auto,created_at,replied_at,media) VALUES(?,?,?,?,?,?,?)",
                  (body.user_id, body.message, answer, 1 if answer else 0, now, now if answer else None, body.media))
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
        # 📎 نجلب الوسائط — 24 رسالة صورة بلا نصّ لا تظهر في القائمة،
        #    فلا يمكن الردّ عليها ويبقى عدّاد الدعم عالقاً على 33.
        rows = c.execute("SELECT id,user_id,message,created_at,replied_at,media "
                         "FROM support_messages "
                         "WHERE (reply IS NULL OR reply='') ORDER BY id DESC LIMIT ?",
                         (limit,)).fetchall()
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
        # 💬 ردّ متعدّد: إن كانت الرسالة مُجابة، نُنشئ صفّاً جديداً
        _row = c.execute("SELECT reply FROM support_messages WHERE id=?",
                         (body.msg_id,)).fetchone()
        _has = bool(dict(_row).get("reply")) if _row else False
        if _has:
            c.execute(
                "INSERT INTO support_messages(user_id,message,reply,auto,created_at,replied_at) "
                "VALUES(?,?,?,?,?,?)",
                (uid, "", body.reply, 0, int(time.time()), int(time.time())))
        else:
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
        rows = c.execute("SELECT message,reply,auto,created_at,replied_at,media FROM support_messages "
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
            "SELECT id,message,reply,auto,created_at,replied_at,media "
            "FROM support_messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit)).fetchall()
        c.close()
        return {"messages": [dict(r) for r in reversed(rows)]}
    except Exception:
        return {"messages": []}


class DirectMsg(BaseModel):
    user_id: str
    reply: str = ""
    media: str = ""


@router.post("/api/admin/support/send")
async def admin_send(body: DirectMsg):
    """💬 رسالة مباشرة من الإدارة — بلا حاجة لرسالة معلّقة."""
    _init()
    now = int(time.time())
    try:
        c = sqlite3.connect(DB)
        c.execute(
            "INSERT INTO support_messages(user_id,message,reply,auto,created_at,replied_at,media) "
            "VALUES(?,?,?,?,?,?,?)",
            (body.user_id, "", body.reply, 0, now, now, body.media))
        c.commit(); c.close()
    except Exception as e:
        log.warning("send: %s", e)
        raise HTTPException(500, "تعذّر الحفظ")
    try:
        from routers.ws import registry
        await registry.send_to_user(body.user_id, {
            "event": "support_reply", "user_id": body.user_id, "reply": body.reply,
        })
    except Exception as e:
        log.debug("ws send: %s", e)
    return {"success": True}


# ═══════════ 📎 رفع الصور والفيديو ═══════════
UP_DIR = "/opt/whalex/static/uploads"
MAX_IMG = 10 * 1024 * 1024      # 10 ميجابايت
MAX_VID = 50 * 1024 * 1024      # 50 ميجابايت
# 📎 كل الصيغ الشائعة — الجوّالات ترسل heic و3gp وغيرها
OK_IMG = {
    "image/jpeg", "image/jpg", "image/pjpeg", "image/png", "image/webp",
    "image/gif", "image/bmp", "image/heic", "image/heif", "image/avif",
    "image/tiff", "image/svg+xml",
}
OK_VID = {
    "video/mp4", "video/webm", "video/quicktime", "video/x-msvideo",
    "video/x-matroska", "video/3gpp", "video/3gpp2", "video/mpeg",
    "video/x-ms-wmv", "video/ogg", "application/octet-stream",
}


@router.post("/api/support/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    """📎 رفع صورة أو فيديو — يُرجع رابطاً يُحفظ مع الرسالة."""
    import os, uuid as _uu
    os.makedirs(UP_DIR, exist_ok=True)
    ct = (file.content_type or "").lower()
    _ext = os.path.splitext(file.filename or "")[1].lower()
    VID_EXT = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".3gp", ".m4v", ".wmv", ".mpeg", ".mpg"}
    IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic", ".heif", ".avif", ".tiff", ".svg"}
    is_vid = ct in OK_VID or _ext in VID_EXT
    is_img = ct in OK_IMG or _ext in IMG_EXT
    if not is_vid and not is_img:
        raise HTTPException(400, f"نوع غير مدعوم: {ct or _ext}")
    if is_img:
        is_vid = False
    data = await file.read()
    cap = MAX_VID if is_vid else MAX_IMG
    if len(data) > cap:
        raise HTTPException(400, f"الحجم يتجاوز {cap // (1024*1024)} ميجابايت")
    ext = os.path.splitext(file.filename or "")[1].lower()[:6] or (
        ".mp4" if is_vid else ".jpg")
    name = f"{_uu.uuid4().hex}{ext}"
    with open(os.path.join(UP_DIR, name), "wb") as fh:
        fh.write(data)
    log.info("📎 رُفع %s (%.1f ميجا)", name, len(data) / 1048576)
    # 🎬 ضغط الفيديو في الخلفية — الرسالة تصل فوراً ثم يُستبدل الملف
    if is_vid:
        import threading
        threading.Thread(target=_compress_video,
                         args=(os.path.join(UP_DIR, name),), daemon=True).start()
    return {"url": f"/uploads/{name}", "kind": "video" if is_vid else "image"}


def _compress_video(path: str) -> None:
    """🎬 ضغط وتحسين للتشغيل السلس — faststart يبدأ الفيديو فوراً."""
    import subprocess, os, shutil
    tmp = path + ".tmp.mp4"
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", path,
             "-vcodec", "libx264", "-crf", "28", "-preset", "fast",
             "-vf", "scale='min(1280,iw)':-2",
             "-acodec", "aac", "-b:a", "96k",
             "-movflags", "+faststart", tmp],
            capture_output=True, timeout=600)
        if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 1000:
            before = os.path.getsize(path) / 1048576
            after = os.path.getsize(tmp) / 1048576
            shutil.move(tmp, path)
            os.chmod(path, 0o644)
            log.info("🎬 ضُغط %s: %.1f → %.1f ميجا",
                     os.path.basename(path), before, after)
        else:
            log.warning("🎬 فشل الضغط: %s", r.stderr[-200:] if r.stderr else "?")
    except Exception as e:
        log.warning("🎬 ضغط: %s", e)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


# ═══════ 👁️ تتبّع القراءة + كل الحسابات ═══════
def _reads_init():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS support_reads (
        user_id TEXT PRIMARY KEY, last_read INTEGER)""")
    c.commit(); c.close()


_reads_init()


@router.post("/api/admin/support/read")
async def mark_read(body: dict):
    """👁️ تُستدعى عند فتح المحادثة — تُصفّر عدّادها."""
    uid = str(body.get("user_id") or "")
    if not uid:
        raise HTTPException(400, "user_id مطلوب")
    c = sqlite3.connect(DB)
    c.execute("INSERT OR REPLACE INTO support_reads VALUES(?,?)",
              (uid, int(time.time())))
    c.commit(); c.close()
    return {"success": True}


@router.get("/api/admin/support/all")
async def all_threads():
    """👥 كل الحسابات — لبدء محادثة مع أي مستخدم."""
    _init(); _reads_init()
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    reads = {r["user_id"]: r["last_read"]
             for r in c.execute("SELECT * FROM support_reads")}
    stats = {}
    for r in c.execute("""
        SELECT user_id, COUNT(*) AS total, MAX(created_at) AS last_at,
               (SELECT message FROM support_messages m2
                 WHERE m2.user_id = m.user_id ORDER BY m2.id DESC LIMIT 1) AS last_msg,
               SUM(CASE WHEN message != '' THEN created_at ELSE 0 END) AS x
          FROM support_messages m GROUP BY user_id"""):
        stats[r["user_id"]] = dict(r)
    unread = {}
    for uid, st in stats.items():
        lr = reads.get(uid, 0)
        n = c.execute(
            "SELECT COUNT(*) FROM support_messages "
            "WHERE user_id=? AND message!='' AND created_at>?",
            (uid, lr)).fetchone()[0]
        unread[uid] = n
    out = []
    for r in c.execute("SELECT id, username, email, tier, display_id "
                       "FROM users ORDER BY tier DESC"):
        uid = r["id"]
        st = stats.get(uid, {})
        out.append({
            "user_id": uid,
            "username": r["username"] or r["email"] or "مستخدم",
            "display_id": r["display_id"],
            "tier": r["tier"] or "free",
            "total": st.get("total", 0),
            "last_msg": st.get("last_msg", ""),
            "last_at": st.get("last_at", 0),
            "unread": unread.get(uid, 0),
        })
    c.close()
    out.sort(key=lambda x: (-x["unread"], -(x["last_at"] or 0)))
    return {"threads": out}
