"""🪙 مدير السبوت بمنطق DCA — أوامر أمان تُخفّض المتوسط.

المشكلة المقيسة: المنطق القديم يقطع الخسارة عند -0.9% فوراً.
223 صفقة من 400 خرجت هكذا، كلّها خاسرة، بمجموع -202.8%.
وقياسنا أثبت أن 36% من هذه العملات صعدت فوق دخولنا بعد خروجنا.

والبديل المقيس على 157 مساراً حقيقياً بشموع خمس دقائق ونافذة
24 ساعة، بمحاكاة شمعةً بشمعة (الوقف أوّلاً ثم الهدف ثم أوامر
الأمان — بلا نظر للمستقبل):

  الواقع الحاليّ           -26.7% | فوز 40%
  أمان -2/-4 · هدف 2%     +177.9% | فوز 84% | ن1 +98 · ن2 +107
  ورأس المال المستهلَك ×1.76 · والوقف -12% لم يُضرَب ولا مرّة

فالفكرة: بدل قطع الخسارة الصغيرة، نشتري أكثر عند -2% و-4%
فينخفض متوسّطنا، ويكفي ارتداد بسيط ليُخرجنا رابحين.
"""
import logging

log = logging.getLogger("spot_dca")

SAFETY_LEVELS = (-2.0, -4.0)     # مستويات أوامر الأمان (% عن الدخول الأوّل)
TAKE_PROFIT = 2.0                # الهدف على المتوسط المرجّح
HARD_SL = -12.0                  # وقف صارم يُغلق كل شيء
MAX_HOURS = 48.0                 # مهلة قصوى


def avg_entry(lots) -> float:
    """المتوسط المرجّح لسعر الدخول."""
    if not lots:
        return 0.0
    tot_qty = sum(q for _p, q in lots)
    if tot_qty <= 0:
        return 0.0
    return sum(p * q for p, q in lots) / tot_qty


def decide(first_entry: float, price: float, lots: list,
           filled_levels: list, age_hours: float) -> tuple:
    """
    القرار في كل نبضة. يُعيد (الفعل، التفاصيل).
    الأفعال: 'hold' · 'safety' · 'take_profit' · 'stop'
    lots: [(سعر, كمّية), ...]  · filled_levels: المستويات المنفَّذة
    """
    if first_entry <= 0 or price <= 0:
        return "hold", {}
    move = (price - first_entry) / first_entry * 100.0
    avg = avg_entry(lots) or first_entry
    gain = (price - avg) / avg * 100.0

    # ① الوقف الصارم أوّلاً — الأسوأ يُفحص قبل الأفضل
    if move <= HARD_SL:
        return "stop", {"move": move, "gain": gain,
                        "why": f"وقف صارم {HARD_SL}% (تحرّك {move:.2f}%)"}

    # ② الهدف على المتوسط
    # تسامح مجهريّ: 99.96 على متوسط 98 يُعطي 1.9999999999999936%
    #   فيفوتنا الهدف بفارق لا يُرى. والسوق لا يفرّق بين هذا وذاك.
    if gain >= TAKE_PROFIT - 1e-9:
        return "take_profit", {"gain": gain, "avg": avg,
                               "why": f"هدف {TAKE_PROFIT}% على متوسط {avg:.8g}"}

    # ③ أمر أمان إن بلغنا مستوىً لم يُنفَّذ بعد
    for lv in SAFETY_LEVELS:
        if lv in filled_levels:
            continue
        if move <= lv:
            return "safety", {"level": lv, "move": move,
                              "why": f"أمان عند {lv}% (تحرّك {move:.2f}%)"}

    # ④ المهلة
    if age_hours >= MAX_HOURS:
        return "stop", {"move": move, "gain": gain,
                        "why": f"مهلة {MAX_HOURS:.0f} ساعة"}

    return "hold", {"move": move, "gain": gain, "avg": avg}
