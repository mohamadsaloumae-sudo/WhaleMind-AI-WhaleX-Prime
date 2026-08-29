"""📒 سجلّ صفقات المستخدمين الحقيقية على Binance — فتح وإغلاق ونتيجة فعلية."""
import sqlite3
import time
import logging

log = logging.getLogger("user_trades")
DB = "/opt/whalex/db/whalex.db"


def init():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS user_trades(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        market TEXT DEFAULT 'futures',
        symbol TEXT, direction TEXT,
        entry REAL, exit_price REAL,
        qty REAL, leverage REAL,
        pnl_pct REAL, pnl_usdt REAL,
        order_id TEXT, close_reason TEXT,
        status TEXT DEFAULT 'open',
        opened_at INTEGER, closed_at INTEGER)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ut_user ON user_trades(user_id, status)")
    c.commit(); c.close()


def log_open(user_id: str, symbol: str, direction: str, entry: float,
             qty: float = 0.0, leverage: float = 1.0, order_id: str = "",
             market: str = "futures"):
    """يُسجَّل فقط عند تنفيذ حقيقي ناجح."""
    if not user_id or not symbol or not entry:
        return None
    init()
    try:
        c = sqlite3.connect(DB)
        cur = c.execute(
            "INSERT INTO user_trades(user_id,market,symbol,direction,entry,qty,leverage,order_id,status,opened_at) "
            "VALUES(?,?,?,?,?,?,?,?,'open',?)",
            (user_id, market, symbol, direction, float(entry), float(qty or 0),
             float(leverage or 1), str(order_id or ""), int(time.time())))
        c.commit(); rid = cur.lastrowid; c.close()
        log.info("📒 فتح حقيقي: %s %s %s @%.6g", user_id[:8], symbol, direction, entry)
        return rid
    except Exception as e:
        log.warning("log_open: %s", e)
        return None


def log_close(user_id: str, symbol: str, exit_price: float, pnl_pct: float,
              reason: str = "", market: str = "futures"):
    """يُغلق أحدث صفقة مفتوحة لهذا المستخدم بنتيجتها الفعلية."""
    if not user_id or not symbol:
        return
    init()
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        row = c.execute("SELECT id, entry, qty, leverage FROM user_trades "
                        "WHERE user_id=? AND symbol=? AND status='open' AND market=? "
                        "ORDER BY id DESC LIMIT 1", (user_id, symbol, market)).fetchone()
        if not row:
            c.close(); return
        d = dict(row)
        _usdt = 0.0
        try:
            _notional = (d.get("entry") or 0) * (d.get("qty") or 0)
            _usdt = _notional * (float(pnl_pct) / 100.0) / max(1.0, float(d.get("leverage") or 1))
        except Exception:
            _usdt = 0.0
        c.execute("UPDATE user_trades SET exit_price=?, pnl_pct=?, pnl_usdt=?, close_reason=?, "
                  "status='closed', closed_at=? WHERE id=?",
                  (float(exit_price or 0), round(float(pnl_pct), 3), round(_usdt, 4),
                   str(reason)[:60], int(time.time()), d["id"]))
        c.commit(); c.close()
        log.info("📒 إغلاق حقيقي: %s %s %+.2f%%", user_id[:8], symbol, pnl_pct)
    except Exception as e:
        log.warning("log_close: %s", e)


def stats(user_id: str):
    """أرقام هذا المستخدم وحده."""
    init()
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM user_trades WHERE user_id=? ORDER BY id DESC LIMIT 300", (user_id,))]
        c.close()
    except Exception:
        return {}
    closed = [r for r in rows if r.get("status") == "closed" and r.get("pnl_pct") is not None]
    wins = [r for r in closed if r["pnl_pct"] > 0]
    losses = [r for r in closed if r["pnl_pct"] <= 0]
    by_market = {}
    for m in ("futures", "spot", "meme"):
        mc = [r for r in closed if (r.get("market") or "futures") == m]
        mw = [r for r in mc if r["pnl_pct"] > 0]
        by_market[m] = {
            "trades": len(mc), "wins": len(mw), "losses": len(mc) - len(mw),
            "win_rate": round(len(mw) / len(mc) * 100, 1) if mc else 0,
            "net_pct": round(sum(r["pnl_pct"] for r in mc), 2),
            "net_usdt": round(sum(r.get("pnl_usdt") or 0 for r in mc), 2),
        }
    # 📊 نفصل الربح عن الخسارة — لا الصافي وحده.
    gw_pct = round(sum(r["pnl_pct"] for r in wins), 2)
    gl_pct = round(sum(r["pnl_pct"] for r in losses), 2)
    gw_usd = round(sum(r.get("pnl_usdt") or 0 for r in wins), 2)
    gl_usd = round(sum(r.get("pnl_usdt") or 0 for r in losses), 2)
    open_rows = [r for r in rows if r.get("status") == "open"]
    return {
        "open": len(open_rows),
        "closed": len(closed), "wins": len(wins), "losses": len(losses),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "net_pct": round(sum(r["pnl_pct"] for r in closed), 2),
        "net_usdt": round(sum(r.get("pnl_usdt") or 0 for r in closed), 2),
        "gross_win_pct": gw_pct, "gross_loss_pct": gl_pct,
        "gross_win_usdt": gw_usd, "gross_loss_usdt": gl_usd,
        "avg_win_pct": round(gw_pct / len(wins), 2) if wins else 0,
        "avg_loss_pct": round(gl_pct / len(losses), 2) if losses else 0,
        "best": max((r["pnl_pct"] for r in closed), default=None),
        "worst": min((r["pnl_pct"] for r in closed), default=None),
        "by_market": by_market,
        "recent": closed[:40],
        "open_list": open_rows,
    }
