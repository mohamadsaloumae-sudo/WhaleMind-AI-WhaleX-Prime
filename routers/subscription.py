from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from db.database import get_session, User, Subscription
from routers.auth import get_current_user
from services.tron_verify import verify_usdt_payment

router = APIRouter(prefix="/api/subscription", tags=["Subscription"])

# ─── الخطط والأسعار (USDT) ───
PLANS = {
    "month":   {"price": 100.0, "days": 30,  "label": "شهر"},
    "quarter": {"price": 270.0, "days": 90,  "label": "3 أشهر"},
}


class UpgradeBody(BaseModel):
    tx_hash: str
    plan: str = "month"


@router.get("/plans")
def get_plans():
    """قائمة الخطط والأسعار + عنوان المحفظة"""
    import os
    return {
        "plans": [
            {"id": k, "price": v["price"], "days": v["days"], "label": v["label"]}
            for k, v in PLANS.items()
        ],
        "wallet_address": os.getenv("WALLET_ADDRESS", ""),
        "network": "TRON (TRC20)",
        "currency": "USDT",
    }


@router.post("/upgrade")
def upgrade(body: UpgradeBody, user=Depends(get_current_user)):
    # 1) نتحقّق أنّ الخطّة صحيحة
    plan = PLANS.get(body.plan)
    if not plan:
        raise HTTPException(400, "خطّة غير صالحة")

    tx = body.tx_hash.strip()
    if not tx or len(tx) < 40:
        raise HTTPException(400, "رقم المعاملة (tx_hash) غير صالح")

    db = get_session()
    try:
        # 2) منع التكرار — هل استُخدم هذا tx_hash من قبل؟
        existing = db.query(Subscription).filter(Subscription.tx_hash == tx).first()
        if existing:
            raise HTTPException(409, "رقم المعاملة مُستخدَم مسبقاً — لا يمكن استخدامه مرّتين")

        # 3) التحقّق الحقيقي من الدفع على شبكة TRON
        result = verify_usdt_payment(tx, min_amount=plan["price"])
        if not result["ok"]:
            raise HTTPException(402, "فشل التحقّق من الدفع: " + result["reason"])

        # 4) الدفع صحيح — نرقّي المستخدم
        u = db.query(User).filter(User.id == user["sub"]).first()
        if not u:
            raise HTTPException(404, "المستخدم غير موجود")

        # نحسب تاريخ الانتهاء (نمدّد إن كان مشتركاً)
        now = datetime.utcnow()
        base = now
        cur = db.query(Subscription).filter(
            Subscription.user_id == u.id
        ).order_by(Subscription.expires_at.desc()).first()
        if cur and cur.expires_at and cur.expires_at > now:
            base = cur.expires_at  # نمدّد من نهاية الاشتراك الحالي

        expires = base + timedelta(days=plan["days"])

        u.tier = "pro"
        sub = Subscription(
            user_id=u.id,
            plan=body.plan,
            tx_hash=tx,
            amount_paid=result["amount"],
            expires_at=expires,
        )
        db.add(sub)
        db.commit()
        return {
            "status": "upgraded",
            "plan": plan["label"],
            "amount_paid": result["amount"],
            "expires_at": str(expires),
        }
    finally:
        db.close()


@router.get("/status")
def sub_status(user=Depends(get_current_user)):
    db = get_session()
    try:
        u = db.query(User).filter(User.id == user["sub"]).first()
        sub = db.query(Subscription).filter(
            Subscription.user_id == user["sub"]
        ).order_by(Subscription.created_at.desc()).first()

        # نتحقّق أنّ الاشتراك لم ينتهِ
        is_active = False
        if u and u.tier in ("pro", "admin"):
            if u.tier == "admin":
                is_active = True
            elif sub and sub.expires_at and sub.expires_at > datetime.utcnow():
                is_active = True

        return {
            "tier": u.tier if u else "free",
            "expires_at": str(sub.expires_at) if sub and sub.expires_at else None,
            "is_active": is_active,
        }
    finally:
        db.close()
