"""🪙🧠 دماغ السبوت الثاني — نموذج أوزان مُدرَّب على المسار الكامل.

القديم مات: 180 صفّاً و65% بلا نتيجة وآخر تسجيل قبل 308 ساعة،
وأربعة حقول فقط، وتنبّؤه بحث تشابه بدائيّ لا نموذج.

والجديد مبنيّ على 446 صفقة بثمانية وعشرين حقلاً، تشمل سياق الدخول
(z-score · بولنجر · RSI-2 · RSI-14 · ATR) ومسار الصفقة (MAE · MFE ·
زمن القمّة · الحاجز الذي لُمس أوّلاً).

وأبرز ما كشفه التدريب:
  taker 0.55-0.65   فوز 50.0%  ← ضغط شراء معتدل
  vol_infl 1.2-2    فوز 50.0%  ← والحجم المتطرّف (2-4) يفوز 34.6% فقط
  path breakout     فوز 47.1%  (51 صفقة)
  path pullback     فوز 34.5%  (354 صفقة — عمودنا الفقريّ وهو الأسوأ)
  rsi2 <15          فوز 25.9%  ← المُشبَع بيعاً يقتلنا
"""
import json
import logging
import math
import os
import sqlite3
import time

log = logging.getLogger("spot_brain2")
DB = "/opt/whalex/db/whalex.db"
MODEL = "/opt/whalex/spot_model.json"
OFF_FLAG = "/opt/whalex/db/spot_brain2.off"
VETO_BELOW = 0.30          # نمنع دون هذا الاحتمال

_cache = {"m": None, "ts": 0}

BINS = {
 "zscore":   [(-99,-1.0,"<-1.0"),(-1.0,-0.4,"-1..-0.4"),(-0.4,0.4,"-0.4..0.4"),(0.4,99,">0.4")],
 "bb_pos":   [(-99,0.2,"<0.2"),(0.2,0.45,"0.2-0.45"),(0.45,0.7,"0.45-0.7"),(0.7,99,">0.7")],
 "rsi2":     [(0,15,"<15"),(15,50,"15-50"),(50,85,"50-85"),(85,101,">85")],
 "rsi14":    [(0,35,"<35"),(35,48,"35-48"),(48,60,"48-60"),(60,101,">60")],
 "atr_pct":  [(0,1.5,"<1.5"),(1.5,3,"1.5-3"),(3,6,"3-6"),(6,99,">6")],
 "taker":    [(0,0.45,"<0.45"),(0.45,0.55,"0.45-0.55"),(0.55,0.65,"0.55-0.65"),(0.65,9,">0.65")],
 "vol_infl": [(0,1.2,"<1.2"),(1.2,2,"1.2-2"),(2,4,"2-4"),(4,999,">4")],
 "range_pos":[(0,0.15,"<0.15"),(0.15,0.35,"0.15-0.35"),(0.35,0.6,"0.35-0.6"),(0.6,9,">0.6")],
 "hour_utc": [(0,6,"00-06"),(6,12,"06-12"),(12,18,"12-18"),(18,24,"18-24")],
}


def _model():
    """يُحمّل النموذج ويُعيد تحميله كل عشر دقائق."""
    now = time.time()
    if _cache["m"] and now - _cache["ts"] < 600:
        return _cache["m"]
    try:
        _cache["m"] = json.load(open(MODEL, encoding="utf-8"))
        _cache["ts"] = now
    except Exception as e:
        log.debug("تحميل النموذج: %s", e)
        _cache["m"] = None
    return _cache["m"]


def _bucket(name, v):
    if v is None: return None
    for lo, hi, lbl in BINS.get(name, []):
        if lo <= v < hi: return lbl
    return None


def predict(feats: dict) -> tuple:
    """يُعيد (احتمال النجاح، الشرح). وأي نقص يُعيد الأساس."""
    m = _model()
    if not m:
        return 0.40, "لا نموذج"
    z = float(m.get("prior") or 0)
    parts = []
    W = m.get("weights") or {}
    for name, bins in BINS.items():
        b = _bucket(name, feats.get(name))
        if b is None: continue
        d = (W.get(name) or {}).get(b)
        if not d: continue
        z += float(d.get("w") or 0)
        if abs(float(d.get("w") or 0)) >= 0.25:
            parts.append(f"{name}={b}({d['w']:+.2f})")
    # مسار الدخول
    p = feats.get("path")
    if p:
        d = (W.get("path") or {}).get(str(p))
        if d:
            z += float(d.get("w") or 0)
            parts.append(f"path={p}({d['w']:+.2f})")
    prob = 1.0 / (1.0 + math.exp(-z))
    return round(prob, 4), " · ".join(parts[:5])


def should_enter(feats: dict) -> tuple:
    """بوّابة الدخول. يُعيد (نقبل؟، الاحتمال، الشرح)."""
    if os.path.exists(OFF_FLAG):
        return True, 0.5, "الدماغ مُطفأ"
    try:
        prob, why = predict(feats)
        if prob < VETO_BELOW:
            return False, prob, f"احتمال {prob*100:.0f}% دون {VETO_BELOW*100:.0f}% · {why}"
        return True, prob, why
    except Exception as e:
        log.debug("بوّابة الدماغ: %s", e)
        return True, 0.5, ""


def record(row: dict) -> None:
    """يُسجّل صفقة مغلقة في جدول التدريب."""
    try:
        c = sqlite3.connect(DB)
        keys = [k for k in row if k not in ("id",)]
        q = ", ".join(keys); ph = ", ".join("?" * len(keys))
        c.execute(f"INSERT OR IGNORE INTO spot_train_v2 ({q}) VALUES ({ph})",
                  [row[k] for k in keys])
        c.commit(); c.close()
    except Exception as e:
        log.debug("تسجيل السبوت: %s", e)
