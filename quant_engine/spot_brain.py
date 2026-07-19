"""🪙🧠 نموذج تعلّم السبوت — معزول تماماً عن نموذج الفيوتشر."""
import sqlite3, time, logging
log = logging.getLogger("spot_brain")
DB = "/opt/whalex/db/whalex.db"


def _table():
    try:
        c = sqlite3.connect(DB)
        c.execute("""CREATE TABLE IF NOT EXISTS spot_training (
            id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT,
            taker REAL, vol REAL, rsi REAL, range_pos REAL,
            outcome INTEGER, pnl REAL, ts INTEGER)""")
        c.commit(); c.close()
    except Exception as e:
        log.debug("table: %s", e)


def record_spot_signal(symbol, taker, vol, rsi, range_pos):
    _table()
    try:
        c = sqlite3.connect(DB)
        c.execute("INSERT INTO spot_training(symbol,taker,vol,rsi,range_pos,outcome,pnl,ts) VALUES(?,?,?,?,?,NULL,NULL,?)",
                  (symbol, taker, vol, rsi, range_pos, int(time.time())))
        c.commit(); c.close()
    except Exception as e:
        log.debug("rec sig: %s", e)


def record_spot_outcome(symbol, outcome, pnl):
    try:
        c = sqlite3.connect(DB)
        c.execute("""UPDATE spot_training SET outcome=?, pnl=? WHERE id=(
            SELECT id FROM spot_training WHERE symbol=? AND outcome IS NULL ORDER BY id DESC LIMIT 1)""",
                  (int(outcome), float(pnl), symbol))
        c.commit(); c.close()
    except Exception as e:
        log.debug("rec out: %s", e)


def predict_spot(taker, vol, rsi, range_pos):
    """يتنبأ باحتمال نجاح إشارة من الإشارات التاريخية المشابهة."""
    _table()
    try:
        c = sqlite3.connect(DB)
        rows = c.execute("SELECT taker,vol,rsi,range_pos,outcome FROM spot_training WHERE outcome IS NOT NULL").fetchall()
        c.close()
    except Exception:
        rows = []
    if len(rows) < 15:
        return 0.55, f"تدريب مبدئي ({len(rows)} نتيجة)"
    sim = [o for (t, v, r, rp, o) in rows if abs(t - taker) < 0.04 and abs(v - vol) < 0.25]
    if len(sim) >= 5:
        p = sum(sim) / len(sim)
        return p, f"من {len(sim)} إشارة مشابهة"
    p = sum(o for *_, o in rows) / len(rows)
    return p, f"المتوسط العام ({len(rows)})"
