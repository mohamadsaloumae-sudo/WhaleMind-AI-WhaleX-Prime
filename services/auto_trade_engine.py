"""
WhaleMind Auto-Trade Engine
═══════════════════════════════════════════════════════════════════
يربط الإشارات الجديدة بالتنفيذ التلقائي على Binance للمشتركين

الفلسفة:
- إشارة جديدة Grade A/S تخرج من الرادار
- نجلب كل المستخدمين الذين فعّلوا Auto-Trade
- ننفّذ الإشارة على حساب كل واحد بالتوازي
- نسجّل كل صفقة في DB (لتتبع الأداء)
- إذا فشل تنفيذ مستخدم، لا يؤثر على الباقين
"""

import asyncio
import logging
import sqlite3
from datetime import datetime
from typing import Optional

from services.binance_trader import (
    get_active_auto_traders,
    execute_signal_for_user,
    get_credentials,
)

log = logging.getLogger("auto_trade_engine")

DB_PATH = "/opt/whalex/db/whalex.db"


# ═══════════════════════════════════════════════════════════════
# ─── DB SCHEMA — Auto Trade Logs ──────────────────────────────
# ═══════════════════════════════════════════════════════════════

def init_logs_db():
    """ينشئ جدول auto_trade_logs لتتبع كل صفقة منفّذة"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auto_trade_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            signal_symbol TEXT NOT NULL,
            signal_direction TEXT NOT NULL,
            signal_grade TEXT,
            signal_entry REAL,
            signal_sl REAL,
            signal_tp1 REAL,
            signal_tp2 REAL,
            signal_tp3 REAL,
            signal_leverage INTEGER,
            executed INTEGER DEFAULT 0,
            order_id TEXT,
            executed_quantity REAL,
            error_message TEXT,
            created_at TEXT,
            execution_time_ms INTEGER
        )
    """)
    # فهرس للبحث السريع
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_signal ON auto_trade_logs(user_id, created_at)")
    conn.commit()
    conn.close()
    log.info("✅ auto_trade_logs table ready")


