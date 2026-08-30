"""🛡️ حارس الهامش — لا نستهلك رصيد المشترك كلّه في الصفقات.

المشكلة المقيسة: مشترك رصيده 10.18$ فُتحت له ثلاث صفقات بهامش 6$،
فبقي متاحاً 4.13$ فقط. وأي حركة ضدّه تُصفّي مركزاً، ولا يبقى ما
يكفي لرسوم الفتح والإغلاق والتمويل.

فالحارس يحسب قبل كل صفقة:
  ① كم يبقى متاحاً بعدها؟
  ② هل تجاوزنا حصّة الرصيد المسموحة؟
  ③ هل عدد المراكز يناسب حجم الحساب؟

والقاعدة: نُبقي 5% من الرصيد سائلاً (أو 3$ أيّهما أكبر)، وعدد المراكز يتبع
الرصيد لا رقماً ثابتاً.
"""
import logging
import os

log = logging.getLogger("margin_guard")

RESERVE_PCT = 0.05          # نُبقي 5% سائلاً للرسوم والتمويل
MIN_RESERVE_USD = 3.0       # أو 3$ أيّهما أكبر — للحسابات الصغيرة
OFF_FLAG = "/opt/whalex/db/margin_guard.off"


MIN_TRADE_USD = 20.0        # 💵 لا صفقة تحت عشرين دولاراً
#   العمولة نسبة ثابتة، والصفقة الصغيرة لا يغطّي ربحها تكلفتها.
#   مقيس: صفقة 10$ ربحها 0.05$ وعمولتها 0.05$ — أي صفر صافٍ.
#   فالعدد يتبع الرصيد بهذا الحدّ، ولا نُصغّر المبلغ لنزيد العدد.
ABS_CAP = 30                # سقف مطلق — الهامش هو الحاكم الحقيقيّ
#   كان 12 فيمنع المشترك من أخذ كل إشارات البوت رغم اتّساع رصيده.


def max_positions_for(balance: float, trade_amount: float = 0.0) -> int:
    """كم مركزاً يحتمل هذا الرصيد؟ — يُشتقّ من الاحتياطيّ لا من جدول ثابت.

    القاعدة: نُبقي 5% سائلاً، والباقي يُقسَّم على مبلغ الصفقة.
    فرصيد 100$ بمبلغ 10$ يحتمل 6 مراكز، وبمبلغ 20$ يحتمل 3.
    """
    if balance <= 0:
        return 0
    reserve = max(balance * RESERVE_PCT, MIN_RESERVE_USD)
    usable = balance - reserve
    if usable <= 0:
        return 0
    amt = max(MIN_TRADE_USD, trade_amount or 0)
    return max(0, min(ABS_CAP, int(usable // amt)))


def safe_amount(balance: float, wanted: float, leverage: float,
                open_margin: float = 0.0) -> tuple:
    """
    كم يمكن أن نُخاطر بهذه الصفقة؟
    يُعيد (المبلغ المسموح، السبب) — والمبلغ 0 يعني: لا تفتح.
    """
    if os.path.exists(OFF_FLAG):
        return wanted, "الحارس مُطفأ"
    if balance <= 0:
        return 0.0, "لا رصيد"

    reserve = max(balance * RESERVE_PCT, MIN_RESERVE_USD)
    usable = balance - reserve - open_margin
    if usable <= 0:
        return 0.0, (f"لا هامش آمن — الرصيد {balance:.2f}$ "
                     f"والمحجوز {open_margin:.2f}$ والاحتياطيّ {reserve:.2f}$")

    # الهامش المطلوب لهذه الصفقة = المبلغ نفسه (المبلغ هو الهامش)
    if wanted <= usable:
        return wanted, f"مسموح — يبقى {usable - wanted:.2f}$ فوق الاحتياطيّ"

    # نُصغّر المبلغ ليناسب المتاح
    # 💵 لا نُصغّر تحت عشرين دولاراً — الصفقة الصغيرة تأكلها العمولة
    if usable >= MIN_TRADE_USD:
        return round(usable, 2), f"صُغِّر إلى {usable:.2f}$ لحماية الاحتياطيّ"
    return 0.0, (f"المتاح {usable:.2f}$ أقلّ من الحدّ الأدنى "
                 f"{MIN_TRADE_USD:.0f}$ — ننتظر إغلاق صفقة")


def check(balance: float, open_count: int, open_margin: float,
          wanted: float, leverage: float) -> tuple:
    """الفحص الكامل قبل الفتح. يُعيد (نفتح؟، المبلغ، السبب)."""
    if os.path.exists(OFF_FLAG):
        return True, wanted, "الحارس مُطفأ"

    cap = max_positions_for(balance, wanted)
    if open_count >= cap:
        return False, 0.0, (f"سقف المراكز {cap} لرصيد {balance:.2f}$ "
                            f"(مفتوح {open_count})")

    amt, why = safe_amount(balance, wanted, leverage, open_margin)
    if amt <= 0:
        return False, 0.0, why
    return True, amt, why
