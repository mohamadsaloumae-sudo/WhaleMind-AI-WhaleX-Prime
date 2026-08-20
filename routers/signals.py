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
        "is_active": bool(s.is_active),
        "pnl_pct": getattr(s, "pnl_pct", None),
        "close_reason": getattr(s, "close_reason", None),
        "closed_at": str(getattr(s, "closed_at", "") or ""),
        "is_win": (None if getattr(s, "pnl_pct", None) is None else bool(s.pnl_pct >= 0)),
    } for s in sigs]

@router.get("/futures", )
def futures_signals():
    db = get_session()
    try:
        sigs = db.query(Signal).filter(Signal.radar_type.in_(["futures","explosion"]), Signal.grade.in_(["S","A"])).order_by(Signal.created_at.desc()).limit(100).all()
        _seen=set(); sigs=[s for s in sigs if not (s.symbol in _seen or _seen.add(s.symbol))]
        return {"signals": _fmt(sigs)}
    finally:
        db.close()

@router.get("/spot", )
def spot_signals():
    db = get_session()
    try:
        sigs = db.query(Signal).filter(Signal.radar_type=="spot", Signal.grade.in_(["S","A"])).order_by(Signal.created_at.desc()).limit(100).all()
        return {"signals": _fmt(sigs)}
    finally:
        db.close()

@router.get("/meme", )
def meme_signals():
    db = get_session()
    try:
        sigs = db.query(Signal).filter(Signal.radar_type=="meme", Signal.grade.in_(["S","A"])).order_by(Signal.created_at.desc()).limit(100).all()
        return {"signals": _fmt(sigs)}
    finally:
        db.close()

@router.get("/all", )
def all_signals(market: str = "futures"):
    db = get_session()
    try:
        if market == "meme":
            import sqlite3 as _sq, os as _os, datetime as _dt
            _mdb = _os.path.join(_os.path.dirname(__file__), "..", "db", "memecoin.db")
            try:
                _mc = _sq.connect(_mdb); _mc.row_factory = _sq.Row
                _rows = _mc.execute("SELECT symbol,address,chain,score,liq,vol,url,ts,entry_price,status,pnl_pct FROM meme_signals ORDER BY ts DESC LIMIT 50").fetchall()
                _mc.close()
                _out = []
                for _r in _rows:
                    _d = dict(_r)
                    _d["direction"] = "MEME"; _d["radar_type"] = "meme"; _d["grade"] = "-"
                    _d["created_at"] = _dt.datetime.utcfromtimestamp(_d["ts"]).strftime("%Y-%m-%d %H:%M:%S")
                    _out.append(_d)
                return {"signals": _out}
            except Exception:
                return {"signals": []}
        if market == "spot":
            sigs = db.query(Signal).filter(Signal.radar_type=="spot").order_by(Signal.created_at.desc()).limit(100).all()
        else:
            sigs = db.query(Signal).filter(Signal.radar_type.in_(["futures","explosion"]), Signal.grade.in_(["S","A"])).order_by(Signal.created_at.desc()).limit(100).all()
        _seen=set(); sigs=[s for s in sigs if not (s.symbol in _seen or _seen.add(s.symbol))]
        return {"signals": _fmt(sigs)}
    finally:
        db.close()


def _hist_ex(symbol: str) -> str:
    """منصّة العملة — للصفقات القديمة التي لم تُسجّلها."""
    try:
        from services.binance_trader import symbol_exchange
        return symbol_exchange(symbol)
    except Exception:
        return "binance"


@router.get("/history")
def signals_history(market: str = "futures"):
    if market == "meme":
        import sqlite3 as _sq, os as _os
        _mdb = _os.path.join(_os.path.dirname(__file__), "..", "db", "memecoin.db")
        try:
            con = _sq.connect(_mdb); con.row_factory = _sq.Row
            rows = con.execute("SELECT symbol, entry_price, exit_price, pnl_pct, closed_ts, chain, score FROM meme_signals WHERE status='closed' AND pnl_pct IS NOT NULL AND closed_ts > (strftime('%s', date('now','+4 hours')) - 14400) ORDER BY closed_ts DESC LIMIT 300").fetchall()
            con.close()
            return {"history": [{"symbol": r["symbol"], "direction": "MEME", "entry": r["entry_price"],
                                 "exit_price": r["exit_price"], "pnl_pct": r["pnl_pct"],
                                 "is_win": bool((r["pnl_pct"] or 0) >= 0), "outcome": 1 if (r["pnl_pct"] or 0) >= 0 else 0,
                                 "closed_at": r["closed_ts"], "grade": str(r["score"]), "tier": "MEME",
                                 "strategies": "\U0001F438 " + (r["chain"] or "")} for r in rows]}
        except Exception:
            return {"history": []}
    if market == "spot":
        import sqlite3 as _sq
        try:
            con = _sq.connect("/opt/whalex/db/whalex.db"); con.row_factory = _sq.Row
            rows = con.execute("SELECT symbol, entry, exit_price, pnl_pct, outcome, reason, ts FROM spot_results WHERE ts > (strftime('%s', date('now','+4 hours')) - 14400) ORDER BY ts DESC LIMIT 300").fetchall()
            con.close()
            return {"history": [{"symbol": r["symbol"], "direction": "LONG", "entry": r["entry"],
                                 "exit_price": r["exit_price"], "pnl_pct": r["pnl_pct"],
                                 "is_win": bool(r["outcome"]), "outcome": r["outcome"],
                                 "closed_at": r["ts"], "grade": "A", "tier": "SPOT",
                                 "strategies": "🪙 Spot Accumulation"} for r in rows]}
        except Exception:
            return {"history": []}

    """آخر الصفقات المغلقة بنتائجها (رابح/خاسر + النسبة) من ml_training.db"""
    import sqlite3
    try:
        con = sqlite3.connect("/opt/whalex/ml_training.db")
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT symbol, direction, entry, exit_price, grade, tier,
                   result, pnl_pct, outcome, closed_at, strategies,
                   leverage, exchange
            FROM training_signals
            WHERE pnl_pct IS NOT NULL AND closed_at IS NOT NULL
              AND result IN ('win','loss')
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
                "leverage": r["leverage"] if "leverage" in r.keys() else None,
                # 🌐 المنصّة: المسجّلة إن وُجدت، وإلا نستنتجها من كون المنصّات.
                #    الصفقات القديمة بلا حقل — فكانت تُعرض بشعار باينانس خطأً.
                "exchange": ((r["exchange"] if "exchange" in r.keys() else None)
                             or _hist_ex(r["symbol"])),
            })
        return {"history": out}
    except Exception as e:
        return {"history": [], "error": str(e)}


