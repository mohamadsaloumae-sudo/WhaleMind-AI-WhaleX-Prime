from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError
from db.database import get_session, User, hash_password, verify_password
from core.config import get_settings
import uuid, secrets, time

router = APIRouter(prefix="/api/auth", tags=["Auth"])
security = HTTPBearer(auto_error=False)

def create_token(user_id: str, tier: str) -> str:
    s = get_settings()
    payload = {"sub": user_id, "tier": tier, "exp": datetime.utcnow() + timedelta(days=30)}
    return jwt.encode(payload, s.secret_key, algorithm="HS256")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(401, "Not authenticated")
    s = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, s.secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(401, "Invalid token")

def require_pro(user=Depends(get_current_user)):
    if user.get("tier") not in ("pro", "admin"):
        raise HTTPException(403, "PRO subscription required")
    return user

def require_admin(user=Depends(get_current_user)):
    if user.get("tier") != "admin":
        raise HTTPException(403, "Admin access required")
    return user

class RegisterBody(BaseModel):
    username: str
    password: str
    email: str = ""

class LoginBody(BaseModel):
    username: str
    password: str

@router.post("/register")
def register(body: RegisterBody):
    db = get_session()
    try:
        if db.query(User).filter(User.username == body.username).first():
            raise HTTPException(400, "Username already exists")
        user = User(
            username=body.username,
            email=body.email or None,
            password_hash=hash_password(body.password),
            tier="free",
        )
        code = "WX-" + secrets.token_hex(3).upper()
        user.tg_link_code = code
        db.add(user); db.commit(); db.refresh(user)
        return {"needs_link": True, "link_code": code, "uid": user.id,
                "bot": "WMAI2026BOT",
                "instructions": f"أرسل هذا للبوت: /link {code}"}
    finally:
        db.close()

@router.post("/login")
def login(body: LoginBody):
    db = get_session()
    try:
        user = db.query(User).filter(User.username == body.username).first()
        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(401, "Invalid credentials")
        token = create_token(user.id, user.tier)
        return {"access_token": token, "tier": user.tier, "uid": user.id, "username": user.username}
    finally:
        db.close()

@router.post("/guest")
def guest():
    uid = str(uuid.uuid4())
    token = create_token(uid, "free")
    return {"access_token": token, "tier": "free", "uid": uid}

@router.get("/me")
def me(user=Depends(get_current_user)):
    db = get_session()
    try:
        u = db.query(User).filter(User.id == user["sub"]).first()
        if not u:
            return {"uid": user["sub"], "tier": user["tier"], "username": "Guest"}
        return {"uid": u.id, "tier": u.tier, "username": u.username, "demo_balance": u.demo_balance}
    finally:
        db.close()

@router.post("/link-code")
def link_code(user=Depends(get_current_user)):
    """يولّد رمز ربط تيليجرام للمستخدم المسجّل. صالح 10 دقائق."""
    db = get_session()
    try:
        u = db.query(User).filter(User.id == user["sub"]).first()
        if not u:
            raise HTTPException(404, "المستخدم غير موجود")
        code = "WX-" + secrets.token_hex(3).upper()
        u.tg_link_code = code
        db.commit()
        return {"link_code": code, "instructions": f"أرسل هذا للبوت: /link {code}"}
    finally:
        db.close()

class ForgotBody(BaseModel):
    username: str

@router.post("/forgot")
async def forgot_password(body: ForgotBody):
    """يولّد رمز استرجاع 6 أرقام ويرسله عبر تيليجرام. صالح 15 دقيقة."""
    db = get_session()
    try:
        u = db.query(User).filter(User.username == body.username).first()
        if not u:
            return {"ok": True, "sent": False, "reason": "إن كان الحساب موجوداً، سيصلك رمز"}
        if not u.tg_chat_id:
            return {"ok": False, "sent": False, "reason": "الحساب غير مربوط بتيليجرام. اربطه أولاً من الإعدادات."}
        code = str(secrets.randbelow(900000) + 100000)
        u.reset_code = code
        u.reset_expires = int(time.time()) + 900
        db.commit()
        chat_id = u.tg_chat_id
        uname = u.username
    finally:
        db.close()
    try:
        from services.telegram import send_message
        await send_message(chat_id,
            f"🔐 <b>استرجاع كلمة السر</b>\n\n"
            f"الحساب: <b>{uname}</b>\n"
            f"رمز الاسترجاع: <code>{code}</code>\n\n"
            f"⏱ صالح 15 دقيقة. لا تشاركه مع أحد.")
    except Exception as _e:
        return {"ok": False, "sent": False, "reason": "تعذّر إرسال الرمز"}
    return {"ok": True, "sent": True, "reason": "تم إرسال الرمز عبر تيليجرام"}

class ResetBody(BaseModel):
    username: str
    code: str
    new_password: str

@router.post("/reset-password")
def reset_password(body: ResetBody):
    """يتحقق من الرمز ويحدّث كلمة السر."""
    db = get_session()
    try:
        u = db.query(User).filter(User.username == body.username).first()
        if not u or not u.reset_code:
            raise HTTPException(400, "لا يوجد طلب استرجاع لهذا الحساب")
        if int(time.time()) > (u.reset_expires or 0):
            raise HTTPException(400, "انتهت صلاحية الرمز. اطلب رمزاً جديداً.")
        if body.code.strip() != u.reset_code:
            raise HTTPException(400, "الرمز غير صحيح")
        if len(body.new_password) < 6:
            raise HTTPException(400, "كلمة السر يجب أن تكون 6 أحرف على الأقل")
        u.password_hash = hash_password(body.new_password)
        u.reset_code = None
        u.reset_expires = None
        db.commit()
        return {"ok": True, "message": "تم تحديث كلمة السر بنجاح"}
    finally:
        db.close()

class LinkStatusBody(BaseModel):
    username: str

@router.post("/link-status")
def link_status(body: LinkStatusBody):
    """يتحقق هل الحساب ربط تيليجرام. إن نعم، يُرجع token للدخول."""
    db = get_session()
    try:
        u = db.query(User).filter(User.username == body.username).first()
        if not u:
            raise HTTPException(404, "المستخدم غير موجود")
        if u.tg_chat_id:
            token = create_token(u.id, u.tier)
            return {"linked": True, "access_token": token, "tier": u.tier, "uid": u.id, "username": u.username}
        return {"linked": False}
    finally:
        db.close()

