"""🛡️ حارس الصفقات اليتيمة — لا مركز بلا حماية.

المشكلة المقيسة: دالة الإغلاق كانت تستدعي _client غير الموجودة، فكل
إغلاق حقيقيّ يفشل صامتاً — 36 إغلاقاً ورقياً وصفر على البورصة. فبقيت
عشر صفقات مفتوحة على حسابين بلا أمر وقف واحد، أي مال مكشوف تماماً.

فالحارس يُقارن كل خمس دقائق مراكز كل مشترك على المنصّة بالصفقات التي
يُديرها النظام. وما لا حارس له يُغلق فوراً ويُسجَّل.

وهذه شبكة أمان أخيرة — لا بديل عن إغلاق المدير، بل حماية إن فشل.
"""
import asyncio
import json
import logging
import os
import sqlite3

log = logging.getLogger("orphan_guard")

DB = "/opt/whalex/db/whalex.db"
POS_DB = "/opt/whalex/positions.db"
CHECK_EVERY = 300
GRACE_SEC = 180          # نُمهل الصفقة الجديدة ثلاث دقائق
OFF_FLAG = "/opt/whalex/db/orphan_guard.off"


def _paper_symbols() -> set:
    try:
        c = sqlite3.connect(POS_DB)
        out = set()
        for (d,) in c.execute("SELECT data FROM active_positions "
                              "WHERE status!='closed'"):
            try:
                out.add(json.loads(d)["symbol"])
            except Exception:
                pass
        c.close()
        return out
    except Exception as e:
        log.error("قراءة الورقيّ: %s", e)
        return None


async def sweep() -> dict:
    if os.path.exists(OFF_FLAG):
        return {"skipped": True}
    from services.binance_trader import (decrypt, close_position_for_user)
    from binance.client import Client
    import time as _t

    paper = _paper_symbols()
    if paper is None:
        return {"error": "تعذّر قراءة الصفقات الورقية"}

    out = {"users": 0, "orphans": 0, "closed": 0}
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM user_binance_credentials WHERE auto_trade_enabled=1")]
        c.close()
    except Exception as e:
        log.error("قائمة المشتركين: %s", e)
        return out

    for d in rows:
        uid = d["user_id"]
        if (d.get("exchange") or "binance") != "binance":
            continue
        try:
            cl = Client(decrypt(d["api_key_encrypted"]),
                        decrypt(d["api_secret_encrypted"]))
            pos = [p for p in cl.futures_position_information()
                   if abs(float(p.get("positionAmt") or 0)) > 0]
            out["users"] += 1
        except Exception as e:
            log.debug("مراكز %s: %s", uid[:8], str(e)[:60])
            continue

        for p in pos:
            sym = p["symbol"]
            if sym in paper:
                continue
            # نُمهل الجديدة — قد تكون فُتحت قبل ثوانٍ ولم تُسجَّل بعد
            try:
                c2 = sqlite3.connect(DB)
                r2 = c2.execute(
                    "SELECT opened_at FROM user_trades WHERE user_id=? AND symbol=? "
                    "AND status='open' ORDER BY id DESC LIMIT 1",
                    (uid, sym)).fetchone()
                c2.close()
                if r2 and (_t.time() - (r2[0] or 0)) < GRACE_SEC:
                    continue
            except Exception:
                pass

            out["orphans"] += 1
            amt = float(p["positionAmt"])
            direction = "LONG" if amt > 0 else "SHORT"
            try:
                res = await close_position_for_user(uid, sym, direction)
                if res.get("success"):
                    out["closed"] += 1
                    log.warning("🛡️ أُغلقت يتيمة: %s %s (%s)",
                                sym, direction, uid[:8])
                else:
                    log.error("🛡️ فشل إغلاق يتيمة %s: %s",
                              sym, str(res.get("error"))[:60])
            except Exception as e:
                log.error("🛡️ يتيمة %s: %s", sym, str(e)[:60])

        # 👻 المصالحة العكسية: صفقة "مفتوحة" في سجلّنا وليست على المنصّة.
        #    مقيس: FETUSDT و ONGUSDT بقيتا open ساعتين بعد أن أغلقهما
        #    أمر الوقف على باينانس — لأن close_position_for_user تخرج
        #    قبل log_close حين لا تجد مركزاً.
        try:
            out["ghosts"] = out.get("ghosts", 0) + _close_ghosts(
                uid, {p["symbol"] for p in pos}, cl)
        except Exception as e:
            log.debug("أشباح %s: %s", uid[:8], str(e)[:60])

    if out["orphans"] or out.get("ghosts"):
        log.warning("🛡️ الحارس: %d مشترك · %d يتيمة (أُغلق %d) · %d شبح سُجّل",
                    out["users"], out["orphans"], out["closed"], out.get("ghosts", 0))
    return out


def _close_ghosts(user_id: str, live: set, client) -> int:
    """يُغلق في السجلّ ما لم يعد على المنصّة — بسعر السوق الحاليّ."""
    from services.user_trades import log_close
    n = 0
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT symbol, opened_at FROM user_trades "
            "WHERE user_id=? AND status='open'", (user_id,))]
        c.close()
    except Exception:
        return 0
    import time as _t
    for r in rows:
        sym = r["symbol"]
        if sym in live:
            continue
        if (_t.time() - (r.get("opened_at") or 0)) < GRACE_SEC:
            continue
        px = 0.0
        try:
            px = float(client.futures_symbol_ticker(symbol=sym).get("price") or 0)
        except Exception:
            pass
        if px <= 0:
            continue
        try:
            log_close(user_id, sym, px, 0.0, "closed_on_exchange", "futures")
            n += 1
            log.warning("👻 سُجّل إغلاق %s للمستخدم %s (أُغلقت على المنصّة)",
                        sym, user_id[:8])
        except Exception as e:
            log.debug("شبح %s: %s", sym, str(e)[:50])
    return n


async def guard_loop():
    await asyncio.sleep(240)
    while True:
        try:
            await sweep()
        except Exception as e:
            log.error("حلقة الحارس: %s", e)
        await asyncio.sleep(CHECK_EVERY)
