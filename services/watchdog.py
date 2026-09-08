"""🕵️ المراقب — يفحص كل ما يمسّ أموال المشتركين ويُنذر الأدمن.

المشكلة المقيسة: 8 سبتمبر — رافعة APEUSDT ضُبطت 5x وبقيت 20x على
باينانس، فعُرضت للمشترك +12.36% وهي عنده +42.84%. لم نكتشفه إلا
بصورة من المشترك. ولولاها لبقي العطل شهوراً.

يفحص عشرة أبواب، كلّها قراءة فقط:
  1 الرافعة المسجَّلة ≠ الفعلية على باينانس
  2 مركز مفتوح على باينانس بلا سجلّ عندنا
  3 سجلّ مفتوح عندنا والمركز مغلق على باينانس
  4 سعر الدخول المسجَّل ≠ الفعليّ
  5 الكمية المسجَّلة ≠ الفعلية
  6 صفقة عالقة مفتوحة أطول من الحدّ
  7 قفزة مفاجئة في سبب فشل واحد
  8 لا مشترك مؤهَّل إطلاقاً
  9 الرادارات صامتة بلا إشارات
 10 أرقام مستحيلة في الإحصاء

ثلاثة ضمانات:
  • قراءة فقط — لا يكتب أمراً ولا يغيّر صفقة
  • أي خطأ في بابٍ يتخطّاه ولا يُسقط الباقي
  • لا تكرار — التحذير نفسه لا يُعاد قبل SILENCE_SEC

الإطفاء: touch /opt/whalex/db/watchdog.off
"""
import logging
import os
import sqlite3
import time

log = logging.getLogger("watchdog")

DB = "/opt/whalex/db/whalex.db"
OFF_FLAG = "/opt/whalex/db/watchdog.off"
INTERVAL_SEC = 1800          # كل نصف ساعة — يخفّف ضغط API
SILENCE_SEC = 3 * 3600       # لا نكرّر التحذير نفسه قبل ثلاث ساعات

LEV_TOL = 0            # الرافعة يجب أن تطابق تماماً
PX_TOL_PCT = 1.0       # فرق سعر الدخول المقبول
QTY_TOL_PCT = 1.0      # فرق الكمية المقبول
STUCK_HOURS = 48       # صفقة مفتوحة أطول من هذا = عالقة
FAIL_SPIKE = 40        # سبب فشل واحد تكرّر أكثر من هذا في ساعة
QUIET_HOURS = 3        # لا إشارات منذ هذه المدّة = صمت مريب

_last_sent = {}        # {مفتاح التحذير: طابع زمنيّ}


def _fresh(key: str) -> bool:
    """هل مرّ وقت كافٍ لإعادة إرسال هذا التحذير؟"""
    t = _last_sent.get(key, 0)
    if time.time() - t < SILENCE_SEC:
        return False
    _last_sent[key] = time.time()
    return True


def _ro(path=DB):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


# ═══════════════════════════════════════════════════════════
# الأبواب العشرة — كلّ باب يُعيد قائمة تحذيرات
# ═══════════════════════════════════════════════════════════

def _check_positions(uid, name, trades, live):
    """يقارن سجلّنا بمراكز باينانس الفعلية."""
    out = []
    live_by_sym = {p["symbol"]: p for p in live}

    for t in trades:
        sym = t["symbol"]
        p = live_by_sym.get(sym)
        if not p:
            out.append(("orphan_local", "عالٍ",
                        f"{name} · {sym}: مفتوحة عندنا ومغلقة على باينانس"))
            continue
        # الرافعة
        try:
            lv_db = int(float(t["leverage"] or 0))
            lv_ex = int(float(p.get("leverage") or 0))
            if lv_db and lv_ex and abs(lv_db - lv_ex) > LEV_TOL:
                out.append(("lev", "حرج",
                            f"{name} · {sym}: الرافعة عندنا {lv_db}x وعلى "
                            f"باينانس {lv_ex}x — النسبة المعروضة خاطئة"))
        except Exception:
            pass
        # سعر الدخول
        try:
            e_db = float(t["entry"] or 0)
            e_ex = float(p.get("entryPrice") or 0)
            if e_db > 0 and e_ex > 0:
                d = abs(e_db - e_ex) / e_ex * 100
                if d > PX_TOL_PCT:
                    out.append(("px", "عالٍ",
                                f"{name} · {sym}: دخول عندنا {e_db:.8g} "
                                f"وعلى باينانس {e_ex:.8g} (فرق {d:.2f}%)"))
        except Exception:
            pass
        # الكمية
        try:
            q_db = abs(float(t["qty"] or 0))
            q_ex = abs(float(p.get("positionAmt") or 0))
            if q_db > 0 and q_ex > 0:
                d = abs(q_db - q_ex) / q_ex * 100
                if d > QTY_TOL_PCT:
                    out.append(("qty", "عالٍ",
                                f"{name} · {sym}: كمية عندنا {q_db:g} "
                                f"وعلى باينانس {q_ex:g} (فرق {d:.1f}%)"))
        except Exception:
            pass

    db_syms = {t["symbol"] for t in trades}
    for sym, p in live_by_sym.items():
        if sym not in db_syms:
            out.append(("orphan_remote", "حرج",
                        f"{name} · {sym}: مفتوحة على باينانس بلا سجلّ "
                        f"عندنا — لا يديرها أحد"))
    return out


