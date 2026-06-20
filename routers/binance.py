"""
WhaleMind Binance Router
═══════════════════════════════════════════════════════════════════
API endpoints لإدارة ربط Binance من الميني آب

Endpoints:
POST   /api/binance/test           — اختبار مفاتيح قبل الحفظ
POST   /api/binance/connect        — حفظ المفاتيح مشفّرة
DELETE /api/binance/disconnect     — قطع الاتصال
GET    /api/binance/status         — هل المستخدم مربوط؟
GET    /api/binance/balance        — الرصيد الحقيقي
GET    /api/binance/positions      — الصفقات المفتوحة
POST   /api/binance/auto-trade     — تفعيل/إيقاف + إعدادات
GET    /api/binance/settings       — الإعدادات الحالية
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import logging

from routers.auth import get_current_user
from services.binance_trader import (
    test_connection,
    save_credentials,
    get_credentials,
    delete_credentials,
    update_auto_trade_settings,
    get_balance,
    get_open_positions,
)

log = logging.getLogger("binance_router")

router = APIRouter(prefix="/api/binance", tags=["Binance"])


# ═══════════════════════════════════════════════════════════════
# ─── REQUEST MODELS ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

class TestBody(BaseModel):
    api_key: str = Field(..., min_length=10)
    api_secret: str = Field(..., min_length=10)
    is_testnet: bool = True


class ConnectBody(BaseModel):
    api_key: str = Field(..., min_length=10)
    api_secret: str = Field(..., min_length=10)
    is_testnet: bool = True
    account_type: str = Field(default="futures", pattern="^(spot|futures|both)$")


class AutoTradeBody(BaseModel):
    enabled: Optional[bool] = None
    trade_amount_usdt: Optional[float] = Field(None, ge=10, le=10000)
    max_open_positions: Optional[int] = Field(None, ge=1, le=10)
    allowed_grades: Optional[str] = Field(None, pattern="^[ASB,]+$")


# ═══════════════════════════════════════════════════════════════
# ─── ENDPOINTS ────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

@router.post("/test")
async def test_keys(body: TestBody, user=Depends(get_current_user)):
    """
    يختبر مفاتيح API قبل الحفظ
    - يرفض إذا فيه صلاحية Withdraw
    - يتحقق من صلاحيات Trade
    """
    result = await test_connection(body.api_key, body.api_secret, body.is_testnet)
    return result


@router.post("/connect")
async def connect(body: ConnectBody, user=Depends(get_current_user)):
    """
    يربط المستخدم بـ Binance (يحفظ المفاتيح مشفّرة)
    يختبر أولاً ثم يحفظ
    """
    # 1. اختبار
    test = await test_connection(body.api_key, body.api_secret, body.is_testnet)
    if not test.get("success"):
        raise HTTPException(status_code=400, detail=test.get("error", "فشل الاتصال"))
    
    # 2. حفظ
    uid = user["sub"]
    ok = save_credentials(
        user_id=uid,
        api_key=body.api_key,
        api_secret=body.api_secret,
        is_testnet=body.is_testnet,
        account_type=body.account_type
    )
    
    if not ok:
        raise HTTPException(status_code=500, detail="فشل حفظ المفاتيح")
    
    log.info("✅ User %s connected to Binance (testnet=%s)", uid, body.is_testnet)
    
    return {
        "success": True,
        "message": "تم الربط بنجاح",
        "permissions": test.get("permissions"),
        "is_testnet": body.is_testnet,
    }


@router.delete("/disconnect")
async def disconnect(user=Depends(get_current_user)):
    """يقطع ربط المستخدم بـ Binance (يحذف المفاتيح)"""
    uid = user["sub"]
    ok = delete_credentials(uid)
    if not ok:
        raise HTTPException(status_code=500, detail="فشل قطع الاتصال")
    return {"success": True, "message": "تم قطع الاتصال"}


@router.get("/status")
async def status(user=Depends(get_current_user)):
    """يتحقق هل المستخدم مربوط"""
    uid = user["sub"]
    creds = get_credentials(uid)
    if not creds:
        return {"connected": False}
    
    # لا نُرجع المفاتيح نفسها، فقط الحالة
    return {
        "connected": True,
        "is_testnet": creds["is_testnet"],
        "account_type": creds["account_type"],
        "auto_trade_enabled": creds["auto_trade_enabled"],
        "trade_amount_usdt": creds["trade_amount_usdt"],
        "max_open_positions": creds["max_open_positions"],
        "allowed_grades": creds["allowed_grades"],
    }


@router.get("/balance")
async def balance(user=Depends(get_current_user)):
    """رصيد المستخدم الحقيقي"""
    uid = user["sub"]
    creds = get_credentials(uid)
    if not creds:
        raise HTTPException(status_code=404, detail="not_connected")
    
    return get_balance(uid)


@router.get("/positions")
async def positions(user=Depends(get_current_user)):
    """الصفقات المفتوحة"""
    uid = user["sub"]
    creds = get_credentials(uid)
    if not creds:
        raise HTTPException(status_code=404, detail="not_connected")
    
    return {"positions": get_open_positions(uid)}


@router.post("/auto-trade")
async def auto_trade(body: AutoTradeBody, user=Depends(get_current_user)):
    """تفعيل/إيقاف Auto-Trade + الإعدادات"""
    uid = user["sub"]
    creds = get_credentials(uid)
    if not creds:
        raise HTTPException(status_code=404, detail="not_connected")
    
    ok = update_auto_trade_settings(
        user_id=uid,
        enabled=body.enabled,
        trade_amount=body.trade_amount_usdt,
        max_positions=body.max_open_positions,
        allowed_grades=body.allowed_grades
    )
    if not ok:
        raise HTTPException(status_code=500, detail="update_failed")
    
    # نُرجع الإعدادات المُحدّثة
    creds = get_credentials(uid)
    return {
        "success": True,
        "auto_trade_enabled": creds["auto_trade_enabled"],
        "trade_amount_usdt": creds["trade_amount_usdt"],
        "max_open_positions": creds["max_open_positions"],
        "allowed_grades": creds["allowed_grades"],
    }


@router.get("/settings")
async def settings(user=Depends(get_current_user)):
    """الإعدادات الحالية"""
    uid = user["sub"]
    creds = get_credentials(uid)
    if not creds:
        return {"connected": False}
    return {
        "connected": True,
        "is_testnet": creds["is_testnet"],
        "auto_trade_enabled": creds["auto_trade_enabled"],
        "trade_amount_usdt": creds["trade_amount_usdt"],
        "max_open_positions": creds["max_open_positions"],
        "allowed_grades": creds["allowed_grades"],
    }
