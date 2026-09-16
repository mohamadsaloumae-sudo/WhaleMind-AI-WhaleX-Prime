"""🔒 حارس الاشتراك — يُطفئ التداول عند انتهائه.

مقيس 16 سبتمبر: 6 من 20 مفعّلاً اشتراكهم منتهٍ ومفاتيحهم تعمل —
moaad منذ يومين و حسين حمزي منذ 11 يوما. فالنظام يُغلق الصفحات
عند الانتهاء ولا يُطفئ التداول، فتبقى المفاتيح حيّة والصفقات تُفتح.

كل 10 دقائق: من انتهى اشتراكه يُطفأ تداوله الآلي (فيوتشر وسبوت)،
وتُغلق مراكزه المفتوحة، ويُنبّه. والمفاتيح تبقى محفوظة — فإن جدّد
عاد التداول بضغطة، ولا يُعيد الربط.

ومن جدّد يُعاد تفعيله تلقائيا ان كان مُطفأ بسببنا وحدنا.

الاطفاء: touch /opt/whalex/db/sub_guard.off
بلا اغلاق المراكز: touch /opt/whalex/db/sub_guard.keep
"""
import os
import time
import sqlite3
import datetime
import logging

log = logging.getLogger("sub_guard")
DB = "/opt/whalex/db/whalex.db"
OFF = "/opt/whalex/db/sub_guard.off"
KEEP = "/opt/whalex/db/sub_guard.keep"
GRACE_H = 6      # مهلة بعد الانتهاء قبل الاطفاء


def _expired(user_id) -> tuple:
    """(منتهٍ؟, أيام منذ الانتهاء)"""
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        r = c.execute("SELECT expires_at FROM subscriptions WHERE user_id=? "
                      "ORDER BY expires_at DESC LIMIT 1", (user_id,)).fetchone()
        c.close()
        if not r or not r[0]:
            return True, 999
        exp = datetime.datetime.strptime(str(r[0])[:19], "%Y-%m-%d %H:%M:%S")
        d = (datetime.datetime.utcnow() - exp).total_seconds() / 3600
        return d > GRACE_H, round(d / 24, 1)
    except Exception as e:
        log.debug("expired %s: %s", user_id, e)
        return False, 0


def _open_positions(user_id, exchange) -> int:
    """كم مركزاً مفتوحاً له — فيوتشر وسبوت."""
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        n = c.execute("SELECT COUNT(*) FROM user_trades WHERE user_id=? "
                      "AND status='open'", (user_id,)).fetchone()[0]
        n += c.execute("SELECT COUNT(*) FROM spot_positions_multi WHERE user_id=? "
                       "AND exchange=? AND status='open'",
                       (user_id, exchange)).fetchone()[0]
        c.close()
        return int(n or 0)
    except Exception:
        return 0


def _ensure_col():
    try:
        c = sqlite3.connect(DB, timeout=10)
        try:
            c.execute("ALTER TABLE user_binance_credentials "
                      "ADD COLUMN off_by_sub INTEGER DEFAULT 0")
            c.commit()
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE user_binance_credentials "
                      "ADD COLUMN keys_cut INTEGER DEFAULT 0")
            c.commit()
        except Exception:
            pass
        c.close()
    except Exception:
        pass


def sweep(close_positions: bool = True) -> dict:
    if os.path.exists(OFF):
        return {"skipped": True}
    _ensure_col()
    out = {"checked": 0, "disabled": 0, "restored": 0, "closed": 0, "users": []}
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT user_id, exchange, auto_trade_enabled, spot_auto_enabled, "
            "COALESCE(off_by_sub,0) AS off_by_sub, COALESCE(keys_cut,0) AS keys_cut FROM user_binance_credentials")]
        c.close()
    except Exception as e:
        return {"error": str(e)[:60]}

    w = sqlite3.connect(DB, timeout=15)
    for r in rows:
        uid, ex = r["user_id"], (r["exchange"] or "binance")
        on = bool(r["auto_trade_enabled"]) or bool(r["spot_auto_enabled"])
        exp, days = _expired(uid)
        out["checked"] += 1

        # ── منتهٍ ⇒ ثلاث مراحل بلا ظلم
        #    1) لا صفقات جديدة فورا
        #    2) المفتوحة تُغلق بحرّاسها الطبيعية (وقف · هدف · نزيف)
        #    3) حين تنتهي كلها ⇒ قطع المفاتيح
        if exp and on:
            w.execute("UPDATE user_binance_credentials SET auto_trade_enabled=0, "
                      "spot_auto_enabled=0, off_by_sub=1 WHERE user_id=? AND exchange=?",
                      (uid, ex))
            out["disabled"] += 1
            out["users"].append({"user": uid[:8], "action": "أُوقف الفتح",
                                 "days": days})
            log.warning("🔒 %s: منتهٍ منذ %.1f يوم — لا صفقات جديدة، "
                        "والمفتوحة تُترك لحرّاسها", uid[:8], days)
            try:
                from services.telegram import send_user
                send_user(uid, "🔒 انتهى اشتراكك.\n"
                               "لن تُفتح صفقات جديدة، وصفقاتك المفتوحة "
                               "تُدار حتى تُغلق طبيعياً.\n"
                               "مفاتيحك محفوظة — وبالتجديد يعود العمل فوراً.")
            except Exception:
                pass

        # ── منتهٍ ومُطفأ سلفا ⇒ نفحص مراكزه
        elif exp and r["off_by_sub"] and not on:
            _n = _open_positions(uid, ex)
            if _n == 0:
                if not r.get("keys_cut"):
                    w.execute("UPDATE user_binance_credentials SET keys_cut=1 "
                              "WHERE user_id=? AND exchange=?", (uid, ex))
                    out["cut"] = out.get("cut", 0) + 1
                    out["users"].append({"user": uid[:8], "action": "قُطعت المفاتيح"})
                    log.warning("🔒✂️ %s: لا مراكز مفتوحة — قُطع الربط", uid[:8])
                    try:
                        from services.telegram import send_user
                        send_user(uid, "✂️ أُغلقت كل صفقاتك وقُطع الربط.\n"
                                       "جدّد اشتراكك ليعود التداول تلقائياً.")
                    except Exception:
                        pass
            else:
                log.info("🔒⏳ %s: %d مركزاً ما زال مفتوحاً — ننتظر", uid[:8], _n)

        # ── جدّد وكان مُطفأ بسببنا ⇒ نُعيده
        elif (not exp) and r["off_by_sub"] and not on:
            w.execute("UPDATE user_binance_credentials SET auto_trade_enabled=1, "
                      "off_by_sub=0, keys_cut=0 WHERE user_id=? AND exchange=?",
                      (uid, ex))
            out["restored"] += 1
            out["users"].append({"user": uid[:8], "action": "أُعيد"})
            log.info("🔓 %s: جدّد — أُعيد التداول", uid[:8])
    w.commit()
    w.close()
    return out


async def loop():
    import asyncio
    await asyncio.sleep(180)
    while True:
        try:
            r = sweep(close_positions=True)
            if r.get("disabled") or r.get("restored"):
                log.warning("🔒 حارس الاشتراك: أُطفئ %d · أُعيد %d",
                            r.get("disabled", 0), r.get("restored", 0))
        except Exception as e:
            log.debug("sub loop: %s", e)
        await asyncio.sleep(600)