def check_users():
    """الأبواب 1-5: مطابقة كل مشترك مفعَّل مع باينانس."""
    alerts = []
    try:
        from services.binance_trader import get_client, get_open_positions
    except Exception as e:
        log.debug("import trader: %s", e)
        return alerts
    try:
        c = _ro()
        c.row_factory = sqlite3.Row
        users = [r["user_id"] for r in c.execute(
            "SELECT user_id FROM user_binance_credentials "
            "WHERE auto_trade_enabled=1")]
        c.close()
    except Exception as e:
        log.debug("users: %s", e)
        return alerts

    for uid in users:
        try:
            c = _ro()
            c.row_factory = sqlite3.Row
            trades = [dict(r) for r in c.execute(
                "SELECT symbol, direction, entry, qty, leverage FROM user_trades "
                "WHERE user_id=? AND status='open' AND market='futures'", (uid,))]
            nm = c.execute("SELECT username FROM users WHERE id=?",
                           (uid,)).fetchone()
            c.close()
            name = (nm["username"] if nm else uid[:8]) or uid[:8]
        except Exception as e:
            log.debug("trades %s: %s", uid[:8], e)
            continue
        # لا نسأل باينانس عمّن لا صفقة له — توفير طلبات
        if not trades:
            continue
        try:
            live = get_open_positions(uid)
        except Exception as e:
            alerts.append(("api", "عالٍ",
                           f"{name}: تعذّر قراءة مراكزه — {str(e)[:60]}"))
            continue
        alerts.extend(_check_positions(uid, name, trades, live))
    return alerts


def check_stuck():
    """الباب 6: صفقات عالقة مفتوحة أطول من الحدّ."""
    out = []
    try:
        cut = int(time.time()) - STUCK_HOURS * 3600
        c = _ro()
        c.row_factory = sqlite3.Row
        for r in c.execute(
                "SELECT symbol, user_id, opened_at FROM user_trades "
                "WHERE status='open' AND opened_at < ?", (cut,)):
            h = (time.time() - r["opened_at"]) / 3600
            out.append(("stuck", "متوسّط",
                        f"{r['user_id'][:8]} · {r['symbol']}: مفتوحة منذ "
                        f"{h:.0f} ساعة بلا إغلاق"))
        c.close()
    except Exception as e:
        log.debug("stuck: %s", e)
    return out


def check_quiet():
    """الباب 9: الرادارات صامتة."""
    out = []
    try:
        c = _ro()
        n = c.execute(
            "SELECT COUNT(*) FROM signals WHERE created_at > "
            "datetime('now', ?)", (f"-{QUIET_HOURS} hours",)).fetchone()[0]
        c.close()
        if n == 0:
            out.append(("quiet", "حرج",
                        f"لا إشارة واحدة منذ {QUIET_HOURS} ساعات — "
                        f"الرادارات قد تكون متوقّفة"))
    except Exception as e:
        log.debug("quiet: %s", e)
    return out


def check_eligibility():
    """الباب 8: لا مشترك مؤهَّل."""
    out = []
    try:
        from services.eligibility import snapshot as _snap
        s = _snap()
        us = s.get("users", {})
        if us:
            ok = sum(1 for v in us.values() if v.get("ok"))
            if ok == 0:
                out.append(("no_eligible", "حرج",
                            f"لا مشترك مؤهَّل إطلاقاً من {len(us)} — "
                            f"تعطُّل عامّ محتمل"))
    except Exception as e:
        log.debug("elig: %s", e)
    return out


