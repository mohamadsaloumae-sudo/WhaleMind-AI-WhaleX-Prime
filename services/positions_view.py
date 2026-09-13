"""🔭 مصدر واحد لمراكز المشترك — الادمن والمشترك يقرآن منه.

كان كلٌّ يقرأ بطريقته فيرى الادمن صفقتين والمشترك لا شيء.
والفيوتشر يُصفّى بـuser_trades: ما لم نفتحه نحن لا يُعرض،
فلا تختلط مراكز المشترك الشخصية بصفقات النظام.
"""
import sqlite3

WX = "/opt/whalex/db/whalex.db"


def spot_open(user_id, prices=None, db=WX):
    """مراكز السبوت المفتوحة. prices: قاموس اختياريّ للاسعار الحيّة."""
    px = prices or {}
    out = []
    try:
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT symbol, exchange, qty, entry, spend, ts "
            "FROM spot_positions_multi "
            "WHERE user_id=? AND status='open' ORDER BY ts DESC",
            (str(user_id),)).fetchall()
        c.close()
    except Exception:
        return out
    for r in rows:
        e = float(r["entry"] or 0)
        if e <= 0:
            continue
        cur = float(px.get(r["symbol"]) or 0) or e
        out.append({
            "symbol": r["symbol"], "direction": "LONG",
            "entry": e, "current": cur,
            "leverage": 1, "size": float(r["qty"] or 0),
            "spend": float(r["spend"] or 0),
            "exchange": r["exchange"], "opened_at": int(r["ts"] or 0),
            "radar": "WhaleX Spot", "kind": "spot",
            "pnl_pct": round((cur - e) / e * 100, 2),
        })
    return out


def ours(user_id, db=WX):
    """رموز الفيوتشر التي فتحها نظامنا لهذا المشترك."""
    try:
        c = sqlite3.connect(db)
        rows = c.execute(
            "SELECT DISTINCT symbol FROM user_trades "
            "WHERE user_id=? AND status='open'", (str(user_id),)).fetchall()
        c.close()
        return {r[0] for r in rows if r and r[0]}
    except Exception:
        return set()


def futures_open(client, user_id, only_ours=True, db=WX):
    """مراكز الفيوتشر. only_ours: نستبعد ما لم نفتحه نحن."""
    out = []
    if client is None:
        return out
    keep = ours(user_id, db) if only_ours else None
    try:
        pos = client.futures_position_information() or []
    except Exception:
        return out
    for p in pos:
        try:
            amt = float(p.get("positionAmt") or 0)
        except Exception:
            continue
        if abs(amt) <= 0:
            continue
        sym = p.get("symbol")
        if keep is not None and sym not in keep:
            continue
        ep = float(p.get("entryPrice") or 0)
        mk = float(p.get("markPrice") or 0)
        lev = float(p.get("leverage") or 1) or 1
        pnl = 0.0
        if ep > 0 and mk > 0:
            mv = (mk - ep) / ep if amt > 0 else (ep - mk) / ep
            pnl = round(mv * 100 * lev, 2)
        out.append({
            "symbol": sym, "direction": "LONG" if amt > 0 else "SHORT",
            "entry": ep, "current": mk, "size": abs(amt),
            "leverage": lev, "pnl_pct": pnl, "kind": "futures",
        })
    return out


def spot_closed(user_id, limit=50, db=WX):
    """سجلّ صفقات السبوت المغلقة — للمشترك والادمن معاً.

    كانت تختفي عند الاغلاق ولا يبقى لها اثر في اي صفحة،
    رغم ان الجدول يحفظ سعر الخروج والربح كاملين.
    """
    out = []
    try:
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT symbol, exchange, qty, entry, spend, ts, "
            "closed_ts, exit_price, pnl_pct FROM spot_positions_multi "
            "WHERE user_id=? AND status='closed' "
            "ORDER BY COALESCE(closed_ts, ts) DESC LIMIT ?",
            (str(user_id), int(limit))).fetchall()
        c.close()
    except Exception:
        return out
    for r in rows:
        e = float(r["entry"] or 0)
        xp = r["exit_price"]
        p = r["pnl_pct"]
        if p is None and e > 0 and xp:
            p = (float(xp) - e) / e * 100
        out.append({
            "symbol": r["symbol"], "direction": "LONG",
            "entry": e, "exit_price": float(xp) if xp else None,
            "pnl_pct": round(float(p), 2) if p is not None else None,
            "is_win": bool(p is not None and float(p) > 0),
            "size": float(r["qty"] or 0),
            "spend": float(r["spend"] or 0),
            "exchange": r["exchange"],
            "opened_at": int(r["ts"] or 0),
            "closed_at": int(r["closed_ts"] or 0),
            "kind": "spot",
        })
    return out
