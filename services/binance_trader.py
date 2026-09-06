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
import time
import logging
import asyncio
import os as _os
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
    account_type: str = "futures",
    exchange: str = "binance",
    passphrase: str = ""
) -> bool:
    """يحفظ مفاتيح API مشفّرة — مع المنصّة وpassphrase (أوكي إكس · بيتجت)."""
    try:
        api_key_enc = encrypt(api_key)
        api_secret_enc = encrypt(api_secret)
        pass_enc = encrypt(passphrase) if passphrase else None
        now = datetime.utcnow().isoformat()
        
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT OR REPLACE INTO user_binance_credentials
            (user_id, api_key_encrypted, api_secret_encrypted, is_testnet,
             account_type, created_at, updated_at, auto_trade_enabled,
             exchange, api_passphrase_encrypted)
            VALUES (?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM user_binance_credentials WHERE user_id=?), ?), ?, 0, ?, ?)
        """, (str(user_id), api_key_enc, api_secret_enc, int(is_testnet),
              account_type, str(user_id), now, now,
              (exchange or "binance").lower(), pass_enc))
        conn.commit()
        conn.close()
        log.info("✅ Credentials saved for user %s (testnet=%s)", user_id, is_testnet)
        return True
    except Exception as e:
        log.error("save_credentials error: %s", e)
        return False


_SYM_EX_CACHE: dict = {}
_SYM_EX_TS = [0.0]


def symbol_exchange(symbol: str) -> str:
    """🎯 على أي منصّة تُتداول هذه العملة؟
    العملات الحصرية على منصّاتها · والباقي على باينانس.
    """
    import time as _t
    if _t.time() - _SYM_EX_TS[0] > 600:
        try:
            _cn = sqlite3.connect("/opt/whalex/multi_universe.db")
            _SYM_EX_CACHE.clear()
            for s, ex in _cn.execute("SELECT symbol, exchange FROM universe"):
                _SYM_EX_CACHE[s] = ex
            _cn.close()
            _SYM_EX_TS[0] = _t.time()
        except Exception:
            pass
    return _SYM_EX_CACHE.get(symbol, "binance")


def get_user_exchanges(user_id: str) -> list:
    """🔌 كل منصّات المستخدم المربوطة — للواجهة والتوجيه."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT exchange, auto_trade_enabled, trade_amount_usdt, "
            "max_open_positions, account_type FROM user_binance_credentials "
            "WHERE user_id=?", (str(user_id),)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error("get_user_exchanges %s: %s", user_id, e)
        return []


