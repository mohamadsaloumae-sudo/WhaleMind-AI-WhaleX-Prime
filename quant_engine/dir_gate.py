"""🧭 بوّابة الاتّجاه — بالرادار والاتّجاه والنظام معاً.

مقيس 18 سبتمبر على 4278 صفقة (30 يوماً). وكل رادار يختلف:

  PH  (شورت 100%): BULL +1.19% · FLAT +0.75% · BEAR +0.27%
      رابح في كل نظام — ومنع الشورت في السوق الصاعد كان سيقتل
      افضل حالاته. فالتعميم "لا شورت في سوق صاعد" خاطئ.

  SP  (لونج 100%): BEAR +0.28% · FLAT +0.16% · BULL -0.03%
      لا حالة خاسرة تُذكر — يمرّ كله.

  DIP (لونج 100%): FLAT -0.52% · BEAR +0.19%
      خاسر في السوق العرضي وحده.

  MX  (الاتجاهان): BULL/LONG +0.78% · BEAR/SHORT +0.59%
      BULL/SHORT -0.39% · BEAR/LONG -0.20% · FLAT/LONG -0.14%
      يتبع السوق: لونج في الصاعد وشورت في الهابط.

النتيجة: 4278 صفقة من +652.9 الى +1119.2 (توفير +466.2)
والمتوسط من +0.153% الى +0.432%، ونحتفظ بـ60% من الصفقات.

والسبب المباشر: السوق انقلب صعودا 17-18 سبتمبر و MX ظلّ يفتح
شورت — 13 صفقة بفوز 8% وصافي -48.9 في يوم واحد.

المقياس: تغيّر بتكوين في آخر 24 ساعة (6 شمعات 4h).
  ≥ +1.0% BULL · ≤ -1.0% BEAR · بينهما FLAT

الاطفاء: touch /opt/whalex/db/dir_gate.off
الظل   : touch /opt/whalex/db/dir_gate.shadow
"""
import os
import time
import logging

log = logging.getLogger("dir_gate")
OFF = "/opt/whalex/db/dir_gate.off"
SHADOW = "/opt/whalex/db/dir_gate.shadow"

BULL_TH = 1.0
BEAR_TH = -1.0
BARS = 6
CACHE_SEC = 300

# (رادار، اتّجاه، نظام) — كلّها متوسّطها سالب على عيّنة ≥300
BLOCK = {
    ("MX", "SHORT", "BULL"),   # -0.39% · 491 صفقة
    ("MX", "LONG", "BEAR"),    # -0.20% · 360 صفقة
    ("MX", "LONG", "FLAT"),    # -0.14% · 611 صفقة
    ("DIP", "LONG", "FLAT"),   # -0.52% · 226 صفقة
}

_cache = {"ts": 0, "reg": None, "ch": 0.0}


def _btc():
    now = time.time()
    if _cache["reg"] and now - _cache["ts"] < CACHE_SEC:
        return _cache["reg"], _cache["ch"]
    try:
        import json
        import urllib.request
        k = json.load(urllib.request.urlopen(
            "https://fapi.binance.com/fapi/v1/klines"
            "?symbol=BTCUSDT&interval=4h&limit=%d" % (BARS + 1), timeout=8))
        if len(k) < BARS:
            return None, 0.0
        rel = k[-BARS:]
        o, c = float(rel[0][1]), float(rel[-1][4])
        ch = (c - o) / o * 100 if o > 0 else 0.0
        reg = "BULL" if ch >= BULL_TH else ("BEAR" if ch <= BEAR_TH else "FLAT")
        _cache.update({"ts": now, "reg": reg, "ch": ch})
        return reg, ch
    except Exception as e:
        log.debug("btc: %s", e)
        return None, 0.0


def allow(tier, direction) -> tuple:
    """(نسمح؟, السبب). لا بيانات أو حالة غير مُقاسة ⇒ نمرّر."""
    if os.path.exists(OFF):
        return True, ""
    reg, ch = _btc()
    if not reg:
        return True, ""
    t = str(tier or "").upper()
    d = str(direction or "").upper()
    if (t, d, reg) not in BLOCK:
        return True, ""
    why = "%s %s في سوق %s (بتكوين %+.2f%%) — مقيس سالب" % (
        t, d, {"BULL": "صاعد", "BEAR": "هابط", "FLAT": "عرضيّ"}[reg], ch)
    if os.path.exists(SHADOW):
        log.info("🧭👁️ %s (ظلّ)", why)
        return True, ""
    return False, why


def current():
    reg, ch = _btc()
    return {"regime": reg, "btc_24h": round(ch, 2)}
