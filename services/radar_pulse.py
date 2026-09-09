"""🩺 نبض الرادارات — الحالة من الواقع لا من نص ثابت.

الفلسفة: نقرأ سجل الخدمة نفسه. صفر لمس للرادارات وصفر كتابة
في قاعدة البيانات. الرادار الذي يمسح يترك اثرا في السجل،
وغياب الاثر هو الدليل الوحيد المقبول على التوقف.

مقيس 9 سبتمبر: كل رادار ودورته الفعلية
  predator 45s · short 3m · long 2m · spot 16s · meme 1m · mx 11m
والعتبة لكل واحد ثلاثة اضعاف دورته، فلا نعلن توقف من يعمل ببطء.

الاطفاء: touch /opt/whalex/db/radar_pulse.off
"""
import re
import time
import logging
import subprocess

log = logging.getLogger("radar_pulse")

OFF_FLAG = "/opt/whalex/db/radar_pulse.off"

# اسم المسجل في السجل -> مفتاح الرادار
LOGGERS = {
    "engine": "predator",
    "multi_scan": "mx",
    "explosion_scout": "short",
    "whalex_long_v2": "long",
    "dip_hunter": "long",
    "spot_scan": "spot",
    "spot_scout": "spot",
    "meme_v2": "meme",
}

# المفتاح -> (الاسم المعروض، الرمز، السوق، عتبة الصمت بالثواني)
RADARS = {
    "predator": ("WhaleX Predator", "⚡", "futures", 300),
    "mx":       ("WhaleX Predator MX", "⚡", "futures", 2400),
    "short":    ("WhaleX Short", "🎯", "futures", 900),
    "long":     ("WhaleX Long", "📈", "futures", 600),
    "spot":     ("WhaleX Spot", "🪙", "spot", 300),
    "meme":     ("WhaleX Meme", "🐸", "meme", 600),
}

_LINE = re.compile(r"^(\d+)\.\d+ .*?(?:INFO|WARNING|ERROR)\s+([a-z_0-9]+)\s+-")

_CACHE: dict = {}
_CACHE_TS = 0.0
CACHE_SEC = 20.0


def _scan_journal(minutes: int = 60) -> dict:
    """اخر نبضة لكل رادار من سجل الخدمة."""
    try:
        out = subprocess.run(
            ["journalctl", "-u", "whalex", "--since", f"-{minutes}min",
             "--no-pager", "-o", "short-unix"],
            capture_output=True, text=True, timeout=25).stdout
    except Exception as e:
        log.warning("journal read: %s", str(e)[:60])
        return {}
    last: dict = {}
    for ln in out.splitlines():
        m = _LINE.match(ln)
        if not m:
            continue
        key = LOGGERS.get(m.group(2))
        if not key:
            continue
        ts = int(m.group(1))
        if ts > last.get(key, 0):
            last[key] = ts
    return last


def status() -> dict:
    """حالة كل رادار — مع كاش قصير كي لا نقرا السجل مع كل طلب."""
    global _CACHE, _CACHE_TS
    import os
    if os.path.exists(OFF_FLAG):
        return {"ok": False, "off": True, "radars": []}
    now = time.time()
    if _CACHE and (now - _CACHE_TS) < CACHE_SEC:
        return _CACHE
    last = _scan_journal(60)
    out = []
    for key, (name, icon, market, limit) in RADARS.items():
        ts = last.get(key)
        if not ts:
            state, ago = "unknown", None
        else:
            ago = int(now - ts)
            state = "live" if ago <= limit else ("slow" if ago <= limit * 3 else "down")
        out.append({
            "key": key, "name": name, "icon": icon, "market": market,
            "state": state, "seconds_ago": ago,
        })
    _CACHE = {"ok": True, "off": False, "radars": out, "ts": int(now)}
    _CACHE_TS = now
    return _CACHE
