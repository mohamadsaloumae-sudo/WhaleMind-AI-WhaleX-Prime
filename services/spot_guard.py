"""🛡️ حارس السبوت — يبيع المراكز اليتيمة والخاسرة.

مقيس 15 سبتمبر: TUSDT اُغلقت اشارتها بـ-0.91% (sl) بينما
مركز المشترك بقي مفتوحاً ووصل -14.23%. فالنظام يُغلق
الاشارة ولا يصل امر البيع، والرصيد يعلق في صفقات ميّتة.

القواعد:
  ① لا اشارة نشطة لهذه العملة  → بيع
  ② خسارة تتجاوز HARD_SL       → بيع
  ③ وقف متحرّك: ربح ≥ ARM ثم تراجع GIVE → بيع
الاطفاء: touch /opt/whalex/db/spot_guard.off
"""
import asyncio
import json
import logging
import os
import sqlite3
import time
import urllib.request

log = logging.getLogger("spot_guard")
DB = "/opt/whalex/db/whalex.db"
OFF = "/opt/whalex/db/spot_guard.off"
EVERY = 60
HARD_SL = -3.0
ARM = 1.5
GIVE = 0.7
_PEAK = {}


def _px(sym):
    try:
        u = "https://api.binance.com/api/v3/ticker/price?symbol=" + sym
        with urllib.request.urlopen(u, timeout=6) as r:
            return float(json.load(r).get("price") or 0)
    except Exception:
        return 0.0


def _active(sym):
    try:
        c = sqlite3.connect(DB)
        n = c.execute(
            "SELECT COUNT(*) FROM signals WHERE radar_type='spot' "
            "AND is_active=1 AND symbol=?", (sym,)).fetchone()[0]
        c.close()
        return int(n or 0) > 0
    except Exception:
        return True


def sweep():
    if os.path.exists(OFF):
        return 0
    try:
        c = sqlite3.connect(DB)
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT DISTINCT symbol, exchange, entry FROM spot_positions_multi "
            "WHERE status='open' AND entry>0")]
        c.close()
    except Exception as e:
        log.error("sweep: %s", e)
        return 0
    n = 0
    for r in rows:
        sym = r["symbol"]
        px = _px(sym)
        if px <= 0:
            continue
        pnl = (px - float(r["entry"])) / float(r["entry"]) * 100.0
        pk = _PEAK.get(sym, pnl)
        if pnl > pk:
            pk = pnl
            _PEAK[sym] = pk
        why = ""
        if not _active(sym):
            why = "يتيمة — لا اشارة نشطة"
        elif pnl <= HARD_SL:
            why = "وقف صلب %.2f%%" % pnl
        elif pk >= ARM and pnl <= pk - GIVE:
            why = "وقف متحرّك · ذروة %.2f%% الآن %.2f%%" % (pk, pnl)
        if not why:
            continue
        try:
            from services.spot_exec import sell_all
            res = sell_all(r["exchange"] or "binance", sym, px)
            ok = sum(1 for x in res if x.get("ok"))
            _PEAK.pop(sym, None)
            n += ok
            log.info("🛡️🪙 %s بيع %d مركز — %s (%.2f%%)", sym, ok, why, pnl)
        except Exception as e:
            log.error("🛡️🪙 %s: %s", sym, e)
    return n


async def guard_loop():
    await asyncio.sleep(90)
    while True:
        try:
            await asyncio.to_thread(orphan_no_keys)
            await asyncio.to_thread(sweep)
        except Exception as e:
            log.error("loop: %s", e)
        await asyncio.sleep(EVERY)


def orphan_no_keys():
    """من حذف مفاتيحه: نُغلق صفقاته في سجلّنا ولا نلاحقها.

    هو يبيع بنفسه على منصّته. ونحن نبقى معلّقين بمحاولات فاشلة
    كل دقيقة، فنُغلقها بسبب واضح ويبقى السجلّ لو عاد.
    """
    n = 0
    try:
        c = sqlite3.connect(DB)
        rows = c.execute(
            "SELECT DISTINCT user_id FROM spot_positions_multi "
            "WHERE status='open'").fetchall()
        for (uid,) in rows:
            has = c.execute(
                "SELECT COUNT(*) FROM user_binance_credentials "
                "WHERE user_id=?", (uid,)).fetchone()[0]
            if int(has or 0) > 0:
                continue
            cur = c.execute(
                "UPDATE spot_positions_multi SET status='closed', "
                "closed_ts=?, exit_price=entry, pnl_pct=0 "
                "WHERE user_id=? AND status='open'",
                (int(time.time()), uid))
            n += cur.rowcount
            log.info("🔑 %s حذف مفاتيحه — اُغلقت %d صفقة في السجلّ",
                     uid[:8], cur.rowcount)
        c.commit()
        c.close()
    except Exception as e:
        log.error("orphan_no_keys: %s", e)
    return n
