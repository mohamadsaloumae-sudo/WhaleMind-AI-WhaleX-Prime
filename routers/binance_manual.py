"""
WhaleMind Binance — Manual Trading Endpoints
═══════════════════════════════════════════════════════════════════
المستخدم يتداول يدوياً بأي عملة، بدون انتظار إشارات الرادار

Endpoints:
POST /api/binance/manual/open      — فتح صفقة (يدوية)
POST /api/binance/manual/close     — إغلاق صفقة
POST /api/binance/manual/modify-sl — تعديل SL
POST /api/binance/manual/modify-tp — تعديل TP
GET  /api/binance/symbols          — قائمة العملات + الأسعار
GET  /api/binance/price/{symbol}   — سعر عملة معينة
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
import logging
import httpx

from routers.auth import get_current_user
from services.binance_trader import get_client, get_credentials

log = logging.getLogger("binance_manual")

router = APIRouter(prefix="/api/binance/manual", tags=["Binance Manual"])


# ═══════════════════════════════════════════════════════════════
# ─── REQUEST MODELS ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

class ManualOpenBody(BaseModel):
    symbol: str = Field(..., min_length=3, max_length=20)
    direction: Literal["LONG", "SHORT"]
    market_type: Literal["spot", "futures"] = "futures"
    amount_usdt: float = Field(..., gt=0, le=100000)
    leverage: int = Field(default=5, ge=1, le=125)
    
    # اختيارية — اذا كانت موجودة، نضع SL/TP تلقائياً
    sl_price: Optional[float] = None
    tp_prices: Optional[list[float]] = None  # [tp1, tp2, tp3]
    
    # نوع الأمر
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    limit_price: Optional[float] = None


class ManualCloseBody(BaseModel):
    symbol: str
    market_type: Literal["spot", "futures"] = "futures"
    # اختياري: إذا قُدّم، إغلاق جزئي
    percentage: Optional[float] = Field(default=100, ge=1, le=100)


class ModifySLBody(BaseModel):
    symbol: str
    new_sl_price: float = Field(..., gt=0)


class ModifyTPBody(BaseModel):
    symbol: str
    new_tp_prices: list[float] = Field(..., min_length=1, max_length=3)


# ═══════════════════════════════════════════════════════════════
# ─── ENDPOINTS ────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

@router.post("/open")
async def manual_open(body: ManualOpenBody, user=Depends(get_current_user)):
    """فتح صفقة يدوية"""
    uid = user["sub"]
    client = get_client(uid)
    if not client:
        raise HTTPException(status_code=404, detail="not_connected")
    
    symbol = body.symbol.upper()
    side = "BUY" if body.direction == "LONG" else "SELL"
    
    try:
        if body.market_type == "futures":
            # 1. ضبط الرافعة
            client.futures_change_leverage(symbol=symbol, leverage=body.leverage)
            
            # 2. حساب الكمية
            ticker = client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker["price"])
            entry_price = body.limit_price if body.order_type == "LIMIT" else current_price
            quantity = round((body.amount_usdt * body.leverage) / entry_price, 3)
            
            # 3. فتح الصفقة
            order_params = {
                "symbol": symbol,
                "side": side,
                "type": body.order_type,
                "quantity": quantity,
            }
            if body.order_type == "LIMIT":
                order_params["price"] = body.limit_price
                order_params["timeInForce"] = "GTC"
            
            order = client.futures_create_order(**order_params)
            order_id = order["orderId"]
            
            # 4. وضع SL إذا قُدّم
            sl_side = "SELL" if body.direction == "LONG" else "BUY"
            if body.sl_price:
                try:
                    client.futures_create_order(
                        symbol=symbol,
                        side=sl_side,
                        type="STOP_MARKET",
                        stopPrice=body.sl_price,
                        closePosition=True,
                    )
                except Exception as e:
                    log.warning("SL error: %s", e)
            
            # 5. وضع TPs
            if body.tp_prices:
                tp_qty = round(quantity / len(body.tp_prices), 3)
                for tp_price in body.tp_prices:
                    try:
                        client.futures_create_order(
                            symbol=symbol,
                            side=sl_side,
                            type="TAKE_PROFIT_MARKET",
                            stopPrice=tp_price,
                            quantity=tp_qty,
                        )
                    except Exception as e:
                        log.warning("TP error: %s", e)
            
            log.info("✅ Manual trade: %s %s %s qty=%s lev=%dx (user %s)",
                     symbol, body.direction, body.order_type,
                     quantity, body.leverage, uid)
            
            return {
                "success": True,
                "order_id": str(order_id),
                "symbol": symbol,
                "direction": body.direction,
                "quantity": quantity,
                "entry_price": entry_price,
                "leverage": body.leverage,
                "market_type": body.market_type,
            }
        else:
            # Spot
            ticker = client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker["price"])
            entry_price = body.limit_price if body.order_type == "LIMIT" else current_price
            
            order_params = {
                "symbol": symbol,
                "side": side,
                "type": body.order_type,
                "quoteOrderQty": body.amount_usdt,
            }
            if body.order_type == "LIMIT":
                order_params["price"] = str(body.limit_price)
                order_params["timeInForce"] = "GTC"
                # spot LIMIT needs quantity, not quoteOrderQty
                order_params.pop("quoteOrderQty", None)
                order_params["quantity"] = round(body.amount_usdt / body.limit_price, 6)
            
            order = client.create_order(**order_params)
            
            log.info("✅ Spot manual: %s %s (user %s)", symbol, side, uid)
            return {
                "success": True,
                "order_id": str(order.get("orderId")),
                "symbol": symbol,
                "direction": body.direction,
                "market_type": "spot",
            }
    
    except Exception as e:
        log.error("manual_open error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/close")
async def manual_close(body: ManualCloseBody, user=Depends(get_current_user)):
    """إغلاق صفقة (كامل أو جزئي)"""
    uid = user["sub"]
    client = get_client(uid)
    if not client:
        raise HTTPException(status_code=404, detail="not_connected")
    
    symbol = body.symbol.upper()
    
    try:
        if body.market_type == "futures":
            # نجلب الصفقة الحالية
            positions = client.futures_position_information(symbol=symbol)
            pos = next((p for p in positions if float(p["positionAmt"]) != 0), None)
            if not pos:
                raise HTTPException(status_code=404, detail="position_not_found")
            
            amt = float(pos["positionAmt"])
            qty_to_close = round(abs(amt) * (body.percentage / 100), 3)
            close_side = "SELL" if amt > 0 else "BUY"
            
            # إلغاء أي SL/TP موجود (لو إغلاق كامل)
            if body.percentage == 100:
                try:
                    client.futures_cancel_all_open_orders(symbol=symbol)
                except Exception:
                    pass
            
            order = client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type="MARKET",
                quantity=qty_to_close,
                reduceOnly=True,
            )
            
            log.info("✅ Close %d%%: %s qty=%s (user %s)",
                     int(body.percentage), symbol, qty_to_close, uid)
            
            return {
                "success": True,
                "order_id": str(order["orderId"]),
                "symbol": symbol,
                "closed_quantity": qty_to_close,
                "closed_percentage": body.percentage,
            }
        else:
            raise HTTPException(status_code=400, detail="spot_close_use_sell")
    
    except HTTPException:
        raise
    except Exception as e:
        log.error("manual_close error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/modify-sl")
async def modify_sl(body: ModifySLBody, user=Depends(get_current_user)):
    """تعديل SL لصفقة مفتوحة"""
    uid = user["sub"]
    client = get_client(uid)
    if not client:
        raise HTTPException(status_code=404, detail="not_connected")
    
    symbol = body.symbol.upper()
    
    try:
        # نجلب الصفقة
        positions = client.futures_position_information(symbol=symbol)
        pos = next((p for p in positions if float(p["positionAmt"]) != 0), None)
        if not pos:
            raise HTTPException(status_code=404, detail="position_not_found")
        
        amt = float(pos["positionAmt"])
        sl_side = "SELL" if amt > 0 else "BUY"
        
        # إلغاء SL القديم
        orders = client.futures_get_open_orders(symbol=symbol)
        for o in orders:
            if o["type"] == "STOP_MARKET":
                client.futures_cancel_order(symbol=symbol, orderId=o["orderId"])
        
        # وضع SL جديد
        new_order = client.futures_create_order(
            symbol=symbol,
            side=sl_side,
            type="STOP_MARKET",
            stopPrice=body.new_sl_price,
            closePosition=True,
        )
        
        return {
            "success": True,
            "symbol": symbol,
            "new_sl_price": body.new_sl_price,
            "order_id": str(new_order["orderId"]),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log.error("modify_sl error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/modify-tp")
async def modify_tp(body: ModifyTPBody, user=Depends(get_current_user)):
    """تعديل TPs لصفقة مفتوحة"""
    uid = user["sub"]
    client = get_client(uid)
    if not client:
        raise HTTPException(status_code=404, detail="not_connected")
    
    symbol = body.symbol.upper()
    
    try:
        positions = client.futures_position_information(symbol=symbol)
        pos = next((p for p in positions if float(p["positionAmt"]) != 0), None)
        if not pos:
            raise HTTPException(status_code=404, detail="position_not_found")
        
        amt = float(pos["positionAmt"])
        tp_side = "SELL" if amt > 0 else "BUY"
        qty = abs(amt)
        
        # إلغاء TPs القديمة
        orders = client.futures_get_open_orders(symbol=symbol)
        for o in orders:
            if o["type"] == "TAKE_PROFIT_MARKET":
                client.futures_cancel_order(symbol=symbol, orderId=o["orderId"])
        
        # وضع TPs جديدة
        tp_qty = round(qty / len(body.new_tp_prices), 3)
        new_orders = []
        for tp_price in body.new_tp_prices:
            o = client.futures_create_order(
                symbol=symbol,
                side=tp_side,
                type="TAKE_PROFIT_MARKET",
                stopPrice=tp_price,
                quantity=tp_qty,
            )
            new_orders.append(str(o["orderId"]))
        
        return {
            "success": True,
            "symbol": symbol,
            "new_tp_prices": body.new_tp_prices,
            "order_ids": new_orders,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log.error("modify_tp error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/symbols")
async def get_symbols(market_type: str = "futures"):
    """قائمة العملات + الأسعار الحالية (Public — لا حاجة لـ auth)"""
    try:
        base_url = "https://fapi.binance.com" if market_type == "futures" else "https://api.binance.com"
        endpoint = "/fapi/v1/ticker/24hr" if market_type == "futures" else "/api/v3/ticker/24hr"
        
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{base_url}{endpoint}")
        
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail="binance_unavailable")
        
        data = r.json()
        # نفلتر USDT فقط ونرتب حسب الحجم
        usdt_only = [
            {
                "symbol": t["symbol"],
                "price": float(t["lastPrice"]),
                "change_24h": float(t["priceChangePercent"]),
                "volume_24h": float(t["quoteVolume"]),
            }
            for t in data
            if t["symbol"].endswith("USDT")
        ]
        usdt_only.sort(key=lambda x: x["volume_24h"], reverse=True)
        return {"symbols": usdt_only[:200]}  # أعلى 200
    
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_symbols error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/price/{symbol}")
async def get_price(symbol: str, market_type: str = "futures"):
    """سعر عملة معينة"""
    try:
        base_url = "https://fapi.binance.com" if market_type == "futures" else "https://api.binance.com"
        endpoint = "/fapi/v1/ticker/price" if market_type == "futures" else "/api/v3/ticker/price"
        
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{base_url}{endpoint}", params={"symbol": symbol.upper()})
        
        if r.status_code != 200:
            raise HTTPException(status_code=404, detail="symbol_not_found")
        
        return r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
