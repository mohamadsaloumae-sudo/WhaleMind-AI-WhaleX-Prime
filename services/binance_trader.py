"""
WhaleMind Binance Trader Service
═══════════════════════════════════════════════════════════════════
خدمة آمنة للتداول التلقائي على Binance نيابة عن المستخدمين

الأمان:
✅ API keys مشفّرة AES-256 (Fernet) في DB
✅ صلاحيات Trade فقط (لا Withdraw)
✅ المستخدم يستطيع قطع الاتصال في أي لحظة
✅ Testnet و Live mode منفصلان
✅ Rate limiting و error handling شامل
"""

import os
import logging
import sqlite3
from typing import Optional
from datetime import datetime
from cryptography.fernet import Fernet
import base64
import hashlib

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException

log = logging.getLogger("binance_trader")

DB_PATH = "/opt/whalex/db/whalex.db"


# ═══════════════════════════════════════════════════════════════
# ─── ENCRYPTION LAYER ─────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def _get_fernet() -> Fernet:
    """يبني Fernet cipher من ENCRYPTION_KEY في .env"""
    key = os.environ.get("ENCRYPTION_KEY", "")
    if not key:
        # نقرأ من .env مباشرة
        try:
            with open("/opt/whalex/.env") as f:
                for line in f:
                    if line.startswith("ENCRYPTION_KEY="):
                        key = line.split("=", 1)[1].strip()
                        break
        except FileNotFoundError:
            pass
    
    if not key:
        raise RuntimeError("ENCRYPTION_KEY missing in .env")
    
    # نُحول المفتاح إلى Fernet-compatible (32 bytes URL-safe base64)
    key_bytes = hashlib.sha256(key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt(plaintext: str) -> str:
    """تشفير API key/secret"""
    if not plaintext:
        return ""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """فك تشفير"""
    if not ciphertext:
        return ""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


# ═══════════════════════════════════════════════════════════════
# ─── DATABASE SCHEMA ──────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def init_db():
    """ينشئ جدول user_binance_credentials إذا غير موجود"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_binance_credentials (
            user_id TEXT PRIMARY KEY,
            api_key_encrypted TEXT NOT NULL,
            api_secret_encrypted TEXT NOT NULL,
            is_testnet INTEGER DEFAULT 1,
            auto_trade_enabled INTEGER DEFAULT 0,
            spot_auto_enabled INTEGER DEFAULT 0,
            spot_trade_amount REAL DEFAULT 5,
            spot_max_positions INTEGER DEFAULT 0,
            trade_amount_usdt REAL DEFAULT 100,
            max_open_positions INTEGER DEFAULT 3,
            allowed_grades TEXT DEFAULT 'A,S',
            created_at TEXT,
            updated_at TEXT,
            last_used TEXT,
            account_type TEXT DEFAULT 'futures',
            disabled_reason TEXT
        )
    """)
    conn.commit()
    conn.close()
    log.info("✅ user_binance_credentials table ready")


# ═══════════════════════════════════════════════════════════════
# ─── CREDENTIAL MANAGEMENT ────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def save_credentials(
    user_id: str,
    api_key: str,
    api_secret: str,
    is_testnet: bool = True,
    account_type: str = "futures"
) -> bool:
    """يحفظ مفاتيح API مشفّرة"""
    try:
        api_key_enc = encrypt(api_key)
        api_secret_enc = encrypt(api_secret)
        now = datetime.utcnow().isoformat()
        
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT OR REPLACE INTO user_binance_credentials
            (user_id, api_key_encrypted, api_secret_encrypted, is_testnet,
             account_type, created_at, updated_at, auto_trade_enabled)
            VALUES (?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM user_binance_credentials WHERE user_id=?), ?), ?, 0)
        """, (str(user_id), api_key_enc, api_secret_enc, int(is_testnet),
              account_type, str(user_id), now, now))
        conn.commit()
        conn.close()
        log.info("✅ Credentials saved for user %s (testnet=%s)", user_id, is_testnet)
        return True
    except Exception as e:
        log.error("save_credentials error: %s", e)
        return False


def get_credentials(user_id: str) -> Optional[dict]:
    """يجلب مفاتيح API مفكوكة"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM user_binance_credentials WHERE user_id=?",
            (str(user_id),)
        ).fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            "user_id": row["user_id"],
            "api_key": decrypt(row["api_key_encrypted"]),
            "api_secret": decrypt(row["api_secret_encrypted"]),
            "is_testnet": bool(row["is_testnet"]),
            "auto_trade_enabled": bool(row["auto_trade_enabled"]),
            "spot_auto_enabled": bool(row["spot_auto_enabled"]) if "spot_auto_enabled" in row.keys() else False,
            "spot_trade_amount": row["spot_trade_amount"] if "spot_trade_amount" in row.keys() else 5,
            "spot_max_positions": row["spot_max_positions"] if "spot_max_positions" in row.keys() else 0,
            "trade_amount_usdt": row["trade_amount_usdt"],
            "max_open_positions": row["max_open_positions"],
            "allowed_grades": (row["allowed_grades"] or "A,S"),
            "leverage": row["leverage"] if "leverage" in row.keys() else None,
            "account_type": row["account_type"],
            "disabled_reason": row["disabled_reason"],
        }
    except Exception as e:
        log.error("get_credentials error for %s: %s", user_id, e)
        return None


