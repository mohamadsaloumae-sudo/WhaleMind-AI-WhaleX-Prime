from fastapi import APIRouter, Depends
from db.database import get_session, Signal
from routers.auth import require_pro
from typing import List

router = APIRouter(prefix="/api/signals", tags=["Signals"])

def _fmt(sigs):
    return [{
        "id": s.id, "radar_type": s.radar_type, "symbol": s.symbol,
        "direction": s.direction, "grade": s.grade, "score": s.score,
        "confidence": s.confidence, "entry": s.entry, "sl": s.sl,
        "tp1": s.tp1, "tp2": s.tp2, "tp3": s.tp3, "leverage": s.leverage,
        "strategies": s.strategies, "created_at": str(s.created_at),
    } for s in sigs]

@router.get("/futures", )
def futures_signals():
    db = get_session()
    try:
        sigs = db.query(Signal).filter(Signal.radar_type=="futures", Signal.is_active==True).order_by(Signal.created_at.desc()).limit(10).all()
        return {"signals": _fmt(sigs)}
    finally:
        db.close()

@router.get("/spot", )
def spot_signals():
    db = get_session()
    try:
        sigs = db.query(Signal).filter(Signal.radar_type=="spot", Signal.is_active==True).order_by(Signal.created_at.desc()).limit(10).all()
        return {"signals": _fmt(sigs)}
    finally:
        db.close()

@router.get("/meme", )
def meme_signals():
    db = get_session()
    try:
        sigs = db.query(Signal).filter(Signal.radar_type=="meme", Signal.is_active==True).order_by(Signal.created_at.desc()).limit(10).all()
        return {"signals": _fmt(sigs)}
    finally:
        db.close()

@router.get("/all", )
def all_signals():
    db = get_session()
    try:
        sigs = db.query(Signal).filter(Signal.is_active==True).order_by(Signal.created_at.desc()).limit(20).all()
        return {"signals": _fmt(sigs)}
    finally:
        db.close()


@router.get("/history")
def signals_history():
    """آخر الصفقات المغلقة بنتائجها (رابح/خاسر + النسبة) من ml_training.db"""
    import sqlite3
    try:
        con = sqlite3.connect("/opt/whalex/ml_training.db")
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT symbol, direction, entry, exit_price, grade, tier,
                   result, pnl_pct, outcome, closed_at, strategies
            FROM training_signals
            WHERE pnl_pct IS NOT NULL AND closed_at IS NOT NULL
              AND closed_at > (strftime('%s', date('now','+4 hours')) - 14400)
            ORDER BY closed_at DESC LIMIT 300
        """).fetchall()
        con.close()
        out = []
        for r in rows:
            out.append({
                "symbol": r["symbol"], "direction": r["direction"],
                "entry": r["entry"], "exit_price": r["exit_price"],
                "grade": r["grade"], "tier": r["tier"],
                "result": r["result"], "pnl_pct": r["pnl_pct"],
                "is_win": bool(r["outcome"]), "closed_at": r["closed_at"],
                "strategies": r["strategies"],
            })
        return {"history": out}
    except Exception as e:
        return {"history": [], "error": str(e)}
