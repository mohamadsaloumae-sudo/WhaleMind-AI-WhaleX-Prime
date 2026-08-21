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
        users = db.query(User).order_by(User.created_at.desc()).all()
        from services.tier import live_status
        out = []
        for u in users:
            st = live_status(db, u.id)
            out.append({"id": u.id, "username": u.username,
                        "tier": "admin" if u.tier == "admin" else st["tier"],
                        "is_pro": st["is_pro"], "days_left": st["days_left"],
                        "level_ar": st["level_ar"], "icon": st["icon"],
                        "demo_balance": u.demo_balance, "created_at": str(u.created_at)})
        return {"users": out}
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
    db = get_session()
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
        try:
            from services.tier import live_status
            out["status"] = live_status(db, user_id)
        except Exception:
            pass
        try:
            from routers.profile import profile_of
            out["profile"] = profile_of(user_id)
        except Exception:
            out["profile"] = {}
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

    # أداء إشارات المنصة (مرجعي — ليس أرباح المستخدم)
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
    executed = 0
    try:
        con = sqlite3.connect("/opt/whalex/db/whalex.db")
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT signal_symbol, signal_direction, executed, error_message, created_at "
            "FROM auto_trade_logs WHERE user_id=? ORDER BY id DESC LIMIT 500", (user_id,)
        ).fetchall()
        con.close()
        executed = sum(1 for r in rows if dict(r).get("executed"))
        out["auto_trades"] = {
            "total": len(rows),
            "executed": executed,
            "failed": len(rows) - executed,
            "last": [dict(r) for r in rows[:5]],
        }
    except Exception as e:
        out["auto_trades"] = {"total": 0, "executed": 0, "failed": 0, "last": [], "note": str(e)[:60]}
    out["markets"] = markets
    out["has_own_trades"] = executed > 0
    try:
        from services.user_trades import stats as _ustats
        out["ledger"] = _ustats(user_id)
    except Exception:
        out["ledger"] = {}
    return out


class GrantBody(BaseModel):
    days: int = 30


@router.post("/users/{user_id}/grant-custom")
async def grant_custom(user_id: str, body: GrantBody, user=Depends(require_admin)):
    """تفعيل مجاني بمدة مخصّصة + إصدار روابط القنوات."""
    from datetime import datetime, timedelta
    import uuid as _uuid
    days = max(1, min(int(body.days or 30), 3650))
    db = get_session()
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
    db = get_session()
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

# ═══════════════ المراسلة ═══════════════
class MsgBody(BaseModel):
    message: str
    title: str = ""


async def _deliver(user_id: str, text: str):
    """يحفظ الرسالة للمستخدم ويبثّها له وحده."""
    import sqlite3, time as _tm
    try:
        cn = sqlite3.connect("/opt/whalex/db/whalex.db")
        cn.execute("""CREATE TABLE IF NOT EXISTS user_messages(
            id INTEGER PRIMARY KEY, user_id TEXT, message TEXT, created_at INTEGER, seen INTEGER DEFAULT 0)""")
        cn.execute("INSERT INTO user_messages(user_id,message,created_at) VALUES(?,?,?)",
                   (user_id, text, int(_tm.time())))
        cn.commit()
        row = cn.execute("SELECT telegram_id FROM users WHERE id=?", (user_id,)).fetchone()
        cn.close()
        tg = row[0] if row else None
    except Exception:
        tg = None
    try:
        from routers.ws import registry
        await registry.broadcast({
            "event": "admin_dm", "market": "futures", "target_user": user_id,
            "message": text, "message_en": text,
        })
    except Exception:
        pass
    if tg:
        try:
            from services.telegram import send_message
            await send_message(str(tg), text)
        except Exception:
            pass


@router.post("/users/{user_id}/message")
async def dm_user(user_id: str, body: MsgBody, user=Depends(require_admin)):
    """رسالة خاصة لمشترك واحد فقط."""
    txt = (body.title + "\n\n" if body.title else "") + body.message
    await _deliver(user_id, txt)
    return {"status": "sent", "user_id": user_id}


@router.get("/users/{user_id}/messages")
def dm_history(user_id: str, user=Depends(require_admin)):
    import sqlite3
    try:
        cn = sqlite3.connect("/opt/whalex/db/whalex.db"); cn.row_factory = sqlite3.Row
        rows = cn.execute("SELECT message, created_at FROM user_messages WHERE user_id=? ORDER BY id DESC LIMIT 30",
                          (user_id,)).fetchall()
        cn.close()
        return {"messages": [dict(r) for r in rows]}
    except Exception:
        return {"messages": []}