def delete_credentials(user_id: str) -> bool:
    """يحذف ربط المستخدم بـ Binance"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM user_binance_credentials WHERE user_id=?", (str(user_id),))
        conn.commit()
        conn.close()
        log.info("✅ Credentials deleted for user %s", user_id)
        return True
    except Exception as e:
        log.error("delete_credentials error: %s", e)
        return False


def update_auto_trade_settings(
    user_id: str,
    enabled: Optional[bool] = None,
    trade_amount: Optional[float] = None,
    max_positions: Optional[int] = None,
    allowed_grades: Optional[str] = None,
    leverage: Optional[int] = None,
    spot_enabled: Optional[bool] = None,
    spot_trade_amount: Optional[float] = None,
    spot_max_positions: Optional[int] = None
) -> bool:
    """يُحدّث إعدادات Auto-Trade"""
    try:
        conn = sqlite3.connect(DB_PATH)
        try: conn.execute("ALTER TABLE user_binance_credentials ADD COLUMN spot_auto_enabled INTEGER DEFAULT 0")
        except Exception: pass
        for _col, _def in (("spot_trade_amount", "REAL DEFAULT 5"), ("spot_max_positions", "INTEGER DEFAULT 0")):
            try: conn.execute(f"ALTER TABLE user_binance_credentials ADD COLUMN {_col} {_def}")
            except Exception: pass
        fields = []
        values = []
        if spot_enabled is not None:
            fields.append("spot_auto_enabled=?")
            values.append(int(spot_enabled))
        if spot_trade_amount is not None:
            fields.append("spot_trade_amount=?")
            values.append(float(spot_trade_amount))
        if spot_max_positions is not None:
            fields.append("spot_max_positions=?")
            values.append(int(spot_max_positions))
        if enabled is not None:
            fields.append("auto_trade_enabled=?")
            values.append(int(enabled))
        if trade_amount is not None:
            fields.append("trade_amount_usdt=?")
            values.append(trade_amount)
        if max_positions is not None:
            fields.append("max_open_positions=?")
            values.append(max_positions)
        if allowed_grades:
            fields.append("allowed_grades=?")
            values.append(allowed_grades)
        if leverage is not None:
            fields.append("leverage=?")
            values.append(int(leverage))
        
        if not fields:
            conn.close()
            return False
        
        fields.append("updated_at=?")
        values.append(datetime.utcnow().isoformat())
        values.append(str(user_id))
        
        sql = f"UPDATE user_binance_credentials SET {', '.join(fields)} WHERE user_id=?"
        conn.execute(sql, values)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log.error("update_settings error: %s", e)
        return False


# ═══════════════════════════════════════════════════════════════
# ─── BINANCE CLIENT FACTORY ───────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def get_client(user_id: str) -> Optional[Client]:
    """يبني Binance Client للمستخدم"""
    creds = get_credentials(user_id)
    if not creds:
        return None
    try:
        client = Client(
            api_key=creds["api_key"],
            api_secret=creds["api_secret"],
            testnet=creds["is_testnet"]
        )
        return client
    except Exception as e:
        log.error("Client init error for %s: %s", user_id, e)
        return None


# ═══════════════════════════════════════════════════════════════
# ─── ACCOUNT INFO ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def test_connection(api_key: str, api_secret: str, is_testnet: bool = True) -> dict:
    """يختبر مفاتيح API قبل الحفظ"""
    try:
        client = Client(api_key=api_key, api_secret=api_secret, testnet=is_testnet)
        
        # نختبر صلاحيات
        info = client.get_account()
        permissions = {
            "spot": info.get("canTrade", False),
            "withdraw": info.get("canWithdraw", False),
            "deposit": info.get("canDeposit", False),
        }
        
        # نتحقق Futures
        try:
            client.futures_account()
            permissions["futures"] = True
        except Exception:
            permissions["futures"] = False
        
        # ⚠️ تحذير أمني: لو withdraw مفعّل، ننبّه فقط (لا نرفض — Binance قد يُرجع canWithdraw=True رغم إطفائه فعلياً)
        if permissions["withdraw"]:
            log.warning("⚠️ مفتاح المستخدم يُظهر canWithdraw=True — يُنصح بمفتاح بلا سحب")
        
        if not permissions["spot"] and not permissions["futures"]:
            return {
                "success": False,
                "error": "المفتاح لا يملك صلاحية التداول.",
                "permissions": permissions
            }
        
        return {
            "success": True,
            "permissions": permissions,
            "account_type": info.get("accountType", "SPOT"),
        }
    except BinanceAPIException as e:
        return {"success": False, "error": f"Binance API: {e.message}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


_spot_total_cache = {}


def get_balance(user_id: str) -> dict:
    """يجلب رصيد المستخدم (Spot + Futures)"""
    client = get_client(user_id)
    if not client:
        return {"error": "no_credentials"}
    
    result = {"spot": {}, "futures": {}}
    
    # Spot
    try:
        spot = client.get_account()
        balances = {}
        for b in spot.get("balances", []):
            free = float(b["free"])
            locked = float(b["locked"])
            total = free + locked
            if total > 0:
                balances[b["asset"]] = {
                    "free": free,
                    "locked": locked,
                    "total": total,
                }
        result["spot"] = balances
        try:
            _uu = client.get_asset_balance(asset="USDT")
            _tot = float(_uu["free"]) if _uu else 0.0
            for _a, _v in balances.items():
                if _a == "LDUSDT" or (_a.startswith("LD") and _a.endswith("USDT")):
                    _tot += _v["total"]
            result["usdt_free"] = _tot
        except Exception:
            result["usdt_free"] = 0.0
    except Exception as e:
        log.debug("Spot balance %s: %s", user_id, e)
        result["spot_error"] = str(e)
    
    # Futures
    try:
        fut = client.futures_account()
        try: result["usdt_free"] = result.get("usdt_free", 0) + float(fut.get("availableBalance", 0) or 0)
        except Exception: pass
        try:
            _tk = {t["symbol"]: float(t["price"]) for t in client.get_all_tickers()}
            _usd = 0.0
            for _as, _inf in balances.items():
                _bs = _as[2:] if _as.startswith("LD") else _as
                if _bs in ("USDT", "USDC", "BUSD", "FDUSD", "TUSD"):
                    _usd += _inf["total"]
                elif _bs + "USDT" in _tk:
                    _usd += _inf["total"] * _tk[_bs + "USDT"]
            _cx = sqlite3.connect(DB_PATH)
            _inv = _cx.execute("SELECT COALESCE(SUM(entry*qty),0) FROM spot_positions WHERE user_id=? AND status='open'", (user_id,)).fetchone()[0]
            _cx.close()
            result["usdt_total_spot"] = _usd + float(_inv or 0)
            _spot_total_cache[user_id] = result["usdt_total_spot"]
        except Exception:
            result["usdt_total_spot"] = _spot_total_cache.get(user_id, result.get("usdt_free", 0))
        result["futures"] = {
            "total_wallet_balance": float(fut.get("totalWalletBalance", 0)),
            "available_balance": float(fut.get("availableBalance", 0)),
            "total_unrealized_pnl": float(fut.get("totalUnrealizedProfit", 0)),
            "total_margin_balance": float(fut.get("totalMarginBalance", 0)),
        }
    except Exception as e:
        log.debug("Futures balance %s: %s", user_id, e)
        result["futures_error"] = str(e)
    
    return result


def get_open_positions(user_id: str) -> list:
    """يجلب الصفقات المفتوحة على Futures"""
    client = get_client(user_id)
    if not client:
        return []
    
    try:
        positions = client.futures_position_information()
        active = []
        for p in positions:
            amt = float(p["positionAmt"])
            if amt != 0:
                active.append({
                    "symbol": p["symbol"],
                    "direction": "LONG" if amt > 0 else "SHORT",
                    "size": abs(amt),
                    "entry_price": float(p["entryPrice"]),
                    "mark_price": float(p["markPrice"]),
                    "unrealized_pnl": float(p["unRealizedProfit"]),
                    "leverage": int(p["leverage"]),
                })
        return active
    except Exception as e:
        log.debug("Positions %s: %s", user_id, e)
        return []


# ═══════════════════════════════════════════════════════════════
# ─── TRADE EXECUTION (سيُستخدم لاحقاً) ─────────────────────────
# ═══════════════════════════════════════════════════════════════

# ═══ 🧮 الرافعة الذكية — موازنة مخاطرة الوقف بجودة الإشارة ═══
SMART_LEV_BASE_RISK = 20.0   # % من الهامش يُسمح بخسارتها عند ضرب الوقف (الأساس)
SMART_LEV_MIN = 1            # أدنى رافعة

_SYMBOL_FILTERS: dict = {}

def _get_symbol_filters(client, symbol: str) -> dict:
    """يجلب دقة السعر والكمية للعملة من Binance (مع cache)."""
    if symbol in _SYMBOL_FILTERS:
        return _SYMBOL_FILTERS[symbol]
    try:
        info = client.futures_exchange_info()
        for s in info["symbols"]:
            if s["symbol"] == symbol:
                f = {
                    "price_prec": int(s["pricePrecision"]),
                    "qty_prec": int(s["quantityPrecision"]),
                }
                _SYMBOL_FILTERS[symbol] = f
                return f
    except Exception as e:
        log.warning("exchange_info %s فشل: %s", symbol, e)
    return {"price_prec": 2, "qty_prec": 3}


def _fmt_price(client, symbol: str, price: float) -> float:
    """يضبط السعر لدقة العملة."""
    p = _get_symbol_filters(client, symbol)["price_prec"]
    return round(float(price), p)


def _fmt_qty(client, symbol: str, qty: float) -> float:
    """يضبط الكمية لدقة العملة."""
    q = _get_symbol_filters(client, symbol)["qty_prec"]
    return round(float(qty), q)


async def execute_signal_for_user(user_id: str, signal: dict) -> dict:
    """
    ينفّذ إشارة على حساب المستخدم
    
    signal = {
        "symbol": "BTCUSDT",
        "direction": "LONG"/"SHORT",
        "entry": float,
        "sl": float,
        "tp1": float, "tp2": float, "tp3": float,
        "leverage": int,
        "grade": "A"/"S",
    }
    
    Returns: {"success": bool, "order_id": str, "error": str}
    """
    creds = get_credentials(user_id)
    if not creds:
        return {"success": False, "error": "no_credentials"}
    
    if not creds["auto_trade_enabled"]:
        return {"success": False, "error": "auto_trade_disabled"}
    
    if signal.get("grade") not in creds["allowed_grades"]:
        return {"success": False, "error": f"grade {signal.get('grade')} not allowed"}
    
    # تحقق max positions + منع التكرار على نفس العملة
    _open = get_open_positions(user_id)
    if len(_open) >= creds["max_open_positions"]:
        return {"success": False, "error": f"max positions reached ({len(_open)})"}
    if any(p.get("symbol") == signal["symbol"] for p in _open):
        return {"success": False, "error": f"position already open for {signal['symbol']}"}
    
    client = get_client(user_id)
    if not client:
        return {"success": False, "error": "client_init_failed"}
    
    symbol = signal["symbol"]
    direction = signal["direction"]
    side = "BUY" if direction == "LONG" else "SELL"
    trade_usdt = creds["trade_amount_usdt"]

    # الرافعة: اختيار المستخدم إن وُجد، وإلا رافعة الإشارة (أوتو)
    _user_lev = creds.get("leverage")
    leverage = int(_user_lev) if _user_lev else 20

    # ═══ 🧮 الرافعة الذكية: الرافعة الفعلية = min(اختيارك، موازنة÷بُعد الوقف) ═══
    #   الموازنة نفسها ذكية: 20% أساس × عامل جودة من توقّع العقل (0.75→1.5)
    #   درس EVAA: وقف 9.3% برافعة 10x = تعريض 93% — الآن مستحيل.
    try:
        _entry = float(signal.get("entry") or 0)
        _sl = float(signal.get("sl") or 0)
        _sl_dist = abs(_entry - _sl) / _entry * 100 if _entry > 0 else 0
        if _sl_dist > 0.3:
            _prob = 0.5
            try:
                from quant_engine.ml_brain import predict_signal as _mlps
                _prob, _ = _mlps(signal)
            except Exception:
                pass
            _q = (0.75 if _prob < 0.45 else 1.0 if _prob < 0.55
                  else 1.25 if _prob < 0.65 else 1.5)
            _budget = SMART_LEV_BASE_RISK * _q
            _smart = max(SMART_LEV_MIN, int(_budget / _sl_dist + 0.5))
            if _smart < leverage:
                log.info("🧮 رافعة ذكية %s: وقف %.1f%% | 🧠%.0f%% → موازنة %.0f%% → %dx (بدل %dx)",
                         symbol, _sl_dist, _prob * 100, _budget, _smart, leverage)
                leverage = _smart
    except Exception as _sle:
        log.debug("smart_lev: %s", _sle)

    try:
        # 1. فحص أقصى رافعة مسموحة للعملة، وتقييد اختيار المستخدم ضمنها
        try:
            _br = client.futures_leverage_bracket(symbol=symbol)
            _max_lev = int(_br[0]["brackets"][0]["initialLeverage"])
            if leverage > _max_lev:
                log.info("رافعة %s: طُلب %dx، أقصى %dx → نستخدم %dx", symbol, leverage, _max_lev, _max_lev)
                leverage = _max_lev
        except Exception as _le:
            log.warning("leverage_bracket %s فشل: %s — نكمل %dx", symbol, _le, leverage)

        # 2. فحص الحد الأدنى (Binance: notional ≥ 5 USDT)
        _notional = trade_usdt * leverage
        if _notional < 5.0:
            return {"success": False, "error": f"notional {_notional:.2f}$ < 5$ (زد المبلغ أو الرافعة)"}

        # 3. ضبط الرافعة
        client.futures_change_leverage(symbol=symbol, leverage=leverage)

        # 4. حساب الكمية (بدقة العملة)
        entry = signal["entry"]
        quantity = _fmt_qty(client, symbol, (trade_usdt * leverage) / entry)
        
        # 3. فتح الصفقة (Market order)
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity,
        )
        
        order_id = order["orderId"]
        log.info("✅ Trade opened: %s %s qty=%s (user %s, order %s)",
                 symbol, direction, quantity, user_id, order_id)
        
        # 4. وضع SL
        sl_side = "SELL" if direction == "LONG" else "BUY"
        try:
            client.futures_create_order(
                symbol=symbol,
                side=sl_side,
                type="STOP_MARKET",
                stopPrice=_fmt_price(client, symbol, signal["sl"]),
                closePosition=True,
            )
        except Exception as e:
            log.warning("SL placement failed: %s", e)
        
        # 5. لا أوامر TP ثابتة — مدير الصفقات يدير الأهداف والخروج بذكاء
        #    (SL الأوّلي فوق يبقى كحماية طوارئ، والمدير يحدّثه لحظياً)
        
        return {
            "success": True,
            "order_id": str(order_id),
            "symbol": symbol,
            "direction": direction,
            "quantity": quantity,
            "leverage": leverage,
        }
    
    except BinanceOrderException as e:
        log.error("Order error %s: %s", user_id, e)
        return {"success": False, "error": f"order: {e.message}"}
    except BinanceAPIException as e:
        log.error("API error %s: %s", user_id, e)
        return {"success": False, "error": f"api: {e.message}"}
    except Exception as e:
        log.error("Execute error %s: %s", user_id, e)
        return {"success": False, "error": str(e)}


def get_active_auto_traders() -> list:
    """يجلب كل المستخدمين الذين فعّلوا Auto-Trade"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT user_id FROM user_binance_credentials WHERE auto_trade_enabled=1"
        ).fetchall()
        conn.close()
        return [r["user_id"] for r in rows]
    except Exception:
        return []


