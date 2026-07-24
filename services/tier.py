"""🏅 حالة الاشتراك الحقيقية + رُتَب الولاء."""
from datetime import datetime

LEVELS = [
    (0,  "جديد",   "New",      "⚪"),
    (1,  "برونزي", "Bronze",   "🥉"),
    (3,  "فضّي",   "Silver",   "🥈"),
    (6,  "ذهبي",   "Gold",     "🥇"),
    (12, "بلاتيني", "Platinum", "💎"),
    (24, "ماسي",   "Diamond",  "👑"),
]


def level_for(renewals: int):
    cur = LEVELS[0]
    for need, ar, en, icon in LEVELS:
        if renewals >= need:
            cur = (need, ar, en, icon)
    return {"renewals": renewals, "level_ar": cur[1], "level_en": cur[2], "icon": cur[3]}


def live_status(db, user_id: str):
    """الحقيقة من جدول الاشتراكات لا من عمود ثابت."""
    from db.database import Subscription, User
    now = datetime.utcnow()
    subs = db.query(Subscription).filter(Subscription.user_id == user_id).all()
    active = [s for s in subs if s.expires_at and s.expires_at > now]
    latest = max(subs, key=lambda s: s.expires_at or now, default=None) if subs else None
    is_pro = bool(active)
    exp = latest.expires_at if latest else None
    days_left = max(0, int((exp - now).total_seconds() / 86400)) if (exp and exp > now) else 0
    lv = level_for(len(subs))
    # مزامنة العمود الثابت حتى لا يتناقض
    try:
        u = db.query(User).filter(User.id == user_id).first()
        if u and getattr(u, "tier", None) not in ("admin",):
            want = "pro" if is_pro else "free"
            if u.tier != want:
                u.tier = want
                db.commit()
    except Exception:
        pass
    return {
        "is_pro": is_pro, "tier": "pro" if is_pro else "free",
        "expires_at": str(exp) if exp else None, "days_left": days_left,
        "plan": latest.plan if latest else None, **lv,
    }
