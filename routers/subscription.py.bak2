from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from db.database import get_session, User, Subscription
from routers.auth import get_current_user

router = APIRouter(prefix="/api/subscription", tags=["Subscription"])

class UpgradeBody(BaseModel):
    tx_hash: str
    amount_paid: float = 50.0

@router.post("/upgrade")
def upgrade(body: UpgradeBody, user=Depends(get_current_user)):
    db = get_session()
    try:
        u = db.query(User).filter(User.id == user["sub"]).first()
        if not u:
            raise HTTPException(404, "User not found")
        if u.tier == "pro":
            return {"status": "already_pro"}
        
        u.tier = "pro"
        sub = Subscription(
            user_id=u.id,
            tx_hash=body.tx_hash,
            amount_paid=body.amount_paid,
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db.add(sub); db.commit()
        return {"status": "upgraded", "expires_at": str(sub.expires_at)}
    finally:
        db.close()

@router.get("/status")
def sub_status(user=Depends(get_current_user)):
    db = get_session()
    try:
        u = db.query(User).filter(User.id == user["sub"]).first()
        sub = db.query(Subscription).filter(Subscription.user_id == user["sub"]).order_by(Subscription.created_at.desc()).first()
        return {
            "tier": u.tier if u else "free",
            "expires_at": str(sub.expires_at) if sub else None,
            "is_active": u.tier in ("pro", "admin") if u else False,
        }
    finally:
        db.close()