@router.get("/monthly")
def signals_monthly(market: str = "futures"):
    """ملخّص الشهر (من تاريخ 1 بتوقيت دبي): رابحة/خاسرة + المجاميع"""
    import sqlite3
    if market == "meme":
        import os as _os
        _mdb = _os.path.join(_os.path.dirname(__file__), "..", "db", "memecoin.db")
        try:
            _mc = sqlite3.connect(_mdb); _mc.row_factory = sqlite3.Row
            _rows = _mc.execute("""
                SELECT pnl_pct FROM meme_signals
                WHERE status='closed' AND pnl_pct IS NOT NULL
                  AND closed_ts > (strftime('%s', date('now','+4 hours','start of month')) - 14400)
            """).fetchall()
            _mc.close()
            _w = [r["pnl_pct"] for r in _rows if r["pnl_pct"] >= 0]
            _l = [r["pnl_pct"] for r in _rows if r["pnl_pct"] < 0]
            _tp = sum(_w); _tl = sum(abs(x) for x in _l)
            return {"wins_count": len(_w), "losses_count": len(_l),
                    "total_profit_pct": round(_tp, 2), "total_loss_pct": round(_tl, 2),
                    "net_pct": round(_tp - _tl, 2), "total_trades": len(_rows)}
        except Exception:
            return {"wins_count": 0, "losses_count": 0, "total_profit_pct": 0,
                    "total_loss_pct": 0, "net_pct": 0, "total_trades": 0}
    if market == "spot":
        try:
            con = sqlite3.connect("/opt/whalex/db/whalex.db"); con.row_factory = sqlite3.Row
            rows = con.execute("""
                SELECT pnl_pct, outcome FROM spot_results
                WHERE pnl_pct IS NOT NULL
                  AND ts > (strftime('%s', date('now','+4 hours','start of month')) - 14400)
            """).fetchall()
            con.close()
            _w = [r for r in rows if r["outcome"]]; _l = [r for r in rows if not r["outcome"]]
            _tp = sum(r["pnl_pct"] for r in _w); _tl = sum(abs(r["pnl_pct"]) for r in _l)
            return {"wins_count": len(_w), "losses_count": len(_l),
                    "total_profit_pct": round(_tp, 2), "total_loss_pct": round(_tl, 2),
                    "net_pct": round(_tp - _tl, 2), "total_trades": len(rows)}
        except Exception:
            return {"wins_count": 0, "losses_count": 0, "total_profit_pct": 0,
                    "total_loss_pct": 0, "net_pct": 0, "total_trades": 0}
    try:
        con = sqlite3.connect("/opt/whalex/ml_training.db")
        con.row_factory = sqlite3.Row
        # بداية الشهر بتوقيت دبي (UTC+4): أول يوم في الشهر منتصف الليل، محوّل لـUTC
        rows = con.execute("""
            SELECT pnl_pct, outcome FROM training_signals
            WHERE pnl_pct IS NOT NULL AND closed_at IS NOT NULL
              AND result IN ('win','loss')
              AND closed_at > (strftime('%s', date('now','+4 hours','start of month')) - 14400)
        """).fetchall()
        con.close()
        wins = [r for r in rows if r["outcome"]]
        losses = [r for r in rows if not r["outcome"]]
        total_profit = sum(r["pnl_pct"] for r in wins)
        total_loss = sum(abs(r["pnl_pct"]) for r in losses)
        return {
            "wins_count": len(wins),
            "losses_count": len(losses),
            "total_profit_pct": round(total_profit, 2),
            "total_loss_pct": round(total_loss, 2),
            "net_pct": round(total_profit - total_loss, 2),
            "total_trades": len(rows),
        }
    except Exception as e:
        return {"wins_count": 0, "losses_count": 0, "total_profit_pct": 0, "total_loss_pct": 0, "net_pct": 0, "error": str(e)}
