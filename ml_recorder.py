import sqlite3
import logging
import time
from typing import Optional

log = logging.getLogger("ml_recorder")
DB_PATH = "/opt/whalex/ml_training.db"


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS training_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER, symbol TEXT, direction TEXT,
            entry REAL, sl REAL, tp1 REAL,
            score REAL, confidence REAL, grade TEXT, tier TEXT, strategies TEXT,
            regime TEXT, range_pos REAL, rsi REAL, stoch_k REAL, stoch_d REAL,
            macd_hist REAL, funding REAL, oi_change REAL, btc_trend TEXT,
            hawk_phase TEXT, hawk_modifier REAL, volume_ratio REAL, key_strat_count INTEGER,
            result TEXT, exit_price REAL, pnl_pct REAL, closed_at INTEGER,
            outcome INTEGER DEFAULT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON training_signals(symbol)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outcome ON training_signals(outcome)")
    conn.commit()
    conn.close()


def record_signal(trade) -> Optional[int]:
    try:
        _init_db()
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("""
            INSERT INTO training_signals (
                timestamp, symbol, direction, entry, sl, tp1,
                score, confidence, grade, tier, strategies,
                regime, range_pos, rsi, stoch_k, stoch_d, macd_hist,
                funding, oi_change, btc_trend, hawk_phase, hawk_modifier,
                volume_ratio, key_strat_count
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            getattr(trade, "timestamp", int(time.time())),
            trade.symbol, trade.direction, trade.entry, trade.sl, trade.tp1,
            trade.score, trade.confidence,
            getattr(trade, "grade", "B"), getattr(trade, "tier", "B"), trade.strategies,
            getattr(trade, "regime", ""), getattr(trade, "range_pos", 0.0),
            getattr(trade, "rsi", 0.0), getattr(trade, "stoch_k", 0.0),
            getattr(trade, "stoch_d", 0.0), getattr(trade, "macd_hist", 0.0),
            getattr(trade, "funding", 0.0), getattr(trade, "oi_change", 0.0),
            getattr(trade, "btc_trend", ""), getattr(trade, "hawk_phase", ""),
            getattr(trade, "hawk_modifier", 1.0), getattr(trade, "volume_ratio", 0.0),
            getattr(trade, "key_strat_count", 0),
        ))
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        log.info("ML recorded: %s %s (id=%d)", trade.symbol, trade.direction, row_id)
        return row_id
    except Exception as e:
        log.debug("record_signal error: %s", e)
        return None


def update_result(row_id: int, result: str, exit_price: float, pnl_pct: float):
    try:
        outcome = 1 if pnl_pct > 0 else 0
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            UPDATE training_signals SET result=?, exit_price=?, pnl_pct=?, closed_at=?, outcome=?
            WHERE id=?
        """, (result, exit_price, pnl_pct, int(time.time()), outcome, row_id))
        conn.commit()
        conn.close()
        log.info("ML result: id=%d pnl=%.2f outcome=%d", row_id, pnl_pct, outcome)
    except Exception as e:
        log.debug("update_result error: %s", e)


def update_result_by_match(symbol: str, direction: str, entry: float,
                           result: str, exit_price: float, pnl_pct: float):
    """تحديث نتيجة آخر إشارة مفتوحة مطابقة (symbol+direction+entry قريب).
    يُستخدم عند إغلاق صفقة لربط النتيجة بالإشارة المسجّلة."""
    try:
        outcome = 1 if pnl_pct > 0 else 0
        conn = sqlite3.connect(DB_PATH)
        # نبحث عن آخر إشارة مفتوحة (outcome IS NULL) بنفس العملة والاتجاه، أقرب entry
        row = conn.execute("""
            SELECT id FROM training_signals
            WHERE symbol=? AND direction=? AND outcome IS NULL
            ORDER BY ABS(entry - ?) ASC, id DESC LIMIT 1
        """, (symbol, direction, entry)).fetchone()
        if row:
            rid = row[0]
            conn.execute("""
                UPDATE training_signals SET result=?, exit_price=?, pnl_pct=?, closed_at=?, outcome=?
                WHERE id=?
            """, (result, exit_price, pnl_pct, int(time.time()), outcome, rid))
            conn.commit()
            log.info("ML result matched: %s %s id=%d pnl=%.2f outcome=%d",
                     symbol, direction, rid, pnl_pct, outcome)
        else:
            log.debug("ML no match: %s %s entry=%.6g", symbol, direction, entry)
        conn.close()
    except Exception as e:
        log.debug("update_result_by_match error: %s", e)


def get_training_stats() -> dict:
    try:
        _init_db()
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute("SELECT COUNT(*) FROM training_signals").fetchone()[0]
        closed = conn.execute("SELECT COUNT(*) FROM training_signals WHERE outcome IS NOT NULL").fetchone()[0]
        wins = conn.execute("SELECT COUNT(*) FROM training_signals WHERE outcome=1").fetchone()[0]
        losses = conn.execute("SELECT COUNT(*) FROM training_signals WHERE outcome=0").fetchone()[0]
        conn.close()
        win_rate = (wins / closed * 100) if closed > 0 else 0
        return {"total": total, "closed": closed, "open": total - closed,
                "wins": wins, "losses": losses, "win_rate": round(win_rate, 1),
                "ready_for_training": closed >= 200}
    except Exception as e:
        log.debug("get_training_stats error: %s", e)
        return {}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _init_db()
    print("ml_training.db جاهزة")
    print(get_training_stats())
