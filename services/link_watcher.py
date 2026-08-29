"""🔔 حارس الربط — يكتشف خلل مفتاح المشترك ويُرشده تلقائياً.

المشكلة المقيسة: تسعة مشتركين ربطوا مفاتيحهم، والثلاثة الذين فُحصوا
لم يفعّلوا صلاحية العقود الآجلة — فيراسلون الدعم قائلين "ربطتُ ولا
يتداول"، ولا نعرف السبب إلا بالسؤال.

فالحارس يفحص كل ستّ ساعات، ويرسل رسالة واحدة واضحة في دردشة المشترك
حين يجد خللاً، ولا يُكرّرها قبل أربع وعشرين ساعة.

والرسالة بالعربية وحدها — لا خلط.
"""
import logging
import sqlite3
import time

log = logging.getLogger("link_watcher")

DB = "/opt/whalex/db/whalex.db"
COOLDOWN = 24 * 3600
CHECK_EVERY = 6 * 3600
OFF_FLAG = "/opt/whalex/db/link_watcher.off"


def _init():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS link_alerts(
        user_id TEXT, problem TEXT, sent_at INTEGER,
        PRIMARY KEY(user_id, problem))""")
    c.commit(); c.close()


def _recent(user_id: str, key: str) -> bool:
    try:
        c = sqlite3.connect(DB)
        r = c.execute("SELECT sent_at FROM link_alerts WHERE user_id=? AND problem=?",
                      (user_id, key)).fetchone()
        c.close()
        return bool(r and (time.time() - (r[0] or 0)) < COOLDOWN)
    except Exception:
        return False


def _remember(user_id: str, key: str):
    try:
        c = sqlite3.connect(DB)
        c.execute("INSERT OR REPLACE INTO link_alerts(user_id,problem,sent_at) "
                  "VALUES(?,?,?)", (user_id, key, int(time.time())))
        c.commit(); c.close()
    except Exception as e:
        log.debug("remember: %s", e)


def _send(user_id: str, text: str):
    try:
        c = sqlite3.connect(DB)
        c.execute("INSERT INTO user_messages(user_id,message,created_at,seen) "
                  "VALUES(?,?,?,0)", (user_id, text, int(time.time())))
        c.commit(); c.close()
        log.info("🔔 أُرسل إرشاد إلى %s", user_id[:8])
        return True
    except Exception as e:
        log.warning("send: %s", e)
        return False


def message_for(d: dict) -> tuple:
    """يُعيد (المفتاح، نصّ الرسالة) لأهمّ خلل واحد — أو (None, None)."""
    if d.get("error") and "لم يربط" in str(d["error"]):
        return None, None

    if not d.get("key_valid"):
        return ("key_invalid",
                "🔑 تنبيه من وِيل إكس\n\n"
                "مفتاح حسابك لا يعمل، فالتداول متوقّف.\n\n"
                "والسبب غالباً أن عنوان خادمنا غير مسموح في مفتاحك.\n\n"
                "الحلّ:\n"
                "١. ادخل حسابك في المنصّة ثم صفحة إدارة مفاتيح واجهة البرمجة\n"
                "٢. عدّل المفتاح الذي ربطته معنا\n"
                "٣. فعّل تقييد الوصول بعناوين موثوقة\n"
                "٤. أضف هذا العنوان: 178.105.49.200\n"
                "٥. احفظ التعديل\n\n"
                "وسيعود التداول تلقائياً بعد ذلك.")

    if d.get("futures_enabled") is False:
        return ("futures_off",
                "🔑 تنبيه من وِيل إكس\n\n"
                "حسابك مربوط بنجاح، لكنّ التداول لا يعمل.\n\n"
                "والسبب أن صلاحية العقود الآجلة غير مفعّلة في مفتاحك.\n\n"
                "الحلّ:\n"
                "١. ادخل صفحة إدارة مفاتيح واجهة البرمجة في منصّتك\n"
                "٢. اضغط تعديل على المفتاح المربوط معنا\n"
                "٣. فعّل خيار العقود الآجلة\n"
                "٤. احفظ التعديل\n\n"
                "ملاحظة: بعض المنصّات تطلب فتح حساب العقود الآجلة أوّلاً "
                "قبل أن يظهر هذا الخيار.")

    if d.get("ip_restricted") is False:
        return ("no_ip",
                "🛡️ تنبيه أمان من وِيل إكس\n\n"
                "مفتاحك يعمل، لكنّه مفتوح لأي عنوان — وهذا خطر عليك.\n\n"
                "الحلّ:\n"
                "١. ادخل صفحة إدارة مفاتيح واجهة البرمجة\n"
                "٢. عدّل مفتاحك\n"
                "٣. فعّل تقييد الوصول بعناوين موثوقة\n"
                "٤. أضف هذا العنوان وحده: 178.105.49.200\n\n"
                "فيصير مفتاحك محميّاً ولا يعمل إلا من خادمنا.")

    if d.get("withdraw_enabled"):
        return ("withdraw_on",
                "⚠️ تحذير أمنيّ من وِيل إكس\n\n"
                "مفتاحك يحمل صلاحية السحب — ونحن لا نحتاجها إطلاقاً.\n\n"
                "ونوصيك بإلغائها فوراً حمايةً لأموالك:\n"
                "١. ادخل صفحة إدارة مفاتيح واجهة البرمجة\n"
                "٢. عدّل مفتاحك\n"
                "٣. ألغِ خيار السحب\n"
                "٤. احفظ التعديل")

    bal = d.get("futures_balance")
    if bal is not None and bal < 10:
        return ("low_balance",
                "💰 تنبيه من وِيل إكس\n\n"
                "مفتاحك سليم والصلاحيات مفعّلة، لكنّ محفظة العقود الآجلة "
                "لديك شبه فارغة.\n\n"
                f"الرصيد الحاليّ: {bal:.2f} دولار\n\n"
                "الحلّ: حوّل مبلغاً من محفظتك الفورية إلى محفظة العقود الآجلة "
                "من داخل منصّتك.\n\n"
                "ونوصي بعشرين دولاراً فأكثر ليعمل النظام بمرونة.")

    # 🔌 صفقات فاتته لأن عملتها على منصّة لم يربطها
    miss = d.get("missed_exchanges") or {}
    if miss:
        top = sorted(miss.items(), key=lambda x: -x[1])[:3]
        names = {"bybit": "بايبت", "okx": "أوكي إكس", "bitget": "بيتجت",
                 "gate": "جيت", "mexc": "إم إكس سي", "bingx": "بينج إكس"}
        lines = "\n".join("   • " + names.get(k, k) + f": {v} صفقة" for k, v in top)
        return ("missed_ex",
                "🔌 فرص فاتتك من وِيل إكس\n\n"
                "بعض إشاراتنا على منصّات لم تربط مفاتيحها معنا، "
                "فلم نستطع تنفيذها في حسابك.\n\n"
                "وما فاتك خلال اليومين الماضيين:\n" + lines + "\n\n"
                "الحلّ: افتح صفحة التداول الآليّ في التطبيق واربط مفتاح "
                "المنصّة التي تريد، ثم سيبدأ التنفيذ عليها تلقائياً.\n\n"
                "وصفحة دليل الاستخدام تشرح خطوات كل منصّة بالتفصيل.")

    if not d.get("auto_trade_on"):
        return ("auto_off",
                "⚙️ تنبيه من وِيل إكس\n\n"
                "كل شيء في حسابك سليم، لكنّ التداول الآليّ مُطفأ من إعداداتك "
                "عندنا.\n\n"
                "الحلّ: افتح صفحة التداول الآليّ في التطبيق وفعّل المفتاح.\n\n"
                "وبعدها ستبدأ الصفقات بالفتح تلقائياً.")

    return None, None


def check_all() -> dict:
    """يفحص كل من ربط مفتاحه، ويُرسل لمن يحتاج."""
    import os
    if os.path.exists(OFF_FLAG):
        return {"skipped": True}
    _init()
    from services.binance_diag import diagnose
    out = {"checked": 0, "sent": 0, "ok": 0, "cooldown": 0}
    try:
        c = sqlite3.connect(DB)
        ids = [r[0] for r in c.execute(
            "SELECT user_id FROM user_binance_credentials")]
        c.close()
    except Exception as e:
        log.error("قائمة المشتركين: %s", e)
        return out

    for uid in ids:
        try:
            d = diagnose(uid)
            out["checked"] += 1
            # نُحصي ما فاته بسبب منصّة غير مربوطة
            try:
                c2 = sqlite3.connect(DB)
                have = {r[0] or "binance" for r in c2.execute(
                    "SELECT exchange FROM user_binance_credentials WHERE user_id=?",
                    (uid,))}
                rows2 = c2.execute(
                    "SELECT signal_symbol FROM auto_trade_logs WHERE user_id=? "
                    "AND executed=0 AND error_message LIKE '%no_credentials%' "
                    "AND created_at > datetime('now','-2 days')", (uid,)).fetchall()
                c2.close()
                if rows2:
                    u2 = sqlite3.connect("/opt/whalex/multi_universe.db")
                    cnt = {}
                    for (sym,) in rows2:
                        e = u2.execute("SELECT exchange FROM universe WHERE symbol=?",
                                       (sym,)).fetchone()
                        if e and e[0] and e[0] not in have:
                            cnt[e[0]] = cnt.get(e[0], 0) + 1
                    u2.close()
                    d["missed_exchanges"] = cnt
            except Exception:
                pass
            key, text = message_for(d)
            if not key:
                out["ok"] += 1
                continue
            if _recent(uid, key):
                out["cooldown"] += 1
                continue
            if _send(uid, text):
                _remember(uid, key)
                out["sent"] += 1
        except Exception as e:
            log.debug("فحص %s: %s", uid[:8], e)
    log.info("🔔 حارس الربط: فُحص %d · أُرسل %d · سليم %d · تبريد %d",
             out["checked"], out["sent"], out["ok"], out["cooldown"])
    return out


async def watcher_loop():
    """حلقة دورية — كل ستّ ساعات."""
    import asyncio
    await asyncio.sleep(120)
    while True:
        try:
            check_all()
        except Exception as e:
            log.error("حلقة الحارس: %s", e)
        await asyncio.sleep(CHECK_EVERY)
