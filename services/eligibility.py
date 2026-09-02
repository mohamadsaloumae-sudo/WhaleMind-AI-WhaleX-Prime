"""بوابة الاهلية — لا نحاول مع من لا تكتمل شروطه.

المشكلة المقيسة: اربعة مشتركين من تسعة مفاتيحهم معطلة، والنظام
يحاول معهم في كل اشارة فيفشل. سجل 31 اغسطس: 355 محاولة فاشلة
لمشترك واحد. وهذا يغرق باينانس بطلبات مرفوضة — وخطرها حظر IP.

ثلاثة ضمانات:
  1 الفشل يفتح لا يغلق — اي خطا يعني السماح لا الحجب
  2 لا حجب من اول فشل — فشلان متتاليان (الشبكة تخطئ مرة)
  3 الحجب للفتح وحده — الاغلاق والادارة لا يمسهما شيء

وضع المراقبة: touch /opt/whalex/db/eligibility.shadow
الاطفاء الكامل: touch /opt/whalex/db/eligibility.off
"""
import logging
import os
import sqlite3
import time

log = logging.getLogger("eligibility")

DB = "/opt/whalex/db/whalex.db"
REFRESH_SEC = 900
STALE_SEC = 3600
FAILS_BEFORE_BLOCK = 2
MIN_BALANCE_FILE = "/opt/whalex/db/eligibility_min_balance.txt"
MIN_BALANCE_DEFAULT = 300.0
OFF_FLAG = "/opt/whalex/db/eligibility.off"
SHADOW_FLAG = "/opt/whalex/db/eligibility.shadow"
GRACE_DAYS = 7

_CACHE = {}
_STATS = {"allowed": 0, "blocked": 0, "shadow": 0, "unknown": 0}


def _min_balance():
    try:
        with open(MIN_BALANCE_FILE) as f:
            return float(f.read().strip())
    except Exception:
        return MIN_BALANCE_DEFAULT


