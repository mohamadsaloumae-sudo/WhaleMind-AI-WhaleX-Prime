"""🔐☀️ API محفظة سولانا الشخصية — إنشاء/رصيد/إعدادات (مالك النظام فقط)"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from routers.auth import get_current_user
import services.sol_wallet as W

router = APIRouter(prefix="/api/memewallet", tags=["MemeWallet"])


def _admin_only(user):
    """🛡️ محفظة شخصية — للمالك فقط."""
    tier = (user or {}).get("tier") or (user or {}).get("subscription_tier") or ""
    if str(tier).lower() != "admin":
        raise HTTPException(403, "متاح للمالك فقط")
    return user


class ConfigBody(BaseModel):
    enabled: int | None = None
    per_trade_sol: float | None = None
    daily_max_sol: float | None = None
    max_concurrent: int | None = None
    slippage_bps: int | None = None


@router.get("/status")
async def status(user=Depends(get_current_user)):
    _admin_only(user)
    cfg = W.get_config()
    out = {
        "exists": W.wallet_exists(),
        "config": cfg,
        "caps": {"per_trade": W.HARD_MAX_PER_TRADE, "daily": W.HARD_MAX_DAILY,
                 "concurrent": W.HARD_MAX_CONCURRENT},
        "spent_today": W.spent_today(),
        "open_positions": W.open_positions_count(),
        "pubkey": None, "sol": 0.0,
    }
    if out["exists"]:
        try:
            b = await W.get_balance()
            out["pubkey"] = b["pubkey"]
            out["sol"] = b["sol"]
        except Exception as e:
            out["error"] = str(e)
    return out


@router.post("/create")
async def create(user=Depends(get_current_user)):
    """ينشئ محفظة جديدة. المفتاح الخاص يُعرض مرّة واحدة فقط."""
    _admin_only(user)
    if W.wallet_exists():
        raise HTTPException(400, "محفظة موجودة بالفعل")
    r = W.create_wallet()
    return {"success": True, "pubkey": r["pubkey"], "secret_b58": r["secret_b58"],
            "warning": "احفظ المفتاح الآن — لن يُعرض مرّة أخرى"}


@router.post("/config")
async def set_cfg(body: ConfigBody, user=Depends(get_current_user)):
    _admin_only(user)
    kw = {k: v for k, v in body.model_dump().items() if v is not None}
    if not kw:
        raise HTTPException(400, "لا قيم")
    return {"success": True, "config": W.set_config(**kw)}


@router.get("/trades")
async def trades(user=Depends(get_current_user), limit: int = 30):
    _admin_only(user)
    import sqlite3
    W._db_init()
    cn = sqlite3.connect(W.WALLET_DB); cn.row_factory = sqlite3.Row
    rows = [dict(r) for r in cn.execute(
        "SELECT * FROM wallet_trades ORDER BY ts DESC LIMIT ?", (min(limit, 100),))]
    cn.close()
    return {"trades": rows}
