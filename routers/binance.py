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
    exchange: str = "binance"        # 🔌 اختياري — باينانس افتراضياً
    passphrase: str = ""             # 🔑 لأوكي إكس وبيتجت فقط


class ConnectBody(BaseModel):
    api_key: str = Field(..., min_length=10)
    api_secret: str = Field(..., min_length=10)
    is_testnet: bool = True
    account_type: str = Field(default="futures", pattern="^(spot|futures|both)$")
    exchange: str = "binance"        # 🔌 اختياري — باينانس افتراضياً
    passphrase: str = ""             # 🔑 لأوكي إكس وبيتجت فقط


class AutoTradeBody(BaseModel):
    enabled: Optional[bool] = None
    trade_amount_usdt: Optional[float] = Field(None, ge=1, le=10000)
    max_open_positions: Optional[int] = Field(None, ge=1, le=10)
    allowed_grades: Optional[str] = Field(None, pattern="^[ASB,]+$")
    leverage: Optional[int] = Field(None, ge=1, le=125)
    spot_enabled: bool | None = None
    spot_trade_amount: float | None = None
    spot_max_positions: int | None = None


# ═══════════════════════════════════════════════════════════════
# ─── ENDPOINTS ────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

@router.get("/exchanges")
async def exchanges():
    """🔌 المنصّات المدعومة — للواجهة.
    إضافة منصّة في services/exchanges/ تظهر هنا تلقائياً.
    """
    from services.exchanges import list_exchanges
    return {"success": True, "exchanges": list_exchanges()}


@router.post("/test")
async def test_keys(body: TestBody, user=Depends(get_current_user)):
    """
    يختبر مفاتيح API قبل الحفظ
    - يرفض إذا فيه صلاحية Withdraw
    - يتحقق من صلاحيات Trade
    """
    _ex = (body.exchange or "binance").lower()
    if _ex == "binance":
        # 🔒 مسار باينانس المُثبت لا يُمسّ
        return await test_connection(body.api_key, body.api_secret, body.is_testnet)
    # 🔌 المنصّات الأخرى عبر المُهايئ المعزول
    import asyncio
    from services.exchanges import get as _get_ex
    _ad = _get_ex(_ex)
    _r = await asyncio.to_thread(_ad.test, body.api_key, body.api_secret,
                                 body.passphrase)
    if _r.get("ok"):
        return {"success": True, "exchange": _r.get("exchange"),
                "usdt_balance": _r.get("usdt", 0),
                "message": f"تم الاتصال بـ{_r.get('exchange')}"}
    return {"success": False, "error": _r.get("error", "فشل الاتصال")}


@router.post("/connect")
async def connect(body: ConnectBody, user=Depends(get_current_user)):
    """
    يربط المستخدم بـ Binance (يحفظ المفاتيح مشفّرة)
    يختبر أولاً ثم يحفظ
    """
    # 1. اختبار
    _ex = (body.exchange or "binance").lower()
    if _ex == "binance":
        test = await test_connection(body.api_key, body.api_secret, body.is_testnet)
    else:
        import asyncio as _aio
        from services.exchanges import get as _gx
        _rr = await _aio.to_thread(_gx(_ex).test, body.api_key,
                                   body.api_secret, body.passphrase)
        test = ({"success": True, "permissions": {"exchange": _rr.get("exchange")}}
                if _rr.get("ok") else {"success": False, "error": _rr.get("error")})
    if not test.get("success"):
        raise HTTPException(status_code=400, detail=test.get("error", "فشل الاتصال"))
    
    # 2. حفظ
    uid = user["sub"]
    ok = save_credentials(
        user_id=uid,
        api_key=body.api_key,
        api_secret=body.api_secret,
        is_testnet=body.is_testnet,
        account_type=body.account_type,
        exchange=body.exchange,
        passphrase=body.passphrase,
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


@router.get("/accounts")
async def accounts(user=Depends(get_current_user)):
    """🔌 كل حسابات المستخدم المربوطة — حساب لكل منصّة.
    يمكّنه من ربط 7 حسابات وأخذ كل الإشارات على منصّاتها.
    """
    from services.binance_trader import get_user_exchanges
    from services.exchanges import REGISTRY
    rows = get_user_exchanges(user["sub"])
    out = []
    for r in rows:
        ex = (r.get("exchange") or "binance").lower()
        ad = REGISTRY.get(ex)
        out.append({
            "exchange": ex,
            "name_ar": ad.name_ar if ad else ex,
            "name_en": ad.name_en if ad else ex,
            "auto_trade_enabled": bool(r.get("auto_trade_enabled")),
            "trade_amount_usdt": r.get("trade_amount_usdt"),
            "max_open_positions": r.get("max_open_positions"),
            "account_type": r.get("account_type"),
        })
    return {"success": True, "accounts": out, "count": len(out)}


@router.delete("/disconnect/{exchange}")
async def disconnect_one(exchange: str, user=Depends(get_current_user)):
    """يفصل منصّة بعينها — الباقي يبقى مربوطاً."""
    import sqlite3
    from services.binance_trader import DB_PATH
    try:
        cn = sqlite3.connect(DB_PATH)
        n = cn.execute("DELETE FROM user_binance_credentials WHERE user_id=? AND exchange=?",
                       (str(user["sub"]), exchange.lower())).rowcount
        cn.commit(); cn.close()
        if not n:
            raise HTTPException(status_code=404, detail="لا حساب على هذه المنصّة")
        log.info("🔌 User %s disconnected %s", user["sub"], exchange)
        return {"success": True, "exchange": exchange}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:120])


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
        "spot_auto_enabled": creds.get("spot_auto_enabled", 0),
        "spot_trade_amount": creds.get("spot_trade_amount", 5),
        "spot_max_positions": creds.get("spot_max_positions", 0),
        "trade_amount_usdt": creds["trade_amount_usdt"],
        "max_open_positions": creds["max_open_positions"],
        "allowed_grades": creds["allowed_grades"],
        "leverage": creds.get("leverage"),
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
    
    try:
        return {"positions": get_open_positions(uid)}
    except Exception as _pe:
        raise HTTPException(status_code=503, detail="تعذّر جلب المراكز")


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
        allowed_grades=body.allowed_grades,
        leverage=body.leverage,
        spot_enabled=body.spot_enabled,
        spot_trade_amount=body.spot_trade_amount,
        spot_max_positions=body.spot_max_positions
    )
    if not ok:
        raise HTTPException(status_code=500, detail="update_failed")
    
    # نُرجع الإعدادات المُحدّثة
    creds = get_credentials(uid)
    return {
        "success": True,
        "auto_trade_enabled": creds["auto_trade_enabled"],
        "spot_auto_enabled": creds.get("spot_auto_enabled", 0),
        "spot_trade_amount": creds.get("spot_trade_amount", 5),
        "spot_max_positions": creds.get("spot_max_positions", 0),
        "trade_amount_usdt": creds["trade_amount_usdt"],
        "max_open_positions": creds["max_open_positions"],
        "allowed_grades": creds["allowed_grades"],
        "leverage": creds.get("leverage"),
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
        "spot_auto_enabled": creds.get("spot_auto_enabled", 0),
        "spot_trade_amount": creds.get("spot_trade_amount", 5),
        "spot_max_positions": creds.get("spot_max_positions", 0),
        "trade_amount_usdt": creds["trade_amount_usdt"],
        "max_open_positions": creds["max_open_positions"],
        "allowed_grades": creds["allowed_grades"],
        "leverage": creds.get("leverage"),
    }