def _grace_init():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS eligibility_grace(
        user_id TEXT PRIMARY KEY, reason TEXT,
        started_at INTEGER, notified_at INTEGER)""")
    c.commit(); c.close()


def _grace_get(uid):
    try:
        _grace_init()
        c = sqlite3.connect(DB)
        r = c.execute("SELECT started_at, notified_at FROM eligibility_grace "
                      "WHERE user_id=?", (uid,)).fetchone()
        c.close()
        return r
    except Exception as e:
        log.debug("grace_get: %s", e)
        return None


def _grace_start(uid, reason):
    try:
        _grace_init()
        c = sqlite3.connect(DB)
        c.execute("INSERT OR IGNORE INTO eligibility_grace"
                  "(user_id,reason,started_at,notified_at) VALUES(?,?,?,0)",
                  (uid, reason, int(time.time())))
        c.commit(); c.close()
    except Exception as e:
        log.debug("grace_start: %s", e)


def _grace_clear(uid):
    try:
        c = sqlite3.connect(DB)
        c.execute("DELETE FROM eligibility_grace WHERE user_id=?", (uid,))
        c.commit(); c.close()
    except Exception as e:
        log.debug("grace_clear: %s", e)


def _grace_notify(uid, days_left, bal):
    try:
        r = _grace_get(uid)
        last = (r[1] if r else 0) or 0
        if time.time() - last < 20 * 3600:
            return
        mb = _min_balance()
        if days_left > 0:
            txt = ("تنبيه من وِيل إكس\n\n"
                   "رصيدك %.2f$ — والحدّ الأدنى للتداول %.0f$.\n\n"
                   "والسبب أن عمولة المنصّة ورسم الاشتراك يأكلان ربح "
                   "رأس المال الصغير، فتتداول بلا فائدة.\n\n"
                   "أمامك %d يوماً، ثم يتوقّف التداول تلقائياً.\n\n"
                   "الحلّ: حوّل USDT إلى محفظة العقود الآجلة حتى %.0f$ "
                   "فأكثر — ويعود التداول فوراً.\n\n"
                   "وتفاصيل خطّة التداول في دليل المستخدم."
                   ) % (bal, mb, days_left, mb)
        else:
            txt = ("توقّف التداول — وِيل إكس\n\n"
                   "رصيدك %.2f$ دون الحدّ الأدنى %.0f$، "
                   "وانتهت مهلة الأسبوع.\n\n"
                   "لا صفقات جديدة حتى يبلغ رصيدك %.0f$.\n\n"
                   "وصفقاتك المفتوحة — إن وُجدت — تُدار وتُغلق طبيعياً.\n\n"
                   "حوّل USDT إلى محفظة العقود الآجلة ويعود التداول فوراً."
                   ) % (bal, mb, mb)
        c = sqlite3.connect(DB)
        c.execute("INSERT INTO user_messages(user_id,message,created_at,seen) "
                  "VALUES(?,?,?,0)", (uid, txt, int(time.time())))
        c.execute("UPDATE eligibility_grace SET notified_at=? WHERE user_id=?",
                  (int(time.time()), uid))
        c.commit(); c.close()
        log.info("تنبيه رصيد %s — %d يوم متبق", uid[:8], days_left)
    except Exception as e:
        log.debug("grace_notify: %s", e)


def grace_state(uid, bal):
    r = _grace_get(uid)
    if not r:
        _grace_start(uid, "low_balance")
        _grace_notify(uid, GRACE_DAYS, bal)
        return True, "مهلة %d ايام" % GRACE_DAYS
    started = r[0] or int(time.time())
    days = (time.time() - started) / 86400.0
    left = int(GRACE_DAYS - days + 0.999)
    if days < GRACE_DAYS:
        _grace_notify(uid, max(1, left), bal)
        return True, "مهلة — %d يوم متبق" % max(1, left)
    _grace_notify(uid, 0, bal)
    return False, "الرصيد %.2f$ دون %.0f$ — انتهت المهلة" % (bal, _min_balance())


def _judge(d):
    err = str(d.get("error") or "")
    if "لم يربط" in err:
        return False, "لا مفتاح مربوط"
    if "-2014" in err or "format invalid" in err:
        return False, "المفتاح مشوَّه"
    if "-2015" in err or "Invalid API-key" in err:
        return False, "المفتاح مرفوض أو الخادم غير مسموح"
    if d.get("key_valid") is False:
        return False, "المفتاح لا يعمل"
    if d.get("futures_enabled") is False:
        return False, "صلاحية العقود الآجلة غير مفعّلة"
    if not d.get("auto_trade_on"):
        return False, "التداول الآليّ مُطفأ"
    if d.get("disabled_reason"):
        return False, "معطَّل: " + str(d["disabled_reason"])[:40]
    bal = d.get("futures_balance")
    if bal is not None and float(bal) < _min_balance():
        return grace_state(d.get("_uid", ""), float(bal))
    if bal is not None:
        _grace_clear(d.get("_uid", ""))
    return True, ""


def allowed(user_id):
    """هل نحاول مع هذا المشترك؟ قراءة ذاكرة فقط — بلا شبكة."""
    try:
        if os.path.exists(OFF_FLAG):
            return True, ""
        e = _CACHE.get(user_id)
        if not e:
            _STATS["unknown"] += 1
            return True, ""
        if (time.time() - e["ts"]) > STALE_SEC:
            _STATS["unknown"] += 1
            return True, ""
        if e["ok"]:
            _STATS["allowed"] += 1
            return True, ""
        if e.get("fails", 0) < FAILS_BEFORE_BLOCK:
            _STATS["allowed"] += 1
            return True, ""
        if os.path.exists(SHADOW_FLAG):
            _STATS["shadow"] += 1
            log.info("SHADOW كان سيُحجب %s — %s", user_id[:8], e["why"])
            return True, ""
        _STATS["blocked"] += 1
        return False, e["why"]
    except Exception as ex:
        log.debug("allowed: %s", ex)
        return True, ""


def refresh_one(user_id):
    from services.binance_diag import diagnose
    prev = _CACHE.get(user_id, {})
    try:
        d = diagnose(user_id)
        d["_uid"] = user_id
        ok, why = _judge(d)
    except Exception as e:
        log.debug("diagnose %s: %s", user_id[:8], e)
        return prev or {}
    fails = 0 if ok else int(prev.get("fails", 0)) + 1
    ent = {"ok": ok, "why": why, "ts": time.time(), "fails": fails}
    _CACHE[user_id] = ent
    if prev.get("ok") is True and not ok:
        log.warning("GATE %s صار غير مؤهَّل — %s", user_id[:8], why)
    elif prev.get("ok") is False and ok:
        log.info("GATE %s عاد مؤهَّلاً", user_id[:8])
    return ent


def refresh_all():
    try:
        c = sqlite3.connect(DB)
        ids = [r[0] for r in c.execute(
            "SELECT DISTINCT user_id FROM user_binance_credentials")]
        c.close()
    except Exception as e:
        log.error("قائمة المشتركين: %s", e)
        return {}
    ok = bad = 0
    for uid in ids:
        e = refresh_one(uid)
        if e.get("ok"):
            ok += 1
        elif e:
            bad += 1
    log.info("GATE الأهلية: مؤهَّل %d · غير مؤهَّل %d · من %d", ok, bad, len(ids))
    return {"ok": ok, "bad": bad, "total": len(ids)}


def snapshot():
    return {"stats": dict(_STATS),
            "shadow": os.path.exists(SHADOW_FLAG),
            "off": os.path.exists(OFF_FLAG),
            "min_balance": _min_balance(),
            "users": {k[:8]: {"ok": v["ok"], "why": v["why"],
                              "fails": v.get("fails", 0),
                              "age_sec": int(time.time() - v["ts"])}
                      for k, v in _CACHE.items()}}


async def eligibility_loop():
    import asyncio
    log.info("GATE بوابة الأهلية بدأت — فحص كل %d دقيقة", REFRESH_SEC // 60)
    await asyncio.sleep(30)
    while True:
        try:
            if not os.path.exists(OFF_FLAG):
                await asyncio.to_thread(refresh_all)
        except Exception as e:
            log.error("حلقة الأهلية: %s", e)
        await asyncio.sleep(REFRESH_SEC)