@router.post("/broadcast")
async def broadcast_all(body: MsgBody, user=Depends(require_admin)):
    """بثّ جماعي — للمشتركين الفعّالين فقط."""
    from datetime import datetime
    txt = (body.title + "\n\n" if body.title else "") + body.message
    db = get_session()
    try:
        now = datetime.utcnow()
        subs = db.query(Subscription).filter(Subscription.expires_at > now).all()
        targets = sorted({s.user_id for s in subs if s.user_id})
    finally:
        db.close()
    sent = 0
    for uid in targets:
        try:
            await _deliver(uid, txt)
            sent += 1
        except Exception:
            pass
    return {"status": "sent", "recipients": sent}


# ═══════════════════ 🎁 الإحالات ═══════════════════

@router.get("/referrals")
def admin_referrals(user=Depends(require_admin)):
    """كل المُحيلين · من أحالوا · أرباحهم."""
    import sqlite3
    cn = sqlite3.connect("/opt/whalex/db/whalex.db")
    cn.row_factory = sqlite3.Row
    rows = cn.execute("""
        SELECT r.owner_id, r.code,
               u.username, u.email,
               (SELECT COUNT(*) FROM referral_links l
                 WHERE l.referrer_id = r.owner_id) AS invited,
               (SELECT COUNT(*) FROM referral_links l
                 JOIN referral_earnings e ON e.referred_id = l.referred_id
                WHERE l.referrer_id = r.owner_id) AS converted,
               (SELECT COALESCE(SUM(e.amount),0) FROM referral_earnings e
                 WHERE e.referrer_id = r.owner_id) AS earned,
               (SELECT COALESCE(SUM(w.amount),0) FROM referral_withdrawals w
                 WHERE w.user_id = r.owner_id AND w.status='paid') AS paid_out
          FROM referrals r
          LEFT JOIN users u ON u.id = r.owner_id
         ORDER BY earned DESC
    """).fetchall()
    cn.close()
    out = [{
        "user_id": x["owner_id"], "code": x["code"],
        "name": x["username"] or x["email"] or "",
        "invited": x["invited"], "converted": x["converted"],
        "earned": round(x["earned"] or 0, 2),
        "paid_out": round(x["paid_out"] or 0, 2),
        "owed": round((x["earned"] or 0) - (x["paid_out"] or 0), 2),
    } for x in rows]
    return {
        "referrers": out,
        "total_invited": sum(x["invited"] for x in out),
        "total_earned": round(sum(x["earned"] for x in out), 2),
        "total_owed": round(sum(x["owed"] for x in out), 2),
    }


@router.get("/withdrawals")
def admin_withdrawals(user=Depends(require_admin)):
    """طلبات السحب مع بيانات صاحبها للتحقّق."""
    import sqlite3
    cn = sqlite3.connect("/opt/whalex/db/whalex.db")
    cn.row_factory = sqlite3.Row
    rows = cn.execute("""
        SELECT w.*, u.username, u.email,
               p.name, p.phone, p.country, p.usdt_network,
               (SELECT COUNT(*) FROM referral_links l
                 WHERE l.referrer_id = w.user_id) AS invited
          FROM referral_withdrawals w
          LEFT JOIN users u ON u.id = w.user_id
          LEFT JOIN user_profiles p ON p.user_id = w.user_id
         ORDER BY CASE w.status WHEN 'pending' THEN 0 ELSE 1 END,
                  w.created_at DESC
    """).fetchall()
    cn.close()
    k = rows[0].keys() if rows else []
    g = lambda x, c: (x[c] if c in x.keys() else None) or ""
    return {"withdrawals": [{
        "id": x["id"], "user_id": x["user_id"],
        "name": g(x, "name") or g(x, "username") or g(x, "email"),
        "phone": g(x, "phone"), "country": g(x, "country"),
        "amount": x["amount"], "wallet": x["wallet"],
        "network": g(x, "usdt_network") or "TRC20",
        "invited": x["invited"], "status": x["status"],
        "created_at": x["created_at"], "paid_at": x["paid_at"],
    } for x in rows]}


class WdAction(BaseModel):
    action: str          # paid · rejected


@router.post("/withdrawals/{wid}")
def admin_withdrawal_action(wid: str, body: WdAction,
                            user=Depends(require_admin)):
    """⚠️ لا إرسال آلي — تُرسل أنت من محفظتك ثم تُعلّم الطلب."""
    if body.action not in ("paid", "rejected"):
        raise HTTPException(400, "إجراء غير معروف")
    import sqlite3, time as _t
    cn = sqlite3.connect("/opt/whalex/db/whalex.db")
    n = cn.execute(
        "UPDATE referral_withdrawals SET status=?, paid_at=? "
        "WHERE id=? AND status='pending'",
        (body.action, int(_t.time()) if body.action == "paid" else None, wid)
    ).rowcount
    cn.commit()
    cn.close()
    if not n:
        raise HTTPException(404, "الطلب غير موجود أو عولج سابقاً")
    return {"success": True, "status": body.action}
