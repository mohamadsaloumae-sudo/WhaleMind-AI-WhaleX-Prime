"""🧠 مُسجّل دورة حياة الصفقة — من الإشارة إلى النتيجة.

المشكلة المقيسة: النموذج يعرف نقطة الدخول والنتيجة النهائية فقط،
ولا يعرف ما حدث بينهما. فصفقة ربحت 2% بعد أن نزلت -5% تُعامَل
كصفقة ربحت 2% مباشرةً — وهما مختلفتان تماماً.

والمعيار الأكاديميّ (طريقة الحواجز الثلاثة، لوبيز دي برادو) يشترط
تسجيل المسار: أي حاجز لُمس أوّلاً — الربح أم الوقف أم الزمن —
وأعمق خسارة (MAE) وأعلى ربح (MFE) بلغتهما الصفقة قبل ذلك.
والحواجز يجب أن تتناسب مع تقلّب الأصل، فحركة 2% ضخمة في سوق
هادئ وتافهة في متقلّب.

فنُسجّل: MAE · MFE · زمن بلوغ القمّة · المدّة · ATR عند الدخول ·
تصنيف الحاجز · وحالة السوق عند الخروج.
"""
import logging
import sqlite3
import time

log = logging.getLogger("lifecycle")
DB = "/opt/whalex/ml_training.db"

# ذاكرة المسار الحيّ: (رمز, اتّجاه) → أرقام المسار
_paths = {}


def track(symbol: str, direction: str, entry: float, price: float,
          leverage: float = 1.0) -> None:
    """نبضة مراقبة — تُستدعى مع كل تحديث سعر لصفقة مفتوحة."""
    try:
        if entry <= 0 or price <= 0:
            return
        k = (symbol, str(direction).upper())
        sg = 1.0 if k[1] == "LONG" else -1.0
        pnl = (price - entry) / entry * 100.0 * (leverage or 1.0) * sg
        p = _paths.get(k)
        if p is None:
            p = {"mae": pnl, "mfe": pnl, "t0": time.time(),
                 "t_peak": time.time()}
            _paths[k] = p
        if pnl < p["mae"]:
            p["mae"] = pnl
        if pnl > p["mfe"]:
            p["mfe"] = pnl
            p["t_peak"] = time.time()
    except Exception as e:
        log.debug("تتبّع %s: %s", symbol, e)


def finish(symbol: str, direction: str, close_reason: str = "",
           atr_pct: float = None) -> dict:
    """عند الإغلاق: نكتب المسار في صفّ التدريب ونُفرغ الذاكرة."""
    k = (symbol, str(direction).upper())
    p = _paths.pop(k, None)
    if not p:
        return {}
    now = time.time()
    out = {
        "mae_pct": round(p["mae"], 4),
        "mfe_pct": round(p["mfe"], 4),
        "time_to_peak_min": round((p["t_peak"] - p["t0"]) / 60.0, 2),
        "duration_min": round((now - p["t0"]) / 60.0, 2),
        "barrier": _barrier(close_reason),
    }
    if atr_pct:
        out["atr_pct_entry"] = round(float(atr_pct), 3)
    try:
        c = sqlite3.connect(DB)
        row = c.execute(
            "SELECT id FROM training_signals WHERE symbol=? AND direction=? "
            "ORDER BY id DESC LIMIT 1", (symbol, k[1])).fetchone()
        if row:
            sets = ", ".join(f"{f}=?" for f in out)
            c.execute(f"UPDATE training_signals SET {sets} WHERE id=?",
                      (*out.values(), row[0]))
            c.commit()
        c.close()
    except Exception as e:
        log.debug("كتابة المسار %s: %s", symbol, e)
    return out


def _barrier(reason: str) -> str:
    """تصنيف الحاجز الذي لُمس أوّلاً."""
    r = str(reason or "").lower()
    if "sl" in r or "stop" in r or "طوارئ" in r:
        return "sl"
    # الركود يُفحَص قبل الحصاد — harvest_stall خروج زمنيّ لا هدف
    if "stall" in r or "time" in r or "expire" in r or "مهلة" in r:
        return "time"
    if "tp" in r or "harvest" in r or "lock" in r or "target" in r:
        return "tp"
    return "tactical"


def live_count() -> int:
    return len(_paths)
