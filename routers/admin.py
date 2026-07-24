from fastapi import APIRouter, Depends, HTTPException
from db.database import get_session, User, Trade, Signal, Subscription
from routers.auth import require_admin
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/stats")
def stats(user=Depends(require_admin)):
    db = get_session()
    try:
        total_users = db.query(User).count()
        pro_users = db.query(User).filter(User.tier == "pro").count()
        total_trades = db.query(Trade).count()
        total_signals = db.query(Signal).count()
        return {
            "total_users": total_users,
            "pro_users": pro_users,
            "free_users": total_users - pro_users,
            "total_trades": total_trades,
            "total_signals": total_signals,
        }
    finally:
        db.close()

@router.get("/users")
def list_users(user=Depends(require_admin)):
    db = get_session()
    try:
        users = db.query(User).order_by(User.created_at.desc()).limit(100).all()
        return {"users": [{"id": u.id, "username": u.username, "tier": u.tier, "demo_balance": u.demo_balance, "created_at": str(u.created_at)} for u in users]}
    finally:
        db.close()

@router.post("/users/{user_id}/grant-pro")
def grant_pro(user_id: str, user=Depends(require_admin)):
    db = get_session()
    try:
        u = db.query(User).filter(User.id == user_id).first()
        if not u:
            from fastapi import HTTPException
            raise HTTPException(404, "User not found")
        u.tier = "pro"
        # ننشئ سجلّ اشتراك (30 يوماً) — بدونه البوّابة ترى is_active=false ولا تفتح الصفحات
        from datetime import datetime, timedelta
        from db.database import Subscription
        expires = datetime.utcnow() + timedelta(days=30)
        sub = Subscription(
            user_id=u.id, plan="month", tx_hash=f"admin-grant-{u.id}-{int(datetime.utcnow().timestamp())}",
            amount_paid=0.0, expires_at=expires,
        )
        db.add(sub)
        db.commit()
        return {"status": "ok", "user_id": user_id, "tier": "pro", "expires_at": str(expires)}
    finally:
        db.close()

class SignalBody(BaseModel):
    radar_type: str
    symbol: str
    direction: str
    grade: str = "B"
    score: float = 75.0
    confidence: float = 75.0
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    tp3: Optional[float] = None
    leverage: Optional[float] = None
    strategies: str = ""

@router.delete("/users/{user_id}")
def delete_user(user_id: str, user=Depends(require_admin)):
    """حذف مستخدم نهائياً (لا يمكن حذف الأدمن نفسه)"""
    db = get_session()
    try:
        if user_id == user["sub"]:
            raise HTTPException(400, "لا يمكنك حذف حسابك")
        u = db.query(User).filter(User.id == user_id).first()
        if not u:
            raise HTTPException(404, "المستخدم غير موجود")
        if u.tier == "admin":
            raise HTTPException(403, "لا يمكن حذف حساب أدمن")
        db.delete(u)
        db.commit()
        return {"status": "deleted", "user_id": user_id}
    finally:
        db.close()


@router.post("/users/{user_id}/revoke-pro")
def revoke_pro(user_id: str, user=Depends(require_admin)):
    """إلغاء اشتراك PRO (إرجاع لـ free)"""
    db = get_session()
    try:
        u = db.query(User).filter(User.id == user_id).first()
        if not u:
            raise HTTPException(404, "المستخدم غير موجود")
        if u.tier == "admin":
            raise HTTPException(403, "لا يمكن تعديل حساب أدمن")
        u.tier = "free"
        db.commit()
        return {"status": "ok", "user_id": user_id, "tier": "free"}
    finally:
        db.close()


@router.post("/signals/publish")
async def publish_signal(body: SignalBody, user=Depends(require_admin)):
    db = get_session()
    try:
        sig = Signal(**body.dict())
        db.add(sig); db.commit(); db.refresh(sig)
        # Broadcast to Telegram
        from services.telegram import TG
        await TG.broadcast_signal(body.dict())
        return {"status": "published", "signal_id": sig.id}
    finally:
        db.close()

@router.delete("/signals/{signal_id}")
def delete_signal(signal_id: str, user=Depends(require_admin)):
    db = get_session()
    try:
        sig = db.query(Signal).filter(Signal.id == signal_id).first()
        if sig:
            sig.is_active = False
            db.commit()
        return {"status": "ok"}
    finally:
        db.close()

