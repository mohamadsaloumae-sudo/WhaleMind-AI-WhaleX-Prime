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
        db.commit()
        return {"status": "ok", "user_id": user_id, "tier": "pro"}
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
