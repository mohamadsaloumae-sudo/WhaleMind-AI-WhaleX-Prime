"""قائمة الحظر المركزية — يقرأ منها كل الرادارات.

المشكلة المقيسة: 9 عملات كلّفت -339%، ومتوسط ذروتها 2.8%
مقابل 9.7% للرابحات — اي تذهب ضدنا فوراً بلا فرصة.
وبصمة صيد التصفيات: وقف واسع (تقلّب عالٍ) وذروة ضعيفة.

الملف: /opt/whalex/db/blocked_symbols.txt — عملة في كل سطر.
يُقرأ كل 60 ثانية، فالتعديل يسري بلا اعادة تشغيل.
السطر الذي يبدا بـ# تعليق.
"""
import logging
import os
import time

log = logging.getLogger("blocklist")

BLOCKED_FILE = "/opt/whalex/db/blocked_symbols.txt"
_CACHE = {"ts": 0.0, "set": frozenset()}


def blocked_set() -> frozenset:
    """القائمة الحالية — ذاكرة مؤقتة 60 ثانية."""
    try:
        now = time.time()
        if now - _CACHE["ts"] > 60:
            _CACHE["ts"] = now
            if os.path.exists(BLOCKED_FILE):
                with open(BLOCKED_FILE) as f:
                    _CACHE["set"] = frozenset(
                        ln.strip().upper() for ln in f
                        if ln.strip() and not ln.strip().startswith("#"))
            else:
                _CACHE["set"] = frozenset()
    except Exception as e:
        log.debug("blocklist read: %s", e)
    return _CACHE["set"]


def is_blocked(symbol) -> bool:
    """هل العملة محظورة؟ اي خطأ يعني السماح — الفشل يفتح لا يغلق."""
    try:
        return str(symbol or "").upper() in blocked_set()
    except Exception:
        return False
