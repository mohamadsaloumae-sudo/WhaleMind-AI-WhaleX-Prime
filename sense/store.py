"""🗄️ ذاكرة المستشعر — سلسلة زمنية لكل عملة، بلا حذف.

كل دقيقة نكتب صفا لكل عملة. فنعرف ماذا كانت قبل ساعة وامس واسبوع.
والتصنيف لاحقا يُبنى على التاريخ لا اللحظة.
"""
import time
import sqlite3
import logging

log = logging.getLogger("sense_store")
DB = "/opt/whalex/db/market_sense.db"


def conn():
    c = sqlite3.connect(DB, timeout=15)
    c.execute("""CREATE TABLE IF NOT EXISTS pulse(
        ts INTEGER, symbol TEXT, exchange TEXT,
        px REAL, rv REAL, roll REAL, cs REAL, kyle REAL,
        vpin REAL, div REAL, vol24 REAL,
        PRIMARY KEY(ts, symbol))""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_sym ON pulse(symbol, ts)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_ts ON pulse(ts)")
    c.execute("PRAGMA journal_mode=WAL")
    return c


def write_batch(rows):
    """rows: [(symbol, exchange, dict_measures, vol24), ...]"""
    if not rows:
        return 0
    ts = int(time.time() // 60 * 60)
    try:
        c = conn()
        c.executemany(
            "INSERT OR REPLACE INTO pulse(ts,symbol,exchange,px,rv,roll,cs,"
            "kyle,vpin,div,vol24) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            [(ts, s, ex, m.get("px"), m.get("rv"), m.get("roll"), m.get("cs"),
              m.get("kyle"), m.get("vpin"), m.get("div"), v24)
             for s, ex, m, v24 in rows if m])
        c.commit()
        n = c.total_changes
        c.close()
        return n
    except Exception as e:
        log.warning("write_batch: %s", str(e)[:80])
        return 0


def history(symbol, hours=24):
    c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute(
        "SELECT * FROM pulse WHERE symbol=? AND ts >= ? ORDER BY ts",
        (symbol, int(time.time()) - hours * 3600))]
    c.close()
    return rows


def latest(limit=1000):
    c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    c.row_factory = sqlite3.Row
    t = c.execute("SELECT MAX(ts) FROM pulse").fetchone()[0]
    if not t:
        c.close()
        return []
    rows = [dict(r) for r in c.execute(
        "SELECT * FROM pulse WHERE ts=? LIMIT ?", (t, limit))]
    c.close()
    return rows


def stats():
    c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    n = c.execute("SELECT COUNT(*) FROM pulse").fetchone()[0]
    s = c.execute("SELECT COUNT(DISTINCT symbol) FROM pulse").fetchone()[0]
    t0 = c.execute("SELECT MIN(ts) FROM pulse").fetchone()[0]
    t1 = c.execute("SELECT MAX(ts) FROM pulse").fetchone()[0]
    c.close()
    return {"rows": n, "symbols": s, "from": t0, "to": t1}
