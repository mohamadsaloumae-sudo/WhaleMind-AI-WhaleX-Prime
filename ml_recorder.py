import sqlite3
import logging
import time
from typing import Optional

log = logging.getLogger("ml_recorder")
DB_PATH = "/opt/whalex/ml_training.db"


def _ensure_cols():
    try:
        conn = sqlite3.connect(DB_PATH)
        for col, typ in (("ob_pressure", "REAL"), ("cvd_flow", "TEXT"),
                         ("peak_pnl", "REAL"), ("close_reason", "TEXT"),
                         ("leverage", "REAL"), ("exchange", "TEXT"),
                         ("tp2", "REAL"), ("tp3", "REAL")):
            try: conn.execute(f"ALTER TABLE training_signals ADD COLUMN {col} {typ}")
            except Exception: pass
        conn.commit(); conn.close()
    except Exception: pass

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


def _sym_exchange(symbol: str) -> str:
    """منصّة العملة — الحصرية على منصّاتها والباقي باينانس."""
    try:
        from services.binance_trader import symbol_exchange
        return symbol_exchange(symbol)
    except Exception:
        return "binance"


def record_signal(trade) -> Optional[int]:
    try:
        _init_db()
        _ensure_cols()
        try:
            from quant_engine.ml_brain import live_context
            _lc = live_context(trade.symbol)
        except Exception:
            _lc = {"ob_pressure": None, "cvd_flow": None}

        # 📊 الحقول التمييزية: كانت تُسجَّل أصفاراً في 3084 صفقة لأن Signal لا يحملها.
        #    نحسبها هنا من الشموع الحيّة — بلا لمس منطق أي رادار.
        _ind = {"stoch_k": 0.0, "stoch_d": 0.0, "macd_hist": 0.0,
                "funding": 0.0, "oi_change": 0.0, "regime": ""}
        try:
            from quant_engine.ob_stream import get_klines as _wsk
            _kl = _wsk(trade.symbol, "15m", 60)
            if _kl and len(_kl) >= 30:
                _cl = [float(k[4]) for k in _kl]
                from radars.futures.engine import stoch_rsi as _sr, macd as _mc
                _sk, _sd = _sr(_cl)
                _ind["stoch_k"], _ind["stoch_d"] = round(_sk, 2), round(_sd, 2)
                _m = _mc(_cl)
                _ind["macd_hist"] = round(_m[2] if isinstance(_m, (list, tuple)) and len(_m) > 2 else 0.0, 6)
        except Exception as _ie:
            log.debug("ind calc: %s", _ie)
        try:
            import asyncio as _aio
            from radars.futures.engine import get_funding_rate as _gf, get_oi_change as _go
            _loop = _aio.get_event_loop()
            if _loop.is_running():
                _ind["funding"] = 0.0   # لا نحجب الحلقة — يُملأ من live_context لاحقاً
            else:
                _ind["funding"] = round(_loop.run_until_complete(_gf(trade.symbol)) or 0.0, 6)
        except Exception:
            pass
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("""
            INSERT INTO training_signals (
                timestamp, symbol, direction, entry, sl, tp1,
                score, confidence, grade, tier, strategies,
                regime, range_pos, rsi, stoch_k, stoch_d, macd_hist,
                funding, oi_change, btc_trend, hawk_phase, hawk_modifier,
                volume_ratio, key_strat_count, ob_pressure, cvd_flow,
                leverage, exchange, tp2, tp3
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            getattr(trade, "timestamp", int(time.time())),
            trade.symbol, trade.direction, trade.entry, trade.sl, trade.tp1,
            trade.score, trade.confidence,
            getattr(trade, "grade", "B"), getattr(trade, "tier", "B"), trade.strategies,
            getattr(trade, "regime", ""), getattr(trade, "range_pos", 0.0),
            getattr(trade, "rsi", 0.0),
            getattr(trade, "stoch_k", 0.0),
            getattr(trade, "stoch_d", 0.0),
            getattr(trade, "macd_hist", 0.0),
            getattr(trade, "funding", 0.0),
            getattr(trade, "oi_change", 0.0),
            getattr(trade, "btc_trend", ""), getattr(trade, "hawk_phase", ""),
            getattr(trade, "hawk_modifier", 1.0), getattr(trade, "volume_ratio", 0.0),
            getattr(trade, "key_strat_count", 0),
            _lc["ob_pressure"], _lc["cvd_flow"],
            # 📊 للشفافية: الرافعة والمنصّة — يراهما المستخدم في الصفقات المغلقة
            float(getattr(trade, "leverage", 0) or 0),
            _sym_exchange(trade.symbol),
            float(getattr(trade, "tp2", 0) or 0),
            float(getattr(trade, "tp3", 0) or 0),
        ))
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        log.info("ML recorded: %s %s (id=%d)", trade.symbol, trade.direction, row_id)
        return row_id
    except Exception as e:
        log.debug("record_signal error: %s", e)
        return None


def update_result(row_id: int, result: str, exit_price: float, pnl_pct: float,
                  peak_pnl: float = None, close_reason: str = None):
    try:
        outcome = 1 if pnl_pct > 0 else 0
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            UPDATE training_signals SET result=?, exit_price=?, pnl_pct=?, closed_at=?, outcome=?,
                   peak_pnl=COALESCE(?, peak_pnl), close_reason=COALESCE(?, close_reason)
            WHERE id=?
        """, (result, exit_price, pnl_pct, int(time.time()), outcome,
              peak_pnl, close_reason, row_id))
        conn.commit()
        conn.close()
        log.info("ML result: id=%d pnl=%.2f outcome=%d", row_id, pnl_pct, outcome)
    except Exception as e:
        log.debug("update_result error: %s", e)


def update_result_by_match(symbol: str, direction: str, entry: float,
                           result: str, exit_price: float, pnl_pct: float,
                           peak_pnl: float = None, close_reason: str = None):
    """تحديث نتيجة آخر إشارة مفتوحة مطابقة (symbol+direction+entry قريب).
    يُستخدم عند إغلاق صفقة لربط النتيجة بالإشارة المسجّلة."""
    # 🧠 نكتب مسار الصفقة قبل نتيجتها — MAE و MFE وزمن القمّة والمدّة
    #    والحاجز الذي لُمس أوّلاً. فالنموذج كان يعرف الدخول والنتيجة
    #    ولا يعرف الرحلة بينهما.
    try:
        from services.lifecycle_recorder import finish as _lf
        _lf(symbol, direction, close_reason or "")
    except Exception:
        pass
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
                UPDATE training_signals SET result=?, exit_price=?, pnl_pct=?, closed_at=?, outcome=?,
                       peak_pnl=COALESCE(?, peak_pnl), close_reason=COALESCE(?, close_reason)
                WHERE id=?
            """, (result, exit_price, pnl_pct, int(time.time()), outcome,
                  peak_pnl, close_reason, rid))
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
