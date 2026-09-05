"""🏷️ أسماء الرادارات — مصدر واحد لكل النظام.

الاسم إنجليزيّ دائماً مهما كانت لغة الصفحة، فهو علامة تجارية لا
تُترجَم — كما لا يُترجَم اسم المنصّة. والوصف وحده يتبع اللغة.

وكان المشترك يرى "🌐 Binance · باينانس" و"🔭 Explosion Scout"
فلا يعرف أي رادار أصدر الإشارة.
"""

RADARS = {
    "A":    ("⚡", "WhaleX Predator",
             "العملات الآمنة على باينانس", "Safe coins on Binance"),
    "B":    ("⚡", "WhaleX Predator",
             "العملات الآمنة على باينانس", "Safe coins on Binance"),
    "S":    ("⚡", "WhaleX Predator",
             "العملات الآمنة على باينانس", "Safe coins on Binance"),
    "MX":   ("⚡", "WhaleX Predator MX",
             "العملات الحصرية على ستّ منصّات", "Exclusive coins, six venues"),
    "PH":   ("🔻", "WhaleX Short",
             "يلتقط انهيار القمّة", "Catches the top breaking down"),
    "DIP":  ("🔺", "WhaleX Long",
             "يلتقط الارتداد من القاع", "Catches the bounce off the floor"),
    "LV2":  ("🔬", "WhaleX Long V2",
             "يرصد نضوب البيع المُرافَع", "Leveraged sell exhaustion"),
    "SP":   ("🪙", "WhaleX Spot",
             "تداول فوريّ بلا رافعة", "Spot trading, no leverage"),
    "SPOT": ("🪙", "WhaleX Spot",
             "تداول فوريّ بلا رافعة", "Spot trading, no leverage"),
    "MEME": ("🐸", "WhaleX Meme",
             "عملات الميم الجديدة", "Fresh meme coins"),
}

_FALLBACK = ("🐋", "WhaleX", "", "")


def radar_of(tier: str) -> tuple:
    return RADARS.get(str(tier or "").upper(), _FALLBACK)


def label(tier: str) -> str:
    """الاسم الكامل مع الرمز — إنجليزيّ دائماً."""
    icon, name, _ar, _en = radar_of(tier)
    return f"{icon} {name}"


def name(tier: str) -> str:
    """الاسم وحده بلا رمز."""
    return radar_of(tier)[1]


def desc(tier: str, lang: str = "ar") -> str:
    """الوصف — يتبع اللغة."""
    _i, _n, ar, en = radar_of(tier)
    return ar if lang == "ar" else en
