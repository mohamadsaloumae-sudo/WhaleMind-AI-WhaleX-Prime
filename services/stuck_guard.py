"""🚨 حارس العملات المحجوزة — ينذر ويبيع.

مقيس 16 سبتمبر: HIVE و ALT سُجّلتا مغلقتين بلا بيع فعلي، فبقي
424$ في حساب Ahmedsd111 ونحن نظنها بيعت. فلا USDT حر، وتُرفض
الاشارات الرابحة (STRAX +9% · XCN +6.66%). ولم ينذرنا شيء —
لان النظام لا يقارن سجله بالمنصة ابدا.

كل 15 دقيقة: لكل صفقة مسجلة "مغلقة" خلال 7 ايام، نفحص هل العملة
ما زالت في حساب المشترك بقيمة تُعتد بها. وان وجدناها:
  · انذار فوري في السجل وللادمن
  · بيع تلقائي (ما لم يُطفأ)

الاطفاء: touch /opt/whalex/db/stuck.off
البيع فقط بلا انذار: touch /opt/whalex/db/stuck.noalert
"""
import os
import time
import sqlite3
import logging

log = logging.getLogger("stuck_guard")
DB = "/opt/whalex/db/whalex.db"
OFF = "/opt/whalex/db/stuck.off"
MIN_USD = 5.0
DAYS = 7


def scan(auto_sell: bool = True) -> dict:
    if os.path.exists(OFF):
        return {"skipped": True}
    from services.exchanges import get as _ga
    from services.spot_exec import spot_traders_for

    out = {"checked": 0, "stuck": 0, "sold": 0, "usd": 0.0, "items": []}
    since = int(time.time()) - DAYS * 86400
    c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    c.row_factory = sqlite3.Row

    for ex in ("binance", "bybit", "mexc", "okx", "bitget", "gate"):
        try:
            traders = spot_traders_for(ex)
        except Exception:
            continue
        for u, k, s, p, a, m, tn in traders:
            try:
                cl = _ga(ex).client(k, s, p, futures=False, testnet=tn)
                bal = cl.fetch_balance()
            except Exception:
                continue
            rows = [dict(r) for r in c.execute(
                "SELECT id, symbol, qty FROM spot_positions_multi "
                "WHERE user_id=? AND exchange=? AND status='closed' AND ts>=?",
                (u, ex, since))]
            seen = set()
            for d in rows:
                base = d["symbol"].replace("USDT", "")
                if base in seen:
                    continue
                out["checked"] += 1
                free = float((bal.get(base) or {}).get("free") or 0)
                want = float(d["qty"] or 0)
                if want <= 0 or free < want * 0.5:
                    continue
                # 🛡️ لها صفقة مفتوحة على نفس العملة؟ فالحيازة لها لا محجوزة
                _op = c.execute(
                    "SELECT COUNT(*) FROM spot_positions_multi WHERE user_id=? "
                    "AND exchange=? AND symbol=? AND status='open'",
                    (u, ex, d["symbol"])).fetchone()[0]
                if _op:
                    continue
                try:
                    px = float(cl.fetch_ticker("%s/USDT" % base)["last"])
                except Exception:
                    continue
                usd = free * px
                if usd < MIN_USD:
                    continue
                seen.add(base)
                out["stuck"] += 1
                out["usd"] += usd
                out["items"].append({"user": u[:8], "symbol": d["symbol"],
                                     "qty": free, "usd": round(usd, 2)})
                log.error("🚨 %s %s: %.4f عملة (%.2f$) مسجّلة مغلقة وهي "
                          "في الحساب — النظام يظنّها بيعت",
                          u[:8], d["symbol"], free, usd)
                if auto_sell:
                    try:
                        o = cl.create_order(
                            "%s/USDT" % base, "market", "sell",
                            float(cl.amount_to_precision("%s/USDT" % base, free)))
                        out["sold"] += 1
                        log.warning("🚨✅ بيع محجوزة %s %s: %.2f$",
                                    u[:8], d["symbol"], usd)
                        w = sqlite3.connect(DB, timeout=10)
                        w.execute("UPDATE spot_positions_multi SET exit_price=?, "
                                  "closed_ts=? WHERE id=?",
                                  (px, int(time.time()), d["id"]))
                        w.commit(); w.close()
                    except Exception as e:
                        log.error("🚨❌ بيع %s فشل: %s", d["symbol"], str(e)[:60])
                time.sleep(0.4)
            time.sleep(0.3)
    c.close()
    if out["stuck"]:
        try:
            from services.telegram import send_admin
            send_admin("🚨 <b>عملات محجوزة</b>\\n%d صفقة · %.2f$\\nبِيع %d"
                       % (out["stuck"], out["usd"], out["sold"]))
        except Exception:
            pass
    return out


async def loop():
    import asyncio
    await asyncio.sleep(300)
    while True:
        try:
            r = scan(auto_sell=True)
            if r.get("stuck"):
                log.error("🚨 حارس المحجوزة: %d صفقة · %.2f$ · بِيع %d",
                          r["stuck"], r["usd"], r["sold"])
        except Exception as e:
            log.debug("stuck loop: %s", e)
        await asyncio.sleep(900)