def check_failures():
    """الباب 7: قفزة في سبب فشل واحد."""
    out = []
    try:
        # created_at نصّ ISO لا طابع رقميّ — المقارنة بـdatetime لا برقم
        c = _ro()
        c.row_factory = sqlite3.Row
        for r in c.execute(
                "SELECT COALESCE(error_message,'?') e, COUNT(*) n "
                "FROM auto_trade_logs WHERE executed=0 AND "
                "created_at > datetime('now','-1 hour') "
                "GROUP BY e HAVING n > ? ORDER BY n DESC", (FAIL_SPIKE,)):
            out.append(("fail_spike", "عالٍ",
                        f"{r['n']} إخفاق في ساعة بسبب واحد: {r['e'][:70]}"))
        c.close()
    except Exception as e:
        log.debug("fails: %s", e)
    return out


def check_stats():
    """الباب 10: أرقام مستحيلة."""
    out = []
    try:
        c = _ro()
        c.row_factory = sqlite3.Row
        for r in c.execute(
                "SELECT symbol, user_id, pnl_pct, leverage FROM user_trades "
                "WHERE closed_at IS NOT NULL AND "
                "(pnl_pct < -100 OR pnl_pct > 500 OR leverage <= 0 "
                " OR leverage > 125) LIMIT 5"):
            out.append(("bad_num", "متوسّط",
                        f"{r['user_id'][:8]} · {r['symbol']}: رقم مستحيل — "
                        f"ربح {r['pnl_pct']} رافعة {r['leverage']}"))
        c.close()
    except Exception as e:
        log.debug("stats: %s", e)
    return out


# ═══════════════════════════════════════════════════════════

ORDER = {"حرج": 0, "عالٍ": 1, "متوسّط": 2}


def scan_all():
    """يشغّل الأبواب العشرة ويُعيد التحذيرات مرتّبة بالخطورة."""
    alerts = []
    for fn in (check_users, check_stuck, check_quiet,
               check_eligibility, check_failures, check_stats):
        try:
            alerts.extend(fn())
        except Exception as e:
            log.error("باب %s: %s", fn.__name__, e)
    alerts.sort(key=lambda a: ORDER.get(a[1], 9))
    return alerts


def format_report(alerts):
    """يبني نصّ التحذير للأدمن."""
    if not alerts:
        return None
    icon = {"حرج": "🔴", "عالٍ": "🟠", "متوسّط": "🟡"}
    lines = ["🕵️ المراقب — تحذيرات النظام", ""]
    for _k, sev, msg in alerts[:15]:
        lines.append(f"{icon.get(sev, '⚪')} [{sev}] {msg}")
    if len(alerts) > 15:
        lines.append(f"\n… و{len(alerts) - 15} تحذيراً آخر")
    lines.append("\n📋 انسخ هذا وأرسله للفحص.")
    return "\n".join(lines)


async def _send_admin(text):
    """يرسل للأدمن — تيليجرام ورسالة داخل التطبيق."""
    sent = False
    try:
        from services.telegram import send_message
        c = _ro()
        r = c.execute("SELECT telegram_admin_chat_id FROM settings "
                      "LIMIT 1").fetchone()
        c.close()
        if r and r[0]:
            await send_message(str(r[0]), text)
            sent = True
    except Exception as e:
        log.debug("tg: %s", e)
    try:
        c = sqlite3.connect(DB)
        c.row_factory = sqlite3.Row
        admins = [r["id"] for r in c.execute(
            "SELECT id FROM users WHERE tier='admin'")]
        for a in admins:
            c.execute("INSERT INTO user_messages(user_id,message,created_at,seen)"
                      " VALUES(?,?,?,0)", (a, text, int(time.time())))
        c.commit()
        c.close()
        if admins:
            sent = True
    except Exception as e:
        log.debug("msg: %s", e)
    return sent


async def run_once():
    """فحص واحد — يُستدعى من الحلقة أو يدوياً."""
    alerts = [a for a in scan_all() if _fresh(f"{a[0]}|{a[2][:60]}")]
    if not alerts:
        log.info("🕵️ المراقب: لا تحذيرات جديدة")
        return 0
    txt = format_report(alerts)
    log.warning("🕵️ المراقب: %d تحذير\n%s", len(alerts), txt)
    await _send_admin(txt)
    return len(alerts)


async def watchdog_loop():
    import asyncio
    log.info("🕵️ المراقب بدأ — فحص كل %d دقيقة", INTERVAL_SEC // 60)
    await asyncio.sleep(120)
    while True:
        try:
            if not os.path.exists(OFF_FLAG):
                await run_once()
        except Exception as e:
            log.error("حلقة المراقب: %s", e)
        await asyncio.sleep(INTERVAL_SEC)

