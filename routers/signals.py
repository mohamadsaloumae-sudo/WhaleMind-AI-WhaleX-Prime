from fastapi import APIRouter, Depends
from routers.auth import get_current_user
from services.signal_masking import mask_for
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

def _d3():
    """🗂️ حدّ الاحتفاظ: ثلاثة أيام للفيوتشر — والسبوت يبقى حتى يُغلق."""
    from datetime import datetime, timedelta
    return datetime.utcnow() - timedelta(days=3)


@router.get("/futures", )
def futures_signals(user=Depends(get_current_user)):
    db = get_session()
    try:
        sigs = db.query(Signal).filter(Signal.radar_type.in_(["futures","explosion"]), Signal.grade.in_(["S","A"]), Signal.created_at >= _d3()).order_by(Signal.created_at.desc()).limit(1500).all()
        # 🗂️ بلا إزالة تكرار — العملة قد تُعطي إشارات في أيام مختلفة
        return {"signals": _fmt(sigs)}
    finally:
        db.close()

@router.get("/spot", )
def spot_signals(user=Depends(get_current_user)):
    db = get_session()
    try:
        sigs = db.query(Signal).filter(Signal.radar_type=="spot", Signal.grade.in_(["S","A"])).order_by(Signal.created_at.desc()).limit(1500).all()
        return {"signals": _fmt(sigs)}
    finally:
        db.close()

@router.get("/meme", )
def meme_signals(user=Depends(get_current_user)):
    db = get_session()
    try:
        sigs = db.query(Signal).filter(Signal.radar_type=="meme", Signal.grade.in_(["S","A"])).order_by(Signal.created_at.desc()).limit(100).all()
        return {"signals": _fmt(sigs)}
    finally:
        db.close()

