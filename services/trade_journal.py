"""📖 سجلّ الصفقة الكامل — الميلاد والحياة والموت وما بعده.

المشكلة المقيسة 10 سبتمبر: النموذج يعرف نقطة الدخول والنتيجة فقط.
لا يعرف على ماذا بُنيت الاشارة، ولا ما تغير وهي مفتوحة، ولا لماذا
اغلقت بالضبط، ولا — وهو الاهم — هل كان الاغلاق صحيحا.

فنسجل اربع مراحل:
  birth  : كل ما رآه الرادار لحظة الاصدار + حالة السوق
  pulse  : لقطة كل دقيقة وهي مفتوحة (سعر · ربح · سوق)
  death  : لحظة الاغلاق بسببها ومؤشراتها
  after  : السعر بعد الاغلاق بـ5 و15 و60 دقيقة — هل احسنا الخروج

الاطفاء: touch /opt/whalex/db/journal.off
"""
import json
import time
import logging
import sqlite3

log = logging.getLogger("journal")
DB = "/opt/whalex/db/trade_journal.db"
OFF = "/opt/whalex/db/journal.off"


def _conn():
    c = sqlite3.connect(DB, timeout=10)
    c.execute("""CREATE TABLE IF NOT EXISTS journal(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_key TEXT, ml_id INTEGER, symbol TEXT, direction TEXT,
        tier TEXT, radar TEXT, stage TEXT, ts INTEGER,
        price REAL, pnl_pct REAL, market TEXT, data TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_key ON journal(trade_key)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_stage ON journal(stage, ts)")
    return c


def _off() -> bool:
    import os
    return os.path.exists(OFF)


def _market() -> str:
    try:
        from services.market_pulse import trend_label
        return trend_label()
    except Exception:
        return "?"


def write(trade_key: str, stage: str, symbol: str, direction: str,
          price: float = 0.0, pnl_pct: float = 0.0, tier: str = "",
          radar: str = "", ml_id: int = 0, data: dict = None) -> None:
    """يكتب سطرا في السجل. لا يرمي ابدا — السجل لا يوقف تداولا."""
    if _off():
        return
    try:
        c = _conn()
        c.execute("""INSERT INTO journal(trade_key, ml_id, symbol, direction,
                     tier, radar, stage, ts, price, pnl_pct, market, data)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (str(trade_key), int(ml_id or 0), symbol, direction,
                   tier, radar, stage, int(time.time()),
                   float(price or 0), float(pnl_pct or 0), _market(),
                   json.dumps(data or {}, ensure_ascii=False)))
        c.commit()
        c.close()
    except Exception as e:
        log.debug("journal %s %s: %s", symbol, stage, e)


def key_of(symbol: str, direction: str, ts: int = 0) -> str:
    return f"{symbol}|{str(direction).upper()}|{int(ts or time.time())}"


def birth(sig, ml_id: int = 0, extra: dict = None) -> str:
    """المرحلة 1 — كل ما رآه الرادار لحظة الاصدار."""
    g = (sig.get if isinstance(sig, dict)
         else lambda k, d=None: getattr(sig, k, d))
    sym = str(g("symbol", ""))
    d = str(g("direction", ""))
    k = key_of(sym, d, int(g("timestamp", 0) or 0))
    fields = ("score", "confidence", "grade", "entry", "sl", "tp1", "tp2",
              "tp3", "leverage", "rsi", "range_pos", "volume_ratio",
              "strategy_count", "regime", "accuracy", "rr_tp1", "rr_tp2",
              "rr_tp3", "btc_trend", "strategies", "funding_rate",
              "open_interest_change", "mtf_15m", "mtf_1h", "mtf_4h")
    data = {f: g(f, None) for f in fields}
    if extra:
        data.update(extra)
    try:
        from services.market_pulse import advice
        data["pulse"] = advice()
    except Exception:
        pass
    write(k, "birth", sym, d, float(g("entry", 0) or 0), 0.0,
          str(g("tier", "")), str(g("source_radar", "")), ml_id, data)
    return k


def pulse(trade_key: str, symbol: str, direction: str, price: float,
          pnl_pct: float, extra: dict = None) -> None:
    """المرحلة 2 — لقطة وهي مفتوحة."""
    write(trade_key, "pulse", symbol, direction, price, pnl_pct,
          data=extra or {})


def death(trade_key: str, symbol: str, direction: str, price: float,
          pnl_pct: float, reason: str, extra: dict = None) -> None:
    """المرحلة 3 — لحظة الاغلاق وسببها."""
    d = {"reason": reason}
    if extra:
        d.update(extra)
    write(trade_key, "death", symbol, direction, price, pnl_pct, data=d)


def after(trade_key: str, symbol: str, direction: str, exit_price: float,
          later_price: float, minutes: int) -> None:
    """المرحلة 4 — هل كان الاغلاق صحيحا؟

    moved_after موجب = السعر تحرك في صالحنا بعد الخروج (خرجنا مبكرا)
    سالب = تحرك ضدنا (الخروج كان صائبا)
    """
    if exit_price <= 0:
        return
    sg = 1.0 if str(direction).upper() == "LONG" else -1.0
    moved = (later_price - exit_price) / exit_price * 100 * sg
    write(trade_key, "after", symbol, direction, later_price, 0.0,
          data={"minutes": minutes, "exit_price": exit_price,
                "moved_after": round(moved, 3),
                "verdict": ("خرجنا مبكرا" if moved > 0.5
                            else "خروج صائب" if moved < -0.5
                            else "متعادل")})
