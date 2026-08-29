"""🚑 منقذ الهامش — يُحرّر رصيد المشترك حين يضيق.

المشكلة المقيسة: مشترك رصيده 10.14$ فُتحت له أربع صفقات بهامش 8$،
فبقي متاحاً 2.17$ لا يكفي رسوم الفتح والإغلاق والتمويل. وحارس الهامش
يمنع الجديد، لكنّه لا يُصلح ما هو مفتوح.

فالمنقذ يفحص كل خمس دقائق: إن هبط المتاح تحت الاحتياطيّ، يُغلق أفضل
مركز ربحاً حتى يعود الهامش آمناً.

والقاعدة: نُغلق الرابح لا الخاسر — فحفظ الربح خير من تثبيت الخسارة.
ولا نلمس الخاسرة إلا إذا لم يبقَ رابح والوضع حرج.
"""
import asyncio
import logging
import os
import sqlite3

log = logging.getLogger("margin_rescue")

DB = "/opt/whalex/db/whalex.db"
CHECK_EVERY = 300
OFF_FLAG = "/opt/whalex/db/margin_rescue.off"
CRITICAL_PCT = 0.02      # متاح أقلّ من 2% = حرج، نُغلق حتى الخاسر


def _positions(client):
    """مراكز المشترك مع ربحها وهامشها."""
    out = []
    for p in client.futures_position_information():
        amt = float(p.get("positionAmt") or 0)
        if abs(amt) <= 0:
            continue
        ep = float(p.get("entryPrice") or 0)
        mp = float(p.get("markPrice") or 0)
        no = abs(float(p.get("notional") or 0))
        im = abs(float(p.get("initialMargin") or 0))
        lev = round(no / im, 1) if im > 0 else 1.0
        pct = ((mp - ep) / ep * 100 * lev) * (1 if amt > 0 else -1) if ep else 0.0
        out.append({
            "symbol": p["symbol"],
            "direction": "LONG" if amt > 0 else "SHORT",
            "pnl_pct": round(pct, 2),
            "pnl_usd": float(p.get("unRealizedProfit") or 0),
            "margin": im,
        })
    return out


async def rescue_user(user_id: str, creds_row: dict) -> dict:
    """يفحص مشتركاً واحداً ويُحرّر هامشه إن لزم."""
    from services.binance_trader import decrypt, close_position_for_user
    from services.margin_guard import RESERVE_PCT, MIN_RESERVE_USD
    from binance.client import Client

    out = {"checked": True, "freed": 0, "closed": []}
    cl = Client(decrypt(creds_row["api_key_encrypted"]),
                decrypt(creds_row["api_secret_encrypted"]))
    bal = avail = 0.0
    for b in cl.futures_account_balance():
        if b.get("asset") == "USDT":
            bal = float(b.get("balance") or 0)
            avail = float(b.get("availableBalance") or 0)
            break
    if bal <= 0:
        return out

    reserve = max(bal * RESERVE_PCT, MIN_RESERVE_USD)
    if avail >= reserve:
        return out          # الوضع آمن

    pos = _positions(cl)
    if not pos:
        return out

    critical = avail < bal * CRITICAL_PCT
    # نُرتّب: الأربح أوّلاً
    pos.sort(key=lambda x: -x["pnl_pct"])
    winners = [p for p in pos if p["pnl_pct"] > 0]
    pool = winners if winners else (pos if critical else [])

    if not pool:
        log.warning("🚑 %s: المتاح %.2f$ تحت الاحتياطيّ %.2f$ "
                    "ولا مركز رابح — ننتظر", user_id[:8], avail, reserve)
        return out

    need = reserve - avail
    for p in pool:
        if need <= 0:
            break
        try:
            r = await close_position_for_user(user_id, p["symbol"], p["direction"])
            if r.get("success"):
                out["freed"] += p["margin"]
                out["closed"].append(p["symbol"])
                need -= p["margin"]
                log.warning("🚑 %s: أُغلقت %s %s (%.2f%%) لتحرير %.2f$",
                            user_id[:8], p["symbol"], p["direction"],
                            p["pnl_pct"], p["margin"])
        except Exception as e:
            log.debug("🚑 إغلاق %s: %s", p["symbol"], str(e)[:50])
    return out


async def sweep() -> dict:
    if os.path.exists(OFF_FLAG):
        return {"skipped": True}
    out = {"users": 0, "rescued": 0, "closed": 0}
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM user_binance_credentials WHERE auto_trade_enabled=1")]
        c.close()
    except Exception as e:
        log.error("قائمة المشتركين: %s", e)
        return out

    for d in rows:
        if (d.get("exchange") or "binance") != "binance":
            continue
        try:
            r = await rescue_user(d["user_id"], d)
            out["users"] += 1
            if r.get("closed"):
                out["rescued"] += 1
                out["closed"] += len(r["closed"])
        except Exception as e:
            log.debug("🚑 %s: %s", d["user_id"][:8], str(e)[:60])

    if out["rescued"]:
        log.warning("🚑 منقذ الهامش: أُنقذ %d مشترك · أُغلق %d مركز",
                    out["rescued"], out["closed"])
    return out


async def rescue_loop():
    await asyncio.sleep(300)
    while True:
        try:
            await sweep()
        except Exception as e:
            log.error("حلقة المنقذ: %s", e)
        await asyncio.sleep(CHECK_EVERY)