@router.get("/all", )
def all_signals(market: str = "futures", user=Depends(get_current_user)):
    db = get_session()
    try:
        if market == "meme":
            import sqlite3 as _sq, os as _os, datetime as _dt
            _mdb = _os.path.join(_os.path.dirname(__file__), "..", "db", "memecoin.db")
            try:
                _mc = _sq.connect(_mdb); _mc.row_factory = _sq.Row
                _rows = _mc.execute("SELECT symbol,address,chain,score,liq,vol,url,ts,entry_price,status,pnl_pct,peak_price,last_price FROM meme_signals ORDER BY ts DESC LIMIT 50").fetchall()
                _mc.close()
                _out = []
                for _r in _rows:
                    _d = dict(_r)
                    _d["direction"] = "MEME"; _d["radar_type"] = "meme"; _d["grade"] = "-"
                    _CH = {"solana": "Solana", "ethereum": "Ethereum", "bsc": "BSC",
                           "base": "Base", "arbitrum": "Arbitrum", "polygon": "Polygon"}
                    _c = (_d.get("chain") or "").lower()
                    _d["exchange"] = ""
                    _d["source"] = "dexscreener"
                    _d["chain_label"] = _CH.get(_c, _c or "-")
                    _d["opened_at"] = _d.get("ts")
                    _d["entry"] = _d.get("entry_price")
                    _d["current"] = _d.get("last_price") or _d.get("entry_price")
                    _d["created_at"] = _dt.datetime.utcfromtimestamp(_d["ts"]).strftime("%Y-%m-%d %H:%M:%S")
                    _out.append(_d)
                return {"signals": _out}
            except Exception:
                return {"signals": []}
        if market == "spot":
            sigs = db.query(Signal).filter(Signal.radar_type=="spot").order_by(Signal.created_at.desc()).limit(1500).all()
        else:
            sigs = db.query(Signal).filter(Signal.radar_type.in_(["futures","explosion"]), Signal.grade.in_(["S","A"]), Signal.created_at >= _d3()).order_by(Signal.created_at.desc()).limit(1500).all()
        # 🗂️ بلا إزالة تكرار — العملة قد تُعطي إشارات في أيام مختلفة
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
def signals_history(market: str = "futures", user=Depends(get_current_user)):
    if market == "meme":
        import sqlite3 as _sq, os as _os
        _mdb = _os.path.join(_os.path.dirname(__file__), "..", "db", "memecoin.db")
        try:
            con = _sq.connect(_mdb); con.row_factory = _sq.Row
            rows = con.execute("SELECT symbol, address, entry_price, exit_price, pnl_pct, peak_price, ts, closed_ts, chain, score, url, liq, vol FROM meme_signals WHERE status='closed' AND pnl_pct IS NOT NULL AND (closed_ts > (strftime('%s','now','+4 hours','start of day','-4 hours')) OR ts > (strftime('%s','now','+4 hours','start of day','-4 hours'))) ORDER BY closed_ts DESC LIMIT 300").fetchall()
            con.close()
            _CH = {"solana": "Solana", "ethereum": "Ethereum", "bsc": "BSC", "base": "Base", "arbitrum": "Arbitrum", "polygon": "Polygon"}
            out = []
            for r in rows:
                _op = r["ts"] or 0
                _cl = r["closed_ts"] or 0
                _ch = (r["chain"] or "").lower()
                _e = float(r["entry_price"] or 0)
                _pk = float(r["peak_price"] or 0)
                _lbl = _CH.get(_ch, _ch or "-")
                out.append({
                    "symbol": r["symbol"], "direction": "MEME",
                    "entry": r["entry_price"], "exit_price": r["exit_price"],
                    "pnl_pct": r["pnl_pct"],
                    "is_win": bool((r["pnl_pct"] or 0) >= 0),
                    "outcome": 1 if (r["pnl_pct"] or 0) >= 0 else 0,
                    "closed_at": _cl, "opened_at": _op,
                    "duration_min": round((_cl - _op) / 60, 1) if (_op and _cl) else None,
                    "exchange": "", "source": "dexscreener",
                    "chain": _ch, "chain_label": _lbl,
                    "url": r["url"] or "", "address": r["address"] or "",
                    "peak_price": r["peak_price"],
                    "peak_pct": round((_pk - _e) / _e * 100, 2) if (_e and _pk) else None,
                    "liq": r["liq"], "vol": r["vol"],
                    "grade": str(r["score"]), "tier": "MEME",
                    "strategies": "DexScreener - " + _lbl,
                })
            return {"history": out}
        except Exception:
            return {"history": []}
    if market == "spot":
        import sqlite3 as _sq
        try:
            con = _sq.connect("/opt/whalex/db/whalex.db"); con.row_factory = _sq.Row
            rows = con.execute(
                "SELECT symbol, entry, exit_price, pnl_pct, outcome, reason, ts, "
                "opened_ts, exchange, path, strategies FROM spot_results "
                "WHERE (ts > (strftime('%s','now','+4 hours','start of day','-4 hours')) OR opened_ts > (strftime('%s','now','+4 hours','start of day','-4 hours'))) "
                "ORDER BY COALESCE(ts,0) DESC LIMIT 300").fetchall()
            con.close()
            _lbl = {"dip": "🪙 صيد القاع", "pullback": "📈 ارتداد في اتجاه صاعد",
                    "breakout": "🚀 اختراق مؤكَّد"}
            out = []
            for r in rows:
                _op = r["opened_ts"] or 0
                out.append({
                    "symbol": r["symbol"], "direction": "LONG", "entry": r["entry"],
                    "exit_price": r["exit_price"], "pnl_pct": r["pnl_pct"],
                    "is_win": bool(r["outcome"]), "outcome": r["outcome"],
                    "closed_at": r["ts"],
                    # 🕐 التوقيتان والمدّة — كانت المدّة غير محسوبة
                    "opened_at": _op,
                    "duration_min": round((r["ts"] - _op) / 60, 1) if _op else None,
                    # 🌐 المنصّة تظهر في المغلقة كما في المفتوحة
                    "exchange": r["exchange"] or "",   # لا نفترض باينانس — المجهول يبقى بلا شعار
                    "path": r["path"] or "",
                    "reason": r["reason"] or "",
                    "grade": "A", "tier": "SPOT",
                    "strategies": r["strategies"] or _lbl.get(r["path"], "🪙 Spot"),
                })
            return {"history": out}
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
                   leverage, exchange, timestamp, sl, tp1, tp2, tp3,
                   peak_pnl, close_reason, rsi, range_pos, volume_ratio,
                   score, confidence
            FROM training_signals
            WHERE pnl_pct IS NOT NULL AND closed_at IS NOT NULL
              -- 🔴 نُخفي الظلّية (shadow) — هي تتبّع نظريّ لا يُنفَّذ على
              -- باينانس إطلاقاً، ووجودها شوّه إحصاء سبتمبر: 566 صفقة
              -- بفوز 46% و -67.9%، بينما الحقيقيّ 306 صفقة بفوز 63%
              -- و +451.9%. والمشترك يرى خسارة وهمية فيفقد ثقته.
              AND result IS NOT NULL AND result NOT IN ('void', 'shadow_hidden')
              AND result NOT LIKE 'shadow%'
              AND pnl_pct > -9
              -- 🔴 صفحة الفيوتشر كانت تعرض صفقات السبوت (tier=SP)
              --    برافعة 1x، فتختلط الأسواق ويشوّه الإحصاء.
              AND tier IN ('MX','PH','A','B','S')
              AND (closed_at > (strftime('%s','now','+4 hours','start of day','-4 hours')) OR timestamp > (strftime('%s','now','+4 hours','start of day','-4 hours')))
            ORDER BY COALESCE(closed_at,0) DESC LIMIT 300
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
                # 📊 تفاصيل كاملة للشفافية
                "opened_at": r["timestamp"], "sl": r["sl"],
                "tp1": r["tp1"], "tp2": r["tp2"], "tp3": r["tp3"],
                "peak_pnl": r["peak_pnl"], "close_reason": r["close_reason"],
                "rsi": r["rsi"], "range_pos": r["range_pos"],
                "volume_ratio": r["volume_ratio"],
                "score": r["score"], "confidence": r["confidence"],
                # 🌐 المنصّة: المسجّلة إن وُجدت، وإلا نستنتجها من كون المنصّات.
                #    الصفقات القديمة بلا حقل — فكانت تُعرض بشعار باينانس خطأً.
                "exchange": ((r["exchange"] if "exchange" in r.keys() else None)
                             or _hist_ex(r["symbol"])),
            })
        return {"history": out}
    except Exception as e:
        return {"history": [], "error": str(e)}


@router.get("/monthly")
def signals_monthly(market: str = "futures", user=Depends(get_current_user)):
    """ملخّص الشهر — من المصدر الموحَّد وحده.

    كانت كل صفحة تحسب بشرطها فتختلف الأرقام: المراكز +451.9%
    والسجلّ -87% لنفس البيانات. والآن لا استعلام إحصائيّ خارج
    services/stats_core.
    """
    from services.stats_core import summary
    return summary(market, "month")