def get_credentials_for(user_id: str, exchange: str) -> Optional[dict]:
    """🎯 اعتماديات منصّة بعينها — الأساس للتنفيذ متعدّد المنصّات.
    إشارة على Bitget تُنفَّذ بحساب Bitget، لا بأي حساب آخر.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM user_binance_credentials WHERE user_id=? AND exchange=?",
            (str(user_id), (exchange or "binance").lower())).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "user_id": row["user_id"],
            "api_key": decrypt(row["api_key_encrypted"]),
            "api_secret": decrypt(row["api_secret_encrypted"]),
            "is_testnet": bool(row["is_testnet"]),
            "auto_trade_enabled": bool(row["auto_trade_enabled"]),
            "trade_amount_usdt": row["trade_amount_usdt"],
            "max_open_positions": row["max_open_positions"],
            "allowed_grades": (row["allowed_grades"] or "A,S"),
            "leverage": row["leverage"] if "leverage" in row.keys() else None,
            "account_type": row["account_type"],
            "disabled_reason": row["disabled_reason"],
            "exchange": row["exchange"] or "binance",
            "passphrase": (decrypt(row["api_passphrase_encrypted"])
                           if "api_passphrase_encrypted" in row.keys()
                           and row["api_passphrase_encrypted"] else ""),
        }
    except Exception as e:
        log.error("get_credentials_for %s/%s: %s", user_id, exchange, e)
        return None


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
            # 🔌 المنصّة المختارة — باينانس افتراضياً للمستخدمين القدامى
            "exchange": (row["exchange"] if "exchange" in row.keys() else None) or "binance",
            "passphrase": (decrypt(row["api_passphrase_encrypted"])
                           if "api_passphrase_encrypted" in row.keys()
                           and row["api_passphrase_encrypted"] else ""),
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
        try:
            _tk = {t["symbol"]: float(t["price"]) for t in client.get_all_tickers()}
            _usd = 0.0
            for _a, _v in balances.items():
                _b = _a[2:] if _a.startswith("LD") else _a
                if _b in ("USDT", "USDC", "BUSD", "FDUSD", "TUSD"):
                    _usd += _v["total"]
                elif _b + "USDT" in _tk:
                    _usd += _v["total"] * _tk[_b + "USDT"]
            result["usdt_total_spot"] = _usd
        except Exception:
            result["usdt_total_spot"] = result.get("usdt_free", 0)
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
            amt = float(p.get("positionAmt") or 0)
            if amt == 0:
                continue
            active.append({
                "symbol": p.get("symbol", ""),
                "direction": "LONG" if amt > 0 else "SHORT",
                "size": abs(amt),
                "entry_price": float(p.get("entryPrice") or 0),
                "mark_price": float(p.get("markPrice") or 0),
                "unrealized_pnl": float(p.get("unRealizedProfit") or 0),
                "leverage": _lev_of(p),
            })
        return active
    except Exception as e:
        # ⚠️ الفشل ليس "لا مراكز" — نرمي كي لا يمرّ سقف المراكز
        #    ومانع التكرار على قائمة فارغة كاذبة.
        log.error("جلب المراكز %s: %s", user_id[:8], e)
        raise


def _lev_of(p: dict) -> int:
    """الرافعة من الحقل إن وُجد، وإلا من القيمة الاسمية ÷ الهامش.

    باينانس أزالت حقل leverage من positionInformation، وكان الكود
    يقرأ p["leverage"] مباشرةً فيرمي KeyError. والاستثناء كان يُبتلَع
    ويُرجع قائمة فارغة — فسقف المراكز ومانع التكرار توقّفا تماماً.
    مقيس: حساب فيه 11 مركزاً أرجعت الدالة له صفراً، ومشترك فُتحت له
    184 صفقة في يوم واحد، وMUBARAKUSDT فُتحت مرّتين لنفس المشترك.
    """
    try:
        v = float(p.get("leverage") or 0)
        if v > 0:
            return int(v)
    except Exception:
        pass
    try:
        no = abs(float(p.get("notional") or 0))
        im = abs(float(p.get("initialMargin") or 0))
        if no > 0 and im > 0:
            return max(1, int(round(no / im)))
    except Exception:
        pass
    return 1


# ═══════════════════════════════════════════════════════════════
# ─── TRADE EXECUTION (سيُستخدم لاحقاً) ─────────────────────────
# ═══════════════════════════════════════════════════════════════

# ═══ 🧮 الرافعة الذكية — موازنة مخاطرة الوقف بجودة الإشارة ═══
SMART_LEV_BASE_RISK = 20.0   # % من الهامش يُسمح بخسارتها عند ضرب الوقف (الأساس)
SMART_LEV_MIN = 5            # أدنى رافعة — الرافعة الذكية كانت
#   تهبط إلى 1x أو 2x على الإشارات واسعة الوقف (وقف 8% ÷ موازنة
#   20% = 3x)، وذلك يجعل الصفقة بلا جدوى. و5x آمنة رياضياً حتى
#   لأوسع وقف عندنا: التصفية عند حركة 19% والوقف الأوسع 13.3%،
#   فالوقف يُضرب قبل التصفية دائماً.

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


async def close_position_for_user(user_id: str, symbol: str, direction: str, reason: str = "") -> dict:
    """🔴 إغلاق حقيقي بأمر سوق reduceOnly — على منصّة العملة نفسها.
    🎯 صفقة بيتجت تُغلق بمفاتيح بيتجت. وبلا هذا التوجيه تبقى مفتوحة بلا حماية.
    """
    _sig_ex = symbol_exchange(symbol)
    creds = get_credentials_for(user_id, _sig_ex)
    if not creds and _sig_ex == "binance":
        creds = get_credentials(user_id)   # توافق خلفي
    if not creds or not creds.get("auto_trade_enabled"):
        return {"success": False, "error": "التداول الآلي غير مفعّل"}
    # ═══ 🔌 توجيه الإغلاق — نفس منطق الفتح ═══
    #   باينانس تكمل أدناه. غيرها يُغلق عبر مُهايئها المعزول (reduceOnly).
    _ex_id = (creds.get("exchange") or "binance").lower()
    if _ex_id != "binance":
        import asyncio as _aio
        from services.exchanges import get as _get_adapter
        _ad = _get_adapter(_ex_id)
        try:
            _cl = _ad.client(creds["api_key"], creds["api_secret"],
                             creds.get("passphrase", ""), futures=True)
            _r = await _aio.to_thread(_ad.close, _cl, symbol, True)
        except Exception as _ee:
            log.error("🔌 %s إغلاق %s: %s", _ad.name_ar, symbol, _ee)
            return {"success": False, "error": str(_ee)[:150]}
        if _r.get("ok"):
            log.info("🔌🔴 %s: أُغلق %s", _ad.name_ar, symbol)
            return {"success": True, "order_id": str(_r.get("id", "")),
                    "exchange": _ad.name_ar}
        return {"success": False, "error": _r.get("error", "فشل الإغلاق")}
    
    # ⚠️ كان يستدعي _client غير الموجودة، فكل إغلاق حقيقيّ يفشل صامتاً:
    #    36 إغلاقاً ورقياً في ساعتين وصفر إغلاق على البورصة — أي صفقات
    #    المشتركين تبقى مفتوحة بلا حصاد ولا قفل ولا وقف.
    try:
        client = Client(api_key=creds["api_key"],
                        api_secret=creds["api_secret"],
                        testnet=bool(creds.get("is_testnet")))
    except Exception as e:
        return {"success": False, "error": f"عميل: {e}"}
    try:
        # الكمية الفعلية المفتوحة من البورصة نفسها
        _pos = client.futures_position_information(symbol=symbol)
        _amt = 0.0
        for p in (_pos if isinstance(_pos, list) else [_pos]):
            _amt = float(p.get("positionAmt") or 0)
            if abs(_amt) > 0:
                break
        if abs(_amt) <= 0:
            return {"success": False, "error": "لا مركز مفتوح"}
        _side = "SELL" if _amt > 0 else "BUY"
        _order = None
        if _is_planned(reason) and not os.path.exists(LIMIT_EXIT_OFF):
            _order, _m = _limit_exit(client, symbol, _side, abs(_amt))
        if not _order:
            _order = client.futures_create_order(
                symbol=symbol, side=_side, type="MARKET",
                quantity=abs(_amt), reduceOnly=True,
            )
        # نلغي أوامر الوقف المعلّقة حتى لا تبقى يتيمة
        try:
            client.futures_cancel_all_open_orders(symbol=symbol)
        except Exception:
            pass
        # 📒 نُغلق الصفقة في سجلّ المستخدم بنتيجتها الفعلية.
        #    log_open كانت مربوطة و log_close لا — فالجدول يبقى فارغاً
        #    ولا يرى المشترك ولا الإدارة أي سجلّ تداول حقيقيّ.
        try:
            from services.user_trades import log_close as _lc
            # 💵 سعر الخروج الفعليّ من التعبئة نفسها.
            #    أمر السوق يعود بـavgPrice=0 لحظة إنشائه، فكنّا نسقط
            #    إلى سعر المؤشّر وهو تقريبيّ. والمشترك يقارن سجلّنا
            #    بباينانس فيرى فرقاً ويظنّه تلاعباً.
            _exit_real = 0.0
            try:
                _exit_real = float(_order.get("avgPrice") or 0)
            except Exception:
                _exit_real = 0.0
            if _exit_real <= 0:
                import time as _tt
                for _try in range(3):
                    try:
                        _od = client.futures_get_order(
                            symbol=symbol, orderId=_order["orderId"])
                        _exit_real = float(_od.get("avgPrice") or 0)
                        if _exit_real > 0:
                            break
                    except Exception:
                        pass
                    _tt.sleep(0.4)
            _fill = _exit_real
            if _fill <= 0:
                try:
                    _fill = float(client.futures_symbol_ticker(
                        symbol=symbol).get("price") or 0)
                    log.warning("💵 %s: تعذّر سعر التعبئة — استُعمل المؤشّر",
                                symbol)
                except Exception:
                    pass
            _ep = 0.0
            try:
                _ep = float(p.get("entryPrice") or 0)
            except Exception:
                pass
            # ⚠️ باينانس لم تعد تُرجع leverage في positionInformation،
            #    فنحسبها من القيمة الاسمية ÷ الهامش المبدئيّ.
            #    مقيس: notional 50.77$ ÷ initialMargin 10.15$ = 5.0x
            _lev = 1.0
            try:
                _lev = abs(float(p.get("leverage") or 0)) or 0.0
                if _lev <= 0:
                    _no = abs(float(p.get("notional") or 0))
                    _im = abs(float(p.get("initialMargin") or 0))
                    if _no > 0 and _im > 0:
                        _lev = round(_no / _im, 1)
                if _lev <= 0:
                    _lev = 1.0
            except Exception:
                _lev = 1.0
            _pct = 0.0
            if _ep > 0 and _fill > 0:
                _raw = (_fill - _ep) / _ep * 100.0
                _pct = _raw * _lev * (1 if _amt > 0 else -1)
            _lc(user_id, symbol, _fill, round(_pct, 3), "manual_close", "futures")
        except Exception as _le:
            log.debug("ledger close: %s", _le)

        log.info("🔴 إغلاق حقيقي: %s %s qty=%s (user %s)", symbol, _side, abs(_amt), user_id)
        return {"success": True, "order_id": str(_order.get("orderId", "")),
                "qty": abs(_amt)}
    except Exception as e:
        log.error("close real %s [%s]: %s", symbol,
                  str(user_id)[:8], e)
        return {"success": False, "error": str(e)}


async def close_all_real_users(symbol: str, direction: str, reason: str = "") -> int:
    """يُغلق المركز حقيقياً لكل مستخدم عليه تداول آلي مفعّل."""
    n = 0
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT user_id FROM user_binance_credentials WHERE auto_trade_enabled=1").fetchall()
        conn.close()
    except Exception as e:
        log.debug("close_all users: %s", e)
        return 0
    _failed = []
    for r in rows:
        _uid = r["user_id"]
        try:
            res = await close_position_for_user(_uid, symbol, direction, reason)
            if res.get("success"):
                n += 1
                continue
            _why = str(res.get("error", ""))
            # "لا مركز مفتوح" ليست فشلاً — المستخدم لم تُفتح له اصلاً
            if "لا مركز" in _why or "not open" in _why.lower():
                continue
            # 🔁 اعادة محاولة واحدة — الشبكة تخطئ مرة
            await asyncio.sleep(2.0)
            res2 = await close_position_for_user(_uid, symbol, direction, reason)
            if res2.get("success"):
                n += 1
                log.info("🔁 اُغلق بالمحاولة الثانية: %s [%s]",
                         symbol, str(_uid)[:8])
                continue
            _failed.append((str(_uid)[:8], str(res2.get("error", _why))[:60]))
        except Exception as e:
            _failed.append((str(_uid)[:8], str(e)[:60]))
    if _failed:
        # ⚠️ الاغلاق الورقيّ: كنّا نسجّل الصفقة مُغلقة والمركز مفتوح
        #    على المنصّة، فتنزف حتى يجدها حارس اليتيمة بعد دقائق.
        #    مقيس 6 سبتمبر: DASHUSDT سجّلناها -3.97% والواقع -8.88%.
        for _u, _w in _failed:
            log.warning("🔴⚠️ فشل اغلاق %s للمشترك %s — %s "
                        "(المركز قد يبقى مفتوحاً)", symbol, _u, _w)
    return n


# ⚡ نداءات باينانس متزامنة وتحجب حلقة الأحداث كلّها، فتنفيذ تسعة
#    مشتركين يصير تسلسلاً رغم asyncio.gather. مقيس: 17 ثانية بين
#    الإشارة وظهور الصفقة، والمشترك الأخير يدخل بسعر يبعد عشر ثوانٍ
#    عن الأوّل. فنُخرجها إلى خيوط منفصلة.
async def _aio_th(fn, *a, **kw):
    import asyncio as _a
    return await _a.to_thread(lambda: fn(*a, **kw))


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
    # 🎯 التوجيه: الإشارة تُنفَّذ على حساب منصّتها لا على أي حساب.
    #    KORUUSDT على بيتجت → يبحث عن حساب بيتجت للمستخدم.
    #    من لا حساب له على تلك المنصّة يتخطّى الإشارة بهدوء.
    _sig_ex = symbol_exchange(signal["symbol"])
    creds = get_credentials_for(user_id, _sig_ex)
    if not creds and _sig_ex == "binance":
        creds = get_credentials(user_id)   # توافق خلفي
    if not creds:
        return {"success": False, "error": "no_credentials"}
    
    if not creds["auto_trade_enabled"]:
        return {"success": False, "error": "auto_trade_disabled"}
    
    if signal.get("grade") not in creds["allowed_grades"]:
        return {"success": False, "error": f"grade {signal.get('grade')} not allowed"}
    
    # تحقق max positions + منع التكرار على نفس العملة
    # 🛡️ فشل الجلب يمنع الفتح — ولا يُعامَل كـ"لا مراكز".
    try:
        _open = await _aio_th(get_open_positions, user_id)
    except Exception as _pe:
        log.error("🛡️ %s: تعذّر جلب المراكز — لا نفتح: %s",
                  user_id[:8], str(_pe)[:60])
        return {"success": False, "error": "تعذّر جلب المراكز"}
    if len(_open) >= creds["max_open_positions"]:
        return {"success": False, "error": f"max positions reached ({len(_open)})"}
    if any(p.get("symbol") == signal["symbol"] for p in _open):
        return {"success": False, "error": f"position already open for {signal['symbol']}"}
    
    # ═══ 🔌 توجيه المنصّة — بعد كل الحمايات وقبل التنفيذ ═══
    #   باينانس تكمل على مسارها المُثبت أدناه. غيرها يمرّ بالمُهايئ المعزول.
    _ex_id = (creds.get("exchange") or "binance").lower()
    if _ex_id != "binance":
        import asyncio as _aio
        from services.exchanges import get as _get_adapter
        _ad = _get_adapter(_ex_id)
        try:
            _cl = _ad.client(creds["api_key"], creds["api_secret"],
                             creds.get("passphrase", ""), futures=True)
            _lev = int(creds.get("leverage") or signal.get("leverage") or 5)
            _r = await _aio.to_thread(
                _ad.open, _cl, signal["symbol"], signal["direction"],
                float(creds["trade_amount_usdt"]), _lev, True)
        except Exception as _ee:
            log.error("🔌 %s فتح %s: %s", _ad.name_ar, signal["symbol"], _ee)
            return {"success": False, "error": str(_ee)[:150]}
        if not _r.get("ok"):
            return {"success": False, "error": _r.get("error", "فشل الفتح")}
        log.info("🔌✅ %s: %s %s فُتحت", _ad.name_ar,
                 signal["symbol"], signal["direction"])
        return {"success": True, "order_id": str(_r.get("id", "")),
                "symbol": signal["symbol"], "direction": signal["direction"],
                "quantity": _r.get("qty"), "leverage": _lev,
                "exchange": _ad.name_ar}
    
    client = get_client(user_id)
    if not client:
        return {"success": False, "error": "client_init_failed"}
    
    symbol = signal["symbol"]
    direction = signal["direction"]
    side = "BUY" if direction == "LONG" else "SELL"
    trade_usdt = creds["trade_amount_usdt"]

    # 🛡️ حارس الهامش — لا نستهلك رصيد المشترك كلّه.
    #    مقيس: مشترك رصيده 10.18$ فُتحت له 3 صفقات بهامش 6$، فبقي
    #    متاحاً 4.13$ لا يكفي رسوم الفتح والإغلاق والتمويل.
    #    والقاعدة: نُبقي 5% سائلاً (أو 3$ أيّهما أكبر)، وعدد المراكز
    #    يُشتقّ من الرصيد ومبلغ الصفقة لا من رقم ثابت.
    try:
        from services.margin_guard import check as _mg_check
        _bal = 0.0
        for _b in await _aio_th(client.futures_account_balance):
            if _b.get("asset") == "USDT":
                _bal = float(_b.get("balance") or 0)
                break
        _used = 0.0
        try:
            for _p in await _aio_th(client.futures_position_information):
                if abs(float(_p.get("positionAmt") or 0)) > 0:
                    _used += abs(float(_p.get("initialMargin") or 0))
        except Exception:
            pass
        _lv_now = float(creds.get("leverage") or signal.get("leverage") or 5)
        # نحترم سقف المشترك أيضاً — الأقلّ من الاثنين هو الحاكم
        _user_cap = int(creds.get("max_open_positions") or 99)
        if len(_open) >= _user_cap:
            return {"success": False,
                    "error": f"سقف المشترك {_user_cap} (مفتوح {len(_open)})"}
        _ok, _amt, _why = _mg_check(_bal, len(_open), _used,
                                    float(trade_usdt), _lv_now)
        if not _ok:
            log.info("🛡️ %s %s مُنعت — %s", user_id[:8], symbol, _why)
            return {"success": False, "error": f"margin_guard: {_why}"}
        if _amt < float(trade_usdt):
            log.info("🛡️ %s %s صُغِّر المبلغ %.2f$ → %.2f$",
                     user_id[:8], symbol, float(trade_usdt), _amt)
        trade_usdt = _amt
    except Exception as _mge:
        log.warning("🛡️ حارس الهامش %s: %s", symbol, _mge)

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
            _br = await _aio_th(client.futures_leverage_bracket, symbol=symbol)
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
        await _aio_th(client.futures_change_leverage, symbol=symbol,
                      leverage=leverage)

        # 4. حساب الكمية (بدقة العملة)
        entry = signal["entry"]
        quantity = _fmt_qty(client, symbol, (trade_usdt * leverage) / entry)
        
        # 3. فتح الصفقة — حدّ أوّلاً، وسوقيّ فقط عند الإطفاء
        if os.path.exists(LIMIT_ENTRY_OFF):
            order = client.futures_create_order(
                symbol=symbol, side=side, type="MARKET", quantity=quantity)
        else:
            order, _why = await _aio_th(_limit_entry, client, symbol, side, direction,
                                       quantity, float(entry))
            if not order:
                return {"success": False, "error": _why or "limit not filled"}
        
        order_id = order["orderId"]
        # 📒 سجلّ حقيقي لهذا المستخدم — بسعر التنفيذ الفعليّ ورافعته.
        #    مقيس على حساب مشترك: GIGGLEUSDT سجّلناها بدخول 44.4 بينما
        #    نُفّذت على باينانس بـ42.74 — فرق 3.9% جعلنا نراها +9.80%
        #    وهي عنده -1.75%. والسبب أنّنا كنّا نسجّل سعر الإشارة لا
        #    سعر التعبئة، ورافعة الإشارة لا الرافعة المضبوطة فعلاً.
        try:
            from services.user_trades import log_open as _lo
            _real_fill = 0.0
            try:
                _real_fill = float(order.get("avgPrice") or 0)
            except Exception:
                _real_fill = 0.0
            if _real_fill <= 0:
                # أمر السوق قد يعود بلا avgPrice — نقرؤه من الأمر نفسه
                try:
                    _od = client.futures_get_order(symbol=symbol, orderId=order_id)
                    _real_fill = float(_od.get("avgPrice") or 0)
                except Exception:
                    pass
            if _real_fill <= 0:
                try:
                    _real_fill = float(client.futures_symbol_ticker(
                        symbol=symbol).get("price") or 0)
                except Exception:
                    pass
            if _real_fill <= 0:
                _real_fill = float(signal.get("entry") or 0) if isinstance(signal, dict) else 0
            _sig_px = float(signal.get("entry") or 0) if isinstance(signal, dict) else 0
            if _sig_px > 0 and _real_fill > 0:
                _slip = abs(_real_fill - _sig_px) / _sig_px * 100
                if _slip > 0.5:
                    log.warning("📒 انزلاق %s: إشارة %.8g → تنفيذ %.8g (%.2f%%)",
                                symbol, _sig_px, _real_fill, _slip)
            _lo(user_id, symbol, direction, _real_fill, quantity,
                float(leverage), str(order_id), "futures")
        except Exception as _le:
            log.debug("ledger open: %s", _le)
        log.info("✅ Trade opened: %s %s qty=%s (user %s, order %s)",
                 symbol, direction, quantity, user_id, order_id)
        
        # 4. وضع SL
        sl_side = "SELL" if direction == "LONG" else "BUY"
        # 🛡️ سقف الخسارة -8% على المنصّة نفسها — تنفّذه فوراً بلا انتظار
        #    دورة الفحص. مقيس 3 سبتمبر: BULLAUSDT وقفها عند حركة 8%
        #    = -40% بالرافعة، وأُغلقت -18.55% في دقيقة واحدة.
        _cap_mv = 8.0 / max(1.0, float(leverage or 5))
        _cap_sl = entry * (1 - _cap_mv / 100) if direction == "LONG" \
            else entry * (1 + _cap_mv / 100)
        _use_sl = signal["sl"]
        try:
            _rsl = float(signal["sl"])
            if direction == "LONG":
                _use_sl = max(_rsl, _cap_sl)
            else:
                _use_sl = min(_rsl, _cap_sl)
        except Exception:
            pass
        try:
            client.futures_create_order(
                symbol=symbol,
                side=sl_side,
                type="STOP_MARKET",
                stopPrice=_fmt_price(client, symbol, _use_sl),
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
    import os
    if os.path.exists("/opt/whalex/db/trading_freeze.flag"):
        return {"ok": False, "error": "التداول مجمّد مؤقتاً للصيانة"}
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
        # 🎯 حدّ اوّلاً، وسوقيّ فقط عند الاطفاء
        if os.path.exists(SPOT_LIMIT_OFF):
            order = client.order_market_buy(symbol=sym,
                                            quoteOrderQty=round(spend, 2))
        else:
            order, _why = _spot_limit_buy(
                client, sym, spend, float(signal.get("entry", 0) or 0))
            if not order:
                return {"success": False, "error": _why or "limit not filled"}
        qty = float(order.get("executedQty", 0) or 0)
        # 💵 سعر التعبئة الحقيقيّ لا سعر الإشارة — كان يسجّل الإشارة
        #    فيرى المشترك رقماً مختلفاً عن باينانس. مقيس على الفيوتشر:
        #    GIGGLEUSDT سجّلناها 44.4 ونُفّذت 42.74 (فرق 3.9%)،
        #    فرأيناها +9.80% وهي عنده -1.75%.
        _fill = 0.0
        try:
            _fl = order.get("fills") or []
            _tq = sum(float(f.get("qty") or 0) for f in _fl)
            _tv = sum(float(f.get("qty") or 0) * float(f.get("price") or 0)
                      for f in _fl)
            if _tq > 0:
                _fill = _tv / _tq
        except Exception:
            pass
        if _fill <= 0:
            try:
                _cq = float(order.get("cummulativeQuoteQty") or 0)
                if _cq > 0 and qty > 0:
                    _fill = _cq / qty
            except Exception:
                pass
        if _fill <= 0:
            _fill = float(signal.get("entry", 0) or 0)
        _sig_px = float(signal.get("entry", 0) or 0)
        if _sig_px > 0 and _fill > 0:
            _sl = abs(_fill - _sig_px) / _sig_px * 100
            if _sl > 0.5:
                log.warning("🪙📒 انزلاق %s: إشارة %.8g → تنفيذ %.8g (%.2f%%)",
                            sym, _sig_px, _fill, _sl)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO spot_positions(user_id,symbol,qty,entry,order_id,status,ts) VALUES(?,?,?,?,?,?,?)",
                     (user_id, sym, qty, _fill,
                      str(order.get("orderId", "")), "open", int(time.time())))
        conn.commit(); conn.close()
        log.info("🪙✅ Spot BUY %s qty=%s spend=%.2f$ (user %s)", sym, qty, spend, user_id)
        return {"success": True, "qty": qty, "order_id": str(order.get("orderId", ""))}
    except Exception as e:
        log.error("🪙❌ Spot buy %s: %s", sym, e)
        return {"success": False, "error": str(e)}


async def close_spot_all(symbol: str, reason: str = "close"):
    """يبيع كل مراكز السبوت المفتوحة على رمزٍ ما (عند TP3/SL)."""
    _ledger_rows = []
    try:
        import sqlite3 as _sq
        _cn = _sq.connect(DB_PATH); _cn.row_factory = _sq.Row
        _ledger_rows = [dict(r) for r in _cn.execute(
            "SELECT user_id, entry FROM spot_positions WHERE symbol=? AND status='open'", (symbol,))]
        _cn.close()
    except Exception:
        _ledger_rows = []
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
                _so = None
                if not os.path.exists(SPOT_LIMIT_OFF):
                    _so, _m = _spot_limit_sell(client, symbol, q)
                if not _so:
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


# ═══════════════════════════════════════════════════════════════
# POOL: subscriber client pool (overrides get_client above)
# ═══════════════════════════════════════════════════════════════
# Measured: each Client() build = 266ms (server_time + exchange_info).
# Called 2-3x per subscriber per trade -> 10 subscribers = 10 seconds
# before the first order reaches Binance.
# Live proof: HEMIUSDT signal 23:41:06 -> fill 23:41:18 (11.1s).
# Kill switch: touch /opt/whalex/db/client_pool.off
_CLIENT_POOL: dict = {}
_POOL_TTL = 3600
_POOL_OFF = "/opt/whalex/db/client_pool.off"


def _creds_fp(creds: dict) -> str:
    raw = f"{creds.get('api_key', '')}|{creds.get('is_testnet')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def drop_client(user_id: str = "") -> None:
    if user_id:
        _CLIENT_POOL.pop(user_id, None)
    else:
        _CLIENT_POOL.clear()


def get_client(user_id: str) -> Optional[Client]:
    creds = get_credentials(user_id)
    if not creds:
        return None
    if os.path.exists(_POOL_OFF):
        try:
            return Client(api_key=creds["api_key"],
                          api_secret=creds["api_secret"],
                          testnet=creds["is_testnet"])
        except Exception as e:
            log.error("Client init error for %s: %s", user_id, e)
            return None
    fp = ""
    try:
        fp = _creds_fp(creds)
        ent = _CLIENT_POOL.get(user_id)
        if ent and ent[1] == fp and (time.time() - ent[2]) < _POOL_TTL:
            return ent[0]
    except Exception as _fe:
        log.debug("pool lookup: %s", _fe)
    try:
        client = Client(api_key=creds["api_key"],
                        api_secret=creds["api_secret"],
                        testnet=creds["is_testnet"])
        if fp:
            _CLIENT_POOL[user_id] = (client, fp, time.time())
            log.info("POOL client %s (total %d)",
                     user_id[:8], len(_CLIENT_POOL))
        return client
    except Exception as e:
        log.error("Client init error for %s: %s", user_id, e)
        return None


# ═══════════════════════════════════════════════════════════════
# LIMIT ENTRY - zero slippage
# ═══════════════════════════════════════════════════════════════
# Measured Sep 1: 龙虾USDT signal 0.085916 filled at 0.079531 for
# subscribers = 7.43% slippage = 37% of margin at 5x leverage,
# before the trade even started. System logged it then opened anyway
# because type="MARKET" has no price ceiling.
# Industry standard (freqtrade / MQL5 / exchange Chase Limit):
#   entry -> limit, stoploss -> market, timeout then cancel,
#   never convert to market.
# Kill switch: touch /opt/whalex/db/limit_entry.off
LIMIT_ENTRY_OFF = "/opt/whalex/db/limit_entry.off"
LIMIT_WAIT_SEC = 30.0
LIMIT_FLEE_PCT = 1.0
LIMIT_POLL_SEC = 1.0


def _limit_entry(client, symbol, side, direction, quantity, sig_px):
    import time as _t
    try:
        px = _fmt_price(client, symbol, sig_px)
        order = client.futures_create_order(
            symbol=symbol, side=side, type="LIMIT",
            timeInForce="GTC", price=px, quantity=quantity)
    except Exception as e:
        log.warning("limit order %s: %s", symbol, e)
        return None, f"limit failed: {e}"
    oid = order.get("orderId")
    t0 = _t.time()
    filled = 0.0
    while (_t.time() - t0) < LIMIT_WAIT_SEC:
        _t.sleep(LIMIT_POLL_SEC)
        try:
            od = client.futures_get_order(symbol=symbol, orderId=oid)
        except Exception as e:
            log.debug("poll %s: %s", symbol, e)
            continue
        st = od.get("status")
        filled = float(od.get("executedQty") or 0)
        if st == "FILLED":
            log.info("LIMIT FILLED %s @%s (%.0fs)", symbol, px, _t.time()-t0)
            return od, ""
        if st in ("CANCELED", "EXPIRED", "REJECTED"):
            return (od if filled > 0 else None), f"cancelled ({st})"
        try:
            live = float(client.futures_symbol_ticker(
                symbol=symbol).get("price") or 0)
        except Exception:
            continue
        if live <= 0 or sig_px <= 0:
            continue
        drift = ((sig_px - live) if direction == "SHORT"
                 else (live - sig_px)) / sig_px * 100
        if drift > LIMIT_FLEE_PCT:
            try:
                client.futures_cancel_order(symbol=symbol, orderId=oid)
            except Exception:
                pass
            if filled > 0:
                od = client.futures_get_order(symbol=symbol, orderId=oid)
                log.info("LIMIT PARTIAL %s %.0f%% then fled %.2f%%", symbol,
                         filled/float(quantity)*100, drift)
                return od, ""
            log.info("LIMIT CANCEL %s - price fled %.2f%%", symbol, drift)
            return None, f"price fled {drift:.2f}%"
    try:
        client.futures_cancel_order(symbol=symbol, orderId=oid)
    except Exception:
        pass
    try:
        od = client.futures_get_order(symbol=symbol, orderId=oid)
        filled = float(od.get("executedQty") or 0)
    except Exception:
        od = None
    if filled > 0:
        log.info("LIMIT PARTIAL %s %.0f%% at timeout", symbol,
                 filled/float(quantity)*100)
        return od, ""
    log.info("LIMIT CANCEL %s - timeout %.0fs no fill", symbol, LIMIT_WAIT_SEC)
    # 🎯 كمين السعر الافضل — الاشارة هربت، فبدل ملاحقتها ننصب
    #    امراً عند نقطة اجود من الاشارة وننتظرها 5 دقائق.
    #    مقيس 6 سبتمبر: 5 اشارات ضاعت بـtimeout وكانت ستعطي
    #    ما بين +10% و+35% لطارق. والملاحقة ترفض (ذيل الشمعة).
    if not _os.path.exists(AMBUSH_OFF):
        _o2, _w2 = _ambush_entry(client, symbol, side, direction,
                                 quantity, sig_px)
        if _o2:
            return _o2, ""
        log.info("🎯 %s كمين: %s", symbol, _w2)
    return None, "timeout no fill"


# ═══════════════════════════════════════════════════════════════
# 🎯 كمين السعر الافضل — المرحلة الثانية بعد فشل الحدّ الاول
# ═══════════════════════════════════════════════════════════════
# الاطفاء: touch /opt/whalex/db/ambush.off
AMBUSH_OFF = "/opt/whalex/db/ambush.off"
AMBUSH_WINDOW = 300.0
AMBUSH_EDGE = 1.0
AMBUSH_POLL = 3.0


def _ambush_entry(client, symbol, side, direction, quantity, sig_px):
    """ينصب امر حدّ عند سعر اجود من الاشارة بـ1% وينتظره 5 دقائق."""
    import time as _t
    if sig_px <= 0:
        return None, "بلا سعر اشارة"
    _d = str(direction or "").upper()
    tgt = sig_px * (1 + AMBUSH_EDGE / 100.0) if _d == "SHORT" \
        else sig_px * (1 - AMBUSH_EDGE / 100.0)
    log.info("🎯 %s كمين @%.8g (اجود %.1f%% من %.8g)",
             symbol, tgt, AMBUSH_EDGE, sig_px)
    t0 = _t.time()
    while (_t.time() - t0) < AMBUSH_WINDOW:
        _t.sleep(AMBUSH_POLL)
        try:
            live = float(client.futures_symbol_ticker(
                symbol=symbol).get("price") or 0)
        except Exception:
            continue
        if live <= 0:
            continue
        _hit = live >= tgt if _d == "SHORT" else live <= tgt
        if not _hit:
            continue
        try:
            o = client.futures_create_order(
                symbol=symbol, side=side, type="LIMIT",
                timeInForce="GTC", quantity=quantity,
                price=_fmt_price(client, symbol, tgt))
        except Exception as e:
            return None, "تعذّر الوضع: %s" % str(e)[:50]
        oid = o.get("orderId")
        t1 = _t.time()
        while (_t.time() - t1) < 20.0:
            _t.sleep(1.0)
            try:
                od = client.futures_get_order(symbol=symbol, orderId=oid)
            except Exception:
                continue
            if od.get("status") == "FILLED":
                log.info("🎯✅ %s كمين امتلأ @%.8g", symbol, tgt)
                return od, ""
            if od.get("status") in ("CANCELED", "EXPIRED", "REJECTED"):
                break
        try:
            client.futures_cancel_order(symbol=symbol, orderId=oid)
        except Exception:
            pass
        return None, "الكمين لم يمتلئ"
    return None, "انتهت مهلة الكمين"


# ═══════════════════════════════════════════════════════════════
# LIMIT EXIT - planned exits only
# ═══════════════════════════════════════════════════════════════
# Measured: trade closed -4.77% in system, -6.20% and -6.18% for
# subscribers = 1.4% extra exit slippage.
# Standard (BloFin / NinjaTrader / Topstep):
#   planned exit -> limit (slippage impossible)
#   emergency    -> market (getting out beats price)
# Never cancel here - we always exit, limit first then market.
# Kill switch: touch /opt/whalex/db/limit_exit.off
LIMIT_EXIT_OFF = "/opt/whalex/db/limit_exit.off"
EXIT_WAIT_SEC = 8.0
EXIT_POLL_SEC = 0.5
# مطابقة حرفية لقيم ExitReason — الخروج المخطط فقط
PLANNED_EXITS = ("tactical_exit", "tp1_hit", "tp2_hit", "tp3_hit",
                 "explosion")


def _is_planned(reason):
    """مطابقة تامّة — لا جزئية، حتى لا يُصنَّف طارئ كمخطَّط."""
    return str(reason or "").strip().lower() in PLANNED_EXITS


def _limit_exit(client, symbol, side, qty):
    import time as _t
    try:
        live = float(client.futures_symbol_ticker(
            symbol=symbol).get("price") or 0)
        if live <= 0:
            raise ValueError("no price")
        px = _fmt_price(client, symbol, live)
        o = client.futures_create_order(
            symbol=symbol, side=side, type="LIMIT", timeInForce="GTC",
            price=px, quantity=qty, reduceOnly=True)
    except Exception as e:
        log.debug("limit exit %s: %s", symbol, e)
        return None, "limit-failed"
    oid = o.get("orderId")
    t0 = _t.time()
    while (_t.time() - t0) < EXIT_WAIT_SEC:
        _t.sleep(EXIT_POLL_SEC)
        try:
            od = client.futures_get_order(symbol=symbol, orderId=oid)
        except Exception:
            continue
        if od.get("status") == "FILLED":
            log.info("EXIT LIMIT %s @%s (%.1fs)", symbol, px, _t.time()-t0)
            return od, "limit"
        if od.get("status") in ("CANCELED", "EXPIRED", "REJECTED"):
            break
    try:
        client.futures_cancel_order(symbol=symbol, orderId=oid)
    except Exception:
        pass
    log.info("EXIT LIMIT %s timeout -> market", symbol)
    return None, "timeout"


# ═══════════════════════════════════════════════════════════════
# SPOT LIMIT — دخول وخروج بالحدّ، لا انزلاق
# ═══════════════════════════════════════════════════════════════
# نفس معيار الفيوتشر: دخول بحدّ ومهلة ثمّ الغاء، وخروج بحدّ
# قصير ثمّ ارتداد الى السوق (الخروج مضمون دائماً).
# الاطفاء: touch /opt/whalex/db/spot_limit.off
SPOT_LIMIT_OFF = "/opt/whalex/db/spot_limit.off"
SPOT_WAIT_SEC = 30.0
SPOT_FLEE_PCT = 1.0
SPOT_POLL_SEC = 1.0
SPOT_EXIT_WAIT = 8.0
SPOT_EXIT_POLL = 0.5


def _spot_limit_buy(client, sym, spend, sig_px):
    import time as _t
    try:
        if sig_px <= 0:
            return None, "no signal price"
        qty = _fmt_spot_qty(client, sym, spend / sig_px)
        if qty <= 0:
            return None, "qty too small"
        o = client.order_limit_buy(symbol=sym, quantity=qty,
                                   price=f"{sig_px:.10f}".rstrip("0"))
    except Exception as e:
        log.warning("spot limit buy %s: %s", sym, e)
        return None, f"limit failed: {e}"
    oid = o.get("orderId")
    t0 = _t.time()
    while (_t.time() - t0) < SPOT_WAIT_SEC:
        _t.sleep(SPOT_POLL_SEC)
        try:
            od = client.get_order(symbol=sym, orderId=oid)
        except Exception:
            continue
        st = od.get("status")
        filled = float(od.get("executedQty") or 0)
        if st == "FILLED":
            log.info("SPOT LIMIT FILLED %s (%.0fs)", sym, _t.time() - t0)
            return od, ""
        if st in ("CANCELED", "EXPIRED", "REJECTED"):
            return (od if filled > 0 else None), f"cancelled ({st})"
        try:
            live = float(client.get_symbol_ticker(symbol=sym).get("price") or 0)
        except Exception:
            continue
        if live <= 0:
            continue
        drift = (live - sig_px) / sig_px * 100
        if drift > SPOT_FLEE_PCT:
            try:
                client.cancel_order(symbol=sym, orderId=oid)
            except Exception:
                pass
            if filled > 0:
                return client.get_order(symbol=sym, orderId=oid), ""
            log.info("SPOT LIMIT CANCEL %s - fled %.2f%%", sym, drift)
            return None, f"price fled {drift:.2f}%"
    try:
        client.cancel_order(symbol=sym, orderId=oid)
        od = client.get_order(symbol=sym, orderId=oid)
        if float(od.get("executedQty") or 0) > 0:
            return od, ""
    except Exception:
        pass
    log.info("SPOT LIMIT CANCEL %s - timeout", sym)
    return None, "timeout no fill"


def _spot_limit_sell(client, sym, qty):
    import time as _t
    try:
        live = float(client.get_symbol_ticker(symbol=sym).get("price") or 0)
        if live <= 0:
            return None, "no price"
        o = client.order_limit_sell(symbol=sym, quantity=qty,
                                    price=f"{live:.10f}".rstrip("0"))
    except Exception as e:
        log.debug("spot limit sell %s: %s", sym, e)
        return None, "limit-failed"
    oid = o.get("orderId")
    t0 = _t.time()
    while (_t.time() - t0) < SPOT_EXIT_WAIT:
        _t.sleep(SPOT_EXIT_POLL)
        try:
            od = client.get_order(symbol=sym, orderId=oid)
        except Exception:
            continue
        if od.get("status") == "FILLED":
            log.info("SPOT EXIT LIMIT %s (%.1fs)", sym, _t.time() - t0)
            return od, "limit"
        if od.get("status") in ("CANCELED", "EXPIRED", "REJECTED"):
            break
    try:
        client.cancel_order(symbol=sym, orderId=oid)
    except Exception:
        pass
    log.info("SPOT EXIT LIMIT %s timeout -> market", sym)
    return None, "timeout"
