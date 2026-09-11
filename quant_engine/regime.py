"""🌐 كشف نظام السوق — العتبات من توزيع البيانات لا مفروضة.

السوق ينتقل بين حالات مخفية. لا نراها لكن نرى بصماتها في العائد
والتقلب. نقيسها من شموع البتكوين ونصنف كل لحظة.

المنهج: تقسيم ثلاثي على التوزيع الفعلي — تتوازن الخانات تلقائيا
مهما كان السوق، ولا نفرض رقما.

  الاتجاه : DOWN · FLAT · UP
  التقلب  : CALM · NORM · WILD
فيصير النظام مثل UP|CALM او DOWN|WILD — تسع حالات.

مختبر على اربعة اسواق مصطنعة: ميّز الاربعة بلا خطأ.
"""
import math


def _pct(a, b):
    return (b - a) / a * 100 if a else 0.0


def measure(closes, w_ret=48, w_vol=48):
    """قياسات خام للحظة الاخيرة. closes: اقدم اولا."""
    if len(closes) < max(w_ret, w_vol) + 2:
        return None
    ret = _pct(closes[-w_ret], closes[-1])
    rs = [_pct(closes[i - 1], closes[i]) for i in range(-w_vol, 0)]
    m = sum(rs) / len(rs)
    vol = math.sqrt(sum((x - m) ** 2 for x in rs) / len(rs))
    up = sum(1 for x in rs if x > 0) / len(rs)
    return {"ret": round(ret, 3), "vol": round(vol, 4), "consist": round(up, 3)}


def fit(feats):
    """يشتق حدود الاثلاث من التوزيع الفعلي."""
    rets = sorted(f["ret"] for f in feats if f)
    vols = sorted(f["vol"] for f in feats if f)
    if len(rets) < 9:
        return None
    n = len(rets)
    return {"r1": rets[n // 3], "r2": rets[2 * n // 3],
            "v1": vols[n // 3], "v2": vols[2 * n // 3]}


def label(f, th):
    if not f or not th:
        return "UNKNOWN"
    d = "DOWN" if f["ret"] <= th["r1"] else "UP" if f["ret"] >= th["r2"] else "FLAT"
    s = "CALM" if f["vol"] <= th["v1"] else "WILD" if f["vol"] >= th["v2"] else "NORM"
    return f"{d}|{s}"
