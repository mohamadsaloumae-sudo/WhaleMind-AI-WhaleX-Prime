"""🛡️ حارس الصفقات المستحيلة — يُصحّح من المنصّة أو يحذف.

مقيس 14 سبتمبر: LSKUSDT سُجّلت -64.86% والمشترك ربح +2.09%.
السبب: سعر الاشارة 0.4663 والتنفيذ 0.4057 (انزلاق 13%)، والمركز
حسب من سعر الاشارة. ونفس العطل تكرّر مرتين في يومين.

القاعدة: اقصى خسارة ممكنة = (الوقف ÷ الدخول) × الرافعة.
وما تجاوزها مستحيل فيزيائيا — فالبيانات فاسدة لا النتيجة.

والمعالجة:
  · نُفّذت عند مشترك ⇒ نُصحّح بالرقم الحقيقي من المنصّة
  · لم تُنفّذ عند احد ⇒ نحذفها (لا نعلّم النموذج من كذب)

يعمل تلقائيا عند كل اغلاق، ودوريا كل 10 دقائق للفائت.
الاطفاء: touch /opt/whalex/db/audit.off
"""
import os
import time
import sqlite3
import logging

log = logging.getLogger("signal_audit")
ML = "/opt/whalex/ml_training.db"
DB = "/opt/whalex/db/whalex.db"
OFF = "/opt/whalex/db/audit.off"

# هامش 50% فوق الحد النظري — مقيس 14 سبتمبر على 6345 صفقة:
# بهامش 1.15 يلتقط 53 صفقة اغلبها انزلاق عادي (BITLIGHT -11.95%
# والحد 11.5%). وبهامش 1.5 لا يلتقط الا الفساد الحقيقي مثل
# LSKUSDT -64.86% بحد 40% (الضعف ونصف).
SLACK = 1.5


def _impossible(d) -> tuple:
    """هل الخسارة مستحيلة؟ (نعم/لا، الحدّ)"""
    try:
        e = float(d.get("entry") or 0)
        sl = float(d.get("sl") or 0)
        lv = float(d.get("leverage") or 5) or 5.0
        p = float(d.get("pnl_pct") or 0)
        if e <= 0 or sl <= 0 or p >= 0:
            return False, 0.0
        cap = abs(sl - e) / e * 100 * lv * SLACK
        return abs(p) > cap, cap
    except Exception:
        return False, 0.0


def _real_result(d) -> dict:
    """النتيجة الحقيقية من user_trades — أو لا شيء."""
    try:
        t0 = int(d.get("timestamp") or 0)
        t1 = int(d.get("closed_at") or 0) or (t0 + 3600)
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT pnl_pct, net_usdt, real_net, exit_price FROM user_trades "
            "WHERE symbol=? AND opened_at BETWEEN ? AND ? "
            "AND closed_at IS NOT NULL",
            (d["symbol"], t0 - 180, t1 + 300))]
        c.close()
        if not rows:
            return {}
        # متوسّط ما تحقّق فعلا عند المشتركين
        pcts = [float(r["pnl_pct"] or 0) for r in rows]
        xs = [float(r["exit_price"] or 0) for r in rows if r["exit_price"]]
        return {"n": len(rows),
                "pnl_pct": round(sum(pcts) / len(pcts), 3),
                "exit_price": round(sum(xs) / len(xs), 8) if xs else None}
    except Exception as e:
        log.debug("real_result: %s", e)
        return {}


def audit(row_id: int) -> dict:
    """يفحص صفقة واحدة ويُصحّح أو يحذف."""
    if os.path.exists(OFF):
        return {"skipped": True}
    try:
        c = sqlite3.connect("file:%s?mode=ro" % ML, uri=True)
        c.row_factory = sqlite3.Row
        r = c.execute("SELECT * FROM training_signals WHERE id=?",
                      (row_id,)).fetchone()
        c.close()
        if not r:
            return {"ok": False}
        d = dict(r)
        bad, cap = _impossible(d)
        if not bad:
            return {"ok": True, "action": "سليمة"}

        real = _real_result(d)
        w = sqlite3.connect(ML, timeout=10)
        if real.get("n"):
            w.execute("UPDATE training_signals SET pnl_pct=?, exit_price=?, "
                      "outcome=?, close_reason=? WHERE id=?",
                      (real["pnl_pct"],
                       real.get("exit_price") or d.get("exit_price"),
                       1 if real["pnl_pct"] > 0 else 0,
                       "corrected_from_exchange", row_id))
            w.commit(); w.close()
            log.warning("🛡️ %s صُحّحت: %.2f%% ← %.2f%% (حدّ %.1f%% · %d مشترك)",
                        d["symbol"], d["pnl_pct"], real["pnl_pct"], cap, real["n"])
            return {"ok": True, "action": "صُحّحت",
                    "from": d["pnl_pct"], "to": real["pnl_pct"]}
        w.execute("DELETE FROM training_signals WHERE id=?", (row_id,))
        w.commit(); w.close()
        try:
            u = sqlite3.connect(DB, timeout=10)
            u.execute("DELETE FROM signals WHERE symbol=? AND pnl_pct=?",
                      (d["symbol"], d["pnl_pct"]))
            u.commit(); u.close()
        except Exception:
            pass
        log.warning("🛡️ %s حُذفت: %.2f%% مستحيلة (حدّ %.1f%%) ولم تُنفّذ",
                    d["symbol"], d["pnl_pct"], cap)
        return {"ok": True, "action": "حُذفت", "pnl": d["pnl_pct"]}
    except Exception as e:
        log.debug("audit %s: %s", row_id, e)
        return {"ok": False, "error": str(e)[:60]}


def sweep(hours: int = 24) -> dict:
    """يمسح الفائت."""
    if os.path.exists(OFF):
        return {"skipped": True}
    out = {"checked": 0, "fixed": 0, "deleted": 0}
    try:
        c = sqlite3.connect("file:%s?mode=ro" % ML, uri=True)
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM training_signals WHERE pnl_pct IS NOT NULL "
            "AND closed_at >= ? AND close_reason != 'corrected_from_exchange'",
            (int(time.time()) - hours * 3600,))]
        c.close()
    except Exception as e:
        return {"error": str(e)[:60]}
    for d in rows:
        bad, _ = _impossible(d)
        if not bad:
            continue
        out["checked"] += 1
        a = audit(d["id"]).get("action")
        if a == "صُحّحت":
            out["fixed"] += 1
        elif a == "حُذفت":
            out["deleted"] += 1
    return out
