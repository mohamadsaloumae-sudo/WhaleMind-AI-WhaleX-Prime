"""🔄 إعادة ضبط جماعية — المشترك لا يعيد الضبط يدويا عند تحديث الحاسبة.

مقيس 14 سبتمبر: moaad على 25$ × 11 (الاستراتيجية القديمة) بينما
الحاسبة الجديدة تعطي 29.9$ × 8. والمشترك لا يعرف ان عليه اعادة الضبط.

القواعد (كلها معا):
  · التداول الآلي مفعّل لهذا السوق
  · نسخة خطته اقدم من PLAN_VERSION
  · لا مراكز مفتوحة (لا نغيّر تحت صفقة جارية)
  · راس ماله المحدد او رصيده يكفي الحد الادنى
  · الاعدادات ليست مطابقة سلفا

ومن حدد راس مال يُحسب منه لا من رصيده — فلا نمس ما زاد عنه.
الاطفاء: touch /opt/whalex/db/plan_sync.off
"""
import os
import time
import sqlite3
import logging

log = logging.getLogger("plan_sync")
DB = "/opt/whalex/db/whalex.db"
OFF = "/opt/whalex/db/plan_sync.off"

# ⬆️ ارفع هذا الرقم عند كل تعديل على الحاسبة — يُعاد ضبط الجميع
PLAN_VERSION = 2


def _ensure_col():
    try:
        c = sqlite3.connect(DB, timeout=10)
        try:
            c.execute("ALTER TABLE user_binance_credentials "
                      "ADD COLUMN plan_version INTEGER DEFAULT 0")
            c.commit()
        except Exception:
            pass
        c.close()
    except Exception as e:
        log.debug("ensure_col: %s", e)


def _open_count(user_id, market):
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        if market == "spot":
            n = c.execute("SELECT COUNT(*) FROM spot_positions_multi "
                          "WHERE user_id=? AND status='open'", (user_id,)).fetchone()[0]
        else:
            n = c.execute("SELECT COUNT(*) FROM user_trades WHERE user_id=? "
                          "AND market='futures' AND status='open'", (user_id,)).fetchone()[0]
        c.close()
        return int(n or 0)
    except Exception:
        return 0


def sync_all(dry=False) -> dict:
    """يُعيد ضبط من يحتاج. dry=True يحسب ولا يكتب."""
    if os.path.exists(OFF):
        return {"skipped": "مُطفأ"}
    _ensure_col()
    from routers.capital import compute
    from services.binance_trader import usdt_futures_balance

    out = {"checked": 0, "updated": 0, "skipped": [], "changes": []}
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM user_binance_credentials")]
        c.close()
    except Exception as e:
        log.error("sync_all read: %s", e)
        return {"error": str(e)[:80]}

    w = sqlite3.connect(DB, timeout=15) if not dry else None
    for r in rows:
        uid = r["user_id"]
        ex = (r.get("exchange") or "binance").lower()
        ver = int(r.get("plan_version") or 0)
        for market in ("futures", "spot"):
            on = r.get("auto_trade_enabled") if market == "futures" \
                else r.get("spot_auto_enabled")
            if not on:
                continue
            out["checked"] += 1
            if ver >= PLAN_VERSION:
                continue
            if _open_count(uid, market) > 0:
                out["skipped"].append((uid[:8], market, "مراكز مفتوحة"))
                continue
            cap = float(r.get("trading_capital") or 0)
            if cap <= 0:
                cap, _ = usdt_futures_balance(uid)
            if cap <= 0:
                out["skipped"].append((uid[:8], market, "بلا رصيد"))
                continue
            plan = compute(cap, market)
            if not plan.get("ok"):
                out["skipped"].append((uid[:8], market, "دون الحدّ"))
                continue
            cur_a = float(r.get("trade_amount_usdt" if market == "futures"
                                else "spot_trade_amount") or 0)
            cur_s = int(r.get("max_open_positions" if market == "futures"
                              else "spot_max_positions") or 0)
            if abs(cur_a - plan["amount"]) < 0.5 and cur_s == plan["slots"]:
                continue
            out["changes"].append({
                "user": uid[:8], "exchange": ex, "market": market,
                "from": "%.1f$ x%d" % (cur_a, cur_s),
                "to": "%.1f$ x%d" % (plan["amount"], plan["slots"]),
                "capital": round(cap, 2),
            })
            if not dry and w:
                try:
                    if market == "futures":
                        w.execute(
                            "UPDATE user_binance_credentials SET trade_amount_usdt=?,"
                            " max_open_positions=?, plan_version=? "
                            "WHERE user_id=? AND exchange=?",
                            (plan["amount"], plan["slots"], PLAN_VERSION, uid, ex))
                    else:
                        w.execute(
                            "UPDATE user_binance_credentials SET spot_trade_amount=?,"
                            " spot_max_positions=?, plan_version=? "
                            "WHERE user_id=? AND exchange=?",
                            (plan["amount"], plan["slots"], PLAN_VERSION, uid, ex))
                    out["updated"] += 1
                except Exception as e:
                    log.warning("sync %s %s: %s", uid[:8], market, str(e)[:60])
    if w:
        w.commit()
        w.close()
    if out["updated"]:
        log.info("🔄 أُعيد ضبط %d حساب على خطّة v%d", out["updated"], PLAN_VERSION)
    return out