def log_execution(user_id: str, signal: dict, result: dict, execution_ms: int):
    """يسجّل كل محاولة تنفيذ"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO auto_trade_logs
            (user_id, signal_symbol, signal_direction, signal_grade,
             signal_entry, signal_sl, signal_tp1, signal_tp2, signal_tp3,
             signal_leverage, executed, order_id, executed_quantity,
             error_message, created_at, execution_time_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            signal.get("symbol"),
            signal.get("direction"),
            signal.get("grade"),
            signal.get("entry"),
            signal.get("sl"),
            signal.get("tp1"),
            signal.get("tp2"),
            signal.get("tp3"),
            signal.get("leverage"),
            int(result.get("success", False)),
            result.get("order_id"),
            result.get("quantity"),
            result.get("error"),
            datetime.utcnow().isoformat(),
            execution_ms,
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        log.error("log_execution error: %s", e)


# ═══════════════════════════════════════════════════════════════
# ─── EXECUTE FOR USER (مع تتبع الزمن) ─────────────────────────
# ═══════════════════════════════════════════════════════════════

async def execute_for_user_tracked(user_id: str, signal: dict) -> dict:
    """ينفّذ إشارة لمستخدم واحد + يسجّل الوقت"""
    import time
    start = time.time()
    try:
        result = await execute_signal_for_user(user_id, signal)
        elapsed_ms = int((time.time() - start) * 1000)
        log_execution(user_id, signal, result, elapsed_ms)
        
        if result.get("success"):
            log.info(
                "✅ Auto-Trade [%dms]: %s → %s %s qty=%s (order %s)",
                elapsed_ms,
                user_id,
                signal["symbol"],
                signal["direction"],
                result.get("quantity"),
                result.get("order_id"),
            )
        else:
            log.warning(
                "⚠️ Auto-Trade FAILED [%dms]: %s → %s %s — %s",
                elapsed_ms,
                user_id,
                signal["symbol"],
                signal["direction"],
                result.get("error"),
            )
        return result
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        err_result = {"success": False, "error": str(e)}
        log_execution(user_id, signal, err_result, elapsed_ms)
        log.error("Execute error for %s: %s", user_id, e)
        return err_result


# ═══════════════════════════════════════════════════════════════
# ─── BROADCAST TO ALL ACTIVE USERS ────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def broadcast_signal_to_traders(signal: dict) -> dict:
    """
    ينفّذ إشارة على كل المستخدمين النشطين بالتوازي
    
    Returns: {
        "total_users": int,
        "successful": int,
        "failed": int,
        "results": [...]
    }
    """
    # 1. نجلب المستخدمين النشطين
    active_users = get_active_auto_traders()
    
    if not active_users:
        log.info("📭 No active auto-traders for %s %s",
                 signal.get("symbol"), signal.get("direction"))
        return {"total_users": 0, "successful": 0, "failed": 0, "results": []}
    
    log.info("🚀 Broadcasting signal to %d auto-traders: %s %s Grade %s",
             len(active_users),
             signal.get("symbol"),
             signal.get("direction"),
             signal.get("grade"))
    
    # 2. تنفيذ بالتوازي (كل مستخدم مستقل)
    tasks = [execute_for_user_tracked(uid, signal) for uid in active_users]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 3. تجميع النتائج
    successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
    failed = len(results) - successful
    
    log.info(
        "📊 Auto-Trade Broadcast: %d ✅ / %d ❌ (total %d) — %s %s",
        successful, failed, len(active_users),
        signal.get("symbol"), signal.get("direction")
    )
    
    return {
        "total_users": len(active_users),
        "successful": successful,
        "failed": failed,
        "results": [r if isinstance(r, dict) else {"error": str(r)} for r in results],
    }


# ═══════════════════════════════════════════════════════════════
# ─── SIGNAL WRAPPER (للاستدعاء من service.py) ─────────────────
# ═══════════════════════════════════════════════════════════════

async def on_signal_approved(sig) -> None:
    """
    يُستدعى من service.py عند كل إشارة معتمدة
    
    sig: Signal object من engine.py
    """
    # نتحقق Grade A/S فقط (للأمان)
    if sig.grade not in ("A", "S"):
        return
    
    # نُحوّل Signal إلى dict
    signal_dict = {
        "symbol": sig.symbol,
        "direction": sig.direction,
        "grade": sig.grade,
        "entry": sig.entry,
        "sl": sig.sl,
        "tp1": sig.tp1,
        "tp2": sig.tp2,
        "tp3": sig.tp3,
        "leverage": int(sig.leverage),
        "score": sig.score,
        "confidence": sig.confidence,
    }
    
    # ننفّذ بالتوازي
    await broadcast_signal_to_traders(signal_dict)


# ═══════════════════════════════════════════════════════════════
# ─── STATS HELPERS ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def get_user_auto_stats(user_id: str, days: int = 7) -> dict:
    """إحصائيات المستخدم لآخر N يوم"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT executed, signal_grade, signal_symbol
            FROM auto_trade_logs
            WHERE user_id = ?
              AND datetime(created_at) > datetime('now', '-' || ? || ' days')
        """, (user_id, days)).fetchall()
        conn.close()
        
        total = len(rows)
        successful = sum(1 for r in rows if r["executed"])
        failed = total - successful
        
        # توزيع حسب الـ Grade
        by_grade = {}
        for r in rows:
            g = r["signal_grade"] or "?"
            by_grade[g] = by_grade.get(g, 0) + 1
        
        return {
            "total_trades": total,
            "successful": successful,
            "failed": failed,
            "success_rate": round(successful / total * 100, 1) if total else 0,
            "by_grade": by_grade,
        }
    except Exception as e:
        log.error("get_user_stats error: %s", e)
        return {"total_trades": 0, "successful": 0, "failed": 0}


def get_global_auto_stats(days: int = 1) -> dict:
    """إحصائيات الـ Auto-Trade الإجمالية"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        total_row = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(executed) as successful,
                   AVG(execution_time_ms) as avg_ms,
                   COUNT(DISTINCT user_id) as users
            FROM auto_trade_logs
            WHERE datetime(created_at) > datetime('now', '-' || ? || ' days')
        """, (days,)).fetchone()
        
        conn.close()
        
        total = total_row["total"] or 0
        successful = total_row["successful"] or 0
        return {
            "period_days": days,
            "total_executions": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": round(successful / total * 100, 1) if total else 0,
            "avg_execution_ms": int(total_row["avg_ms"] or 0),
            "active_users": total_row["users"] or 0,
        }
    except Exception as e:
        log.error("global_stats error: %s", e)
        return {}


# ═══════════════════════════════════════════════════════════════
# ─── INIT ON IMPORT ──────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

init_logs_db()
