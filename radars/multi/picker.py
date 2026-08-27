"""🎯 فلتر الانتقاء — يجمع إشارات الدورة ويفتح أقواها فقط.

المشكلة: الرادار يُصدر فور فحص كل عملة، فتُفتح الصفقات بترتيب الوصول
لا الجودة. وحين تبلغ الحصّة، تُرفض إشارة أقوى لأن أضعف سبقتها.

القياس على 1,956 صفقة MX (911 دورة):
  الكلّ            1,956 صفقة | فوز 48% | صافي  +91.7%
  أقوى 5 لكل دورة  1,339 صفقة | فوز 50% | صافي +242.2%
والمكسب أغلبه من استبعاد الضعيفة (MIN_RANK) لا من الترتيب — لأن
متوسط الإشارات كان 2.1 لكل دورة. أمّا اليوم فالكون 385 عملة وأعطت
دورة واحدة 53 إشارة، فالتصفية تصير أنفع بكثير.

المعيار من عوامل أثبتت تمييزاً فعلياً (لا من النقاط، فهي لا تُميّز):
  • عرض الوقف 4-8%     → فوز 65% · متوسط +1.54%
  • الرافعة 3x         → فوز 59% · متوسط +1.05%
  • موقع النطاق 50-75% → فوز 63% · متوسط +1.27%

⚠️ خاصّ بـMX: القياس على PH أعطى فوز 40% مقابل 46% للكلّ — أي يضرّه.
"""
import logging
import os

log = logging.getLogger("mx_picker")

TOP_N = 5
MIN_RANK = 1.5
OFF_FLAG = "/opt/whalex/db/picker.off"


def enabled() -> bool:
    return not os.path.exists(OFF_FLAG)


def _from_tuple(t):
    """
    يحوّل عنصر السلّة إلى قاموس.
    الماسح يُمرّر: (row, score, direction, reasons, price, lv, rsi, range_pos, vol_ratio)
    والبيانات موزّعة — فلا يجدها الفلتر في row وحده.
    """
    try:
        row, sc, _d, _r, price, lv, _rsi, rpos, _vr = t
        return {
            "symbol": (row["symbol"] if hasattr(row, "keys") else row.get("symbol", "?")),
            "entry": float(price or 0),
            "sl": float((lv or {}).get("sl") or 0),
            "sl_pct": float((lv or {}).get("sl_pct") or 0),
            "leverage": float((lv or {}).get("leverage") or 0),
            "range_pos": float(rpos or 0),
            "score": float(sc or 0),
        }
    except Exception:
        return None


def rank(sig) -> float:
    """درجة الجودة — كلّما ارتفعت ارتفع احتمال الربح."""
    def g(k, d=0):
        try:
            v = sig.get(k) if isinstance(sig, dict) else getattr(sig, k, d)
            return float(v or d)
        except Exception:
            return float(d)

    if isinstance(sig, (tuple, list)):
        _c = _from_tuple(sig)
        if _c is None:
            return 0.0
        sig = _c

        def g(k, d=0):
            try:
                return float(sig.get(k) or d)
            except Exception:
                return float(d)

    s = 0.0
    entry, sl = g("entry"), g("sl")
    if entry > 0 and sl > 0:
        slp = abs((sl - entry) / entry * 100)
        if 4 <= slp < 8:
            s += 3.0
        elif 2 <= slp < 4:
            s += 1.0
        elif slp >= 8:
            s -= 2.0
    lev = g("leverage", 0)
    if lev > 0:
        if lev <= 3.5:
            s += 2.5
        elif lev <= 4.5:
            s += 0.5
    else:
        # الرافعة تُحدَّد لاحقاً في مدير الصفقات — نُحيّد العامل
        s += 1.0
    rp = g("range_pos")
    rp = rp * 100 if rp <= 1 else rp
    if 50 <= rp < 75:
        s += 2.0
    elif rp < 25:
        s += 0.5
    s += min(1.0, g("score") / 10)
    return round(s, 2)


def why(sig) -> str:
    if isinstance(sig, (tuple, list)):
        sig = _from_tuple(sig) or {}
    def g(k, d=0):
        try:
            v = sig.get(k) if isinstance(sig, dict) else getattr(sig, k, d)
            return float(v or d)
        except Exception:
            return float(d)
    entry, sl = g("entry"), g("sl")
    slp = abs((sl - entry) / entry * 100) if (entry > 0 and sl > 0) else 0
    rp = g("range_pos")
    rp = rp * 100 if rp <= 1 else rp
    return f"وقف {slp:.1f}% · {g('leverage'):.0f}x · موقع {rp:.0f}%"


def pick(signals: list, top_n: int = TOP_N) -> tuple:
    """يُعيد (المختارة، المتروكة) — والقرار النهائيّ لمدير الصفقات."""
    if not signals:
        return [], []
    if not enabled():
        return list(signals), []
    scored = [(rank(s), s) for s in signals]
    weak = [(r, s) for r, s in scored if r < MIN_RANK]
    strong = sorted([(r, s) for r, s in scored if r >= MIN_RANK], key=lambda x: -x[0])
    picked = [s for _r, s in strong[:top_n]]
    left = [s for _r, s in strong[top_n:]] + [s for _r, s in weak]
    if signals:
        log.info("🎯 الفلتر: %d إشارة → %d مختارة | ضعيفة %d · فائضة %d",
                 len(signals), len(picked), len(weak), max(0, len(strong) - top_n))
        for _r, s in strong[:top_n]:
            _sym = s.get("symbol") if isinstance(s, dict) else getattr(s, "symbol", "?")
            log.info("   ✅ %s درجة %.2f | %s", _sym, _r, why(s))
    return picked, left