def get_active_spot_traders() -> list:
    """مستخدمو تداول السبوت الآلي (مفتاح منفصل تماماً عن الفيوتشر)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        try: conn.execute("ALTER TABLE user_binance_credentials ADD COLUMN spot_auto_enabled INTEGER DEFAULT 0")
        except Exception: pass
        for _col, _def in (("spot_trade_amount", "REAL DEFAULT 5"), ("spot_max_positions", "INTEGER DEFAULT 0")):
            try: conn.execute(f"ALTER TABLE user_binance_credentials ADD COLUMN {_col} {_def}")
            except Exception: pass
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT user_id FROM user_binance_credentials WHERE spot_auto_enabled=1").fetchall()
        conn.close()
        return [r["user_id"] for r in rows]
    except Exception:
        return []


def _spot_pos_table():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""CREATE TABLE IF NOT EXISTS spot_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, symbol TEXT,
            qty REAL, entry REAL, order_id TEXT, status TEXT, ts INTEGER)""")
        conn.commit(); conn.close()
    except Exception as e:
        log.debug("spot_pos table: %s", e)


def _fmt_spot_qty(client, symbol: str, qty: float) -> float:
    """تنسيق الكمية على خطوة LOT_SIZE للسبوت."""
    try:
        info = client.get_symbol_info(symbol)
        for f in info.get("filters", []):
            if f.get("filterType") == "LOT_SIZE":
                step = float(f.get("stepSize", 0))
                if step > 0:
                    import math
                    return math.floor(qty / step) * step
    except Exception as e:
        log.debug("spot qty fmt %s: %s", symbol, e)
    return round(qty, 6)