# ═══════════════ ملف المستخدم التفصيلي ═══════════════
@router.get("/users/{user_id}/detail")
def user_detail(user_id: str, user=Depends(require_admin)):
    """كل شيء عن مشترك: بياناته، اشتراكه، ونتائج تداوله في كل سوق."""
    import sqlite3
    from datetime import datetime as _dt
    out = {"user_id": user_id}
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user_id).first()
        if u:
            out["email"] = getattr(u, "email", None)
            out["telegram_id"] = getattr(u, "telegram_id", None)
            out["created_at"] = str(getattr(u, "created_at", "") or "")
        sub = db.query(Subscription).filter(Subscription.user_id == user_id)\
                .order_by(Subscription.expires_at.desc()).first()
        if sub:
            exp = sub.expires_at
            out["subscription"] = {
                "plan": sub.plan, "expires_at": str(exp) if exp else None,
                "amount_paid": sub.amount_paid,
                "active": bool(exp and exp > _dt.utcnow()),
                "days_left": max(0, int((exp - _dt.utcnow()).total_seconds() / 86400)) if exp else 0,
            }
        else:
            out["subscription"] = {"active": False, "days_left": 0}
    except Exception as e:
        out["error"] = str(e)[:120]
    finally:
        db.close()

    def _agg(rows):
        vals = [r for r in rows if r is not None]
        wins = [v for v in vals if v > 0]
        losses = [v for v in vals if v <= 0]
        return {
            "trades": len(vals), "wins": len(wins), "losses": len(losses),
            "win_rate": round(len(wins) / len(vals) * 100, 1) if vals else 0,
            "profit": round(sum(wins), 2), "loss": round(abs(sum(losses)), 2),
            "net": round(sum(vals), 2),
        }

    markets = {}
    try:
        con = sqlite3.connect("/opt/whalex/ml_training.db")
        rows = [r[0] for r in con.execute(
            "SELECT pnl_pct FROM training_signals WHERE pnl_pct IS NOT NULL AND result IN ('win','loss')")]
        con.close()
        markets["futures"] = _agg(rows)
    except Exception:
        markets["futures"] = _agg([])
    try:
        con = sqlite3.connect("/opt/whalex/db/whalex.db")
        rows = [r[0] for r in con.execute("SELECT pnl_pct FROM spot_results WHERE pnl_pct IS NOT NULL")]
        con.close()
        markets["spot"] = _agg(rows)
    except Exception:
        markets["spot"] = _agg([])
    try:
        con = sqlite3.connect("/opt/whalex/db/memecoin.db")
        rows = [r[0] for r in con.execute(
            "SELECT pnl_pct FROM meme_signals WHERE status='closed' AND pnl_pct IS NOT NULL")]
        con.close()
        markets["meme"] = _agg(rows)
    except Exception:
        markets["meme"] = _agg([])
    out["markets"] = markets
    return out


class GrantBody(BaseModel):
    days: int = 30


@router.post("/users/{user_id}/grant-custom")
async def grant_custom(user_id: str, body: GrantBody, user=Depends(require_admin)):
    """تفعيل مجاني بمدة مخصّصة + إصدار روابط القنوات."""
    from datetime import datetime, timedelta
    import uuid as _uuid
    days = max(1, min(int(body.days or 30), 3650))
    db = SessionLocal()
    try:
        cur = db.query(Subscription).filter(Subscription.user_id == user_id)\
                .order_by(Subscription.expires_at.desc()).first()
        base = datetime.utcnow()
        if cur and cur.expires_at and cur.expires_at > base:
            base = cur.expires_at
        expires = base + timedelta(days=days)
        db.add(Subscription(id=str(_uuid.uuid4()), user_id=user_id, plan="pro",
                            amount_paid=0.0, expires_at=expires))
        db.commit()
    finally:
        db.close()
    channels = []
    try:
        from services.membership import issue_links, _clear_reminders
        _clear_reminders(user_id)
        channels = await issue_links(user_id, int(expires.timestamp()))
    except Exception:
        pass
    return {"status": "ok", "days": days, "expires_at": str(expires), "channels": channels}


@router.post("/users/{user_id}/cancel-sub")
async def cancel_sub(user_id: str, user=Depends(require_admin)):
    """إلغاء الاشتراك فوراً + سحب الوصول للقنوات."""
    from datetime import datetime
    db = SessionLocal()
    try:
        for s in db.query(Subscription).filter(Subscription.user_id == user_id).all():
            s.expires_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()
    try:
        from services.membership import revoke_access
        await revoke_access(user_id)
    except Exception:
        pass
    return {"status": "cancelled", "user_id": user_id}


# ═══════════════ تجميد التداول العام ═══════════════
FREEZE_FILE = "/opt/whalex/db/trading_freeze.flag"


@router.get("/freeze")
def freeze_status(user=Depends(require_admin)):
    import os
    return {"frozen": os.path.exists(FREEZE_FILE)}


@router.post("/freeze")
async def set_freeze(enable: bool = True, user=Depends(require_admin)):
    """تجميد/فك تجميد كل التنفيذ الآلي أثناء الصيانة."""
    import os
    if enable:
        os.makedirs(os.path.dirname(FREEZE_FILE), exist_ok=True)
        with open(FREEZE_FILE, "w") as f:
            f.write(str(int(__import__("time").time())))
    else:
        try:
            os.remove(FREEZE_FILE)
        except FileNotFoundError:
            pass
    try:
        from services.notifier import push_note
        await push_note("futures", "alert",
                        "🧊 تم تجميد التداول الآلي مؤقتاً للصيانة" if enable
                        else "✅ عاد التداول الآلي للعمل")
    except Exception:
        pass
    return {"frozen": enable}