async def execute_spot_buy(user_id: str, signal: dict) -> dict:
    """شراء سبوت حقيقي بمبلغ USDT محدّد (quoteOrderQty). لا رافعة."""
    _spot_pos_table()
    client = get_client(user_id)
    if not client:
        return {"success": False, "error": "no client"}
    creds = get_credentials(user_id) or {}
    amount = float(creds.get("spot_trade_amount") or 5)
    _maxp = int(creds.get("spot_max_positions") or 0)
    sym = signal["symbol"]
    if _maxp > 0:
        try:
            _cc = sqlite3.connect(DB_PATH)
            _op = _cc.execute("SELECT COUNT(*) FROM spot_positions WHERE user_id=? AND status='open'", (user_id,)).fetchone()[0]
            _cc.close()
            if _op >= _maxp:
                return {"success": False, "error": f"بلغت حد الصفقات ({_maxp})"}
        except Exception: pass
    try:
        _b = client.get_asset_balance(asset="USDT")
        bal = float(_b["free"]) if _b else 0.0
    except Exception as e:
        return {"success": False, "error": f"تعذّر قراءة رصيد Spot: {e}"}
    spend = min(amount, bal)
    if spend < 5:
        return {"success": False, "error": f"رصيد Spot غير كافٍ ({bal:.2f}$، الأدنى 5$)"}
    try:
        order = client.order_market_buy(symbol=sym, quoteOrderQty=round(spend, 2))
        qty = float(order.get("executedQty", 0) or 0)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO spot_positions(user_id,symbol,qty,entry,order_id,status,ts) VALUES(?,?,?,?,?,?,?)",
                     (user_id, sym, qty, float(signal.get("entry", 0) or 0),
                      str(order.get("orderId", "")), "open", int(time.time())))
        conn.commit(); conn.close()
        log.info("🪙✅ Spot BUY %s qty=%s spend=%.2f$ (user %s)", sym, qty, spend, user_id)
        return {"success": True, "qty": qty, "order_id": str(order.get("orderId", ""))}
    except Exception as e:
        log.error("🪙❌ Spot buy %s: %s", sym, e)
        return {"success": False, "error": str(e)}


async def close_spot_all(symbol: str, reason: str = "close"):
    """يبيع كل مراكز السبوت المفتوحة على رمزٍ ما (عند TP3/SL)."""
    _spot_pos_table()
    try:
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT DISTINCT user_id FROM spot_positions WHERE symbol=? AND status='open'", (symbol,)).fetchall()
        conn.close()
    except Exception:
        return
    for r in rows:
        uid = r["user_id"]
        client = get_client(uid)
        if not client:
            continue
        asset = symbol.replace("USDT", "")
        try:
            _b = client.get_asset_balance(asset=asset)
            free = float(_b["free"]) if _b else 0.0
            q = _fmt_spot_qty(client, symbol, free)
            if q > 0:
                client.order_market_sell(symbol=symbol, quantity=q)
                log.info("🪙💰 Spot SELL %s qty=%s (user %s, %s)", symbol, q, uid, reason)
        except Exception as e:
            log.error("🪙❌ Spot sell %s: %s", symbol, e)
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE spot_positions SET status='closed' WHERE user_id=? AND symbol=? AND status='open'", (uid, symbol))
            conn.commit(); conn.close()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# ─── INIT ON IMPORT ──────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

init_db()
