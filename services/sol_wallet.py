"""🔐☀️ محفظة سولانا الشخصية — WhaleX (المرحلة 1: مفتاح مشفّر + حدود + رصيد)"""
import os, json, time, sqlite3, logging

log = logging.getLogger("sol_wallet")

_BASE = "/opt/whalex"
KEY_FILE = os.path.join(_BASE, ".sol_wallet.enc")
WALLET_DB = os.path.join(_BASE, "db", "sol_wallet.db")
RPC_URL = os.environ.get("SOL_RPC", "https://api.mainnet-beta.solana.com")

HARD_MAX_PER_TRADE = 2.0
HARD_MAX_DAILY = 5.0
HARD_MAX_CONCURRENT = 5

DEFAULTS = {"enabled": 0, "per_trade_sol": 0.1, "daily_max_sol": 0.5,
            "max_concurrent": 3, "slippage_bps": 300}


def _fernet():
    import base64
    from cryptography.fernet import Fernet
    key = os.environ.get("ENCRYPTION_KEY", "")
    if not key:
        env = os.path.join(_BASE, ".env")
        if os.path.exists(env):
            with open(env, encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("ENCRYPTION_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    if not key:
        raise RuntimeError("ENCRYPTION_KEY missing in .env")
    kb = key.encode()[:32].ljust(32, b"0")
    return Fernet(base64.urlsafe_b64encode(kb))


def save_private_key(secret_b58: str) -> str:
    import base58
    from solders.keypair import Keypair
    raw = base58.b58decode(secret_b58.strip())
    kp = Keypair.from_bytes(raw)
    pub = str(kp.pubkey())
    token = _fernet().encrypt(secret_b58.strip().encode())
    with open(KEY_FILE, "wb") as fh:
        fh.write(token)
    os.chmod(KEY_FILE, 0o600)
    _db_init()
    _set_meta("pubkey", pub)
    log.info("🔐 محفظة محفوظة مشفّرة — العنوان %s", pub)
    return pub


def create_wallet(force: bool = False) -> dict:
    """🔐 ينشئ محفظة جديدة داخل النظام ويحفظها مشفّرة.
    يرجع المفتاح الخاص مرّة واحدة — احفظه فوراً، لن يُعرض مرّة أخرى."""
    import base58
    from solders.keypair import Keypair
    if os.path.exists(KEY_FILE) and not force:
        raise RuntimeError("محفظة موجودة بالفعل — force=True للاستبدال (ستفقد القديمة)")
    kp = Keypair()
    secret_b58 = base58.b58encode(bytes(kp)).decode()
    pub = str(kp.pubkey())
    with open(KEY_FILE, "wb") as fh:
        fh.write(_fernet().encrypt(secret_b58.encode()))
    os.chmod(KEY_FILE, 0o600)
    _db_init()
    _set_meta("pubkey", pub)
    log.info("🔐 محفظة جديدة أُنشئت — %s", pub)
    return {"pubkey": pub, "secret_b58": secret_b58}


def _load_keypair():
    import base58
    from solders.keypair import Keypair
    if not os.path.exists(KEY_FILE):
        raise RuntimeError("لا محفظة محفوظة")
    with open(KEY_FILE, "rb") as fh:
        token = fh.read()
    secret = _fernet().decrypt(token).decode()
    return Keypair.from_bytes(base58.b58decode(secret))


def get_pubkey() -> str:
    v = _get_meta("pubkey")
    return v if v else str(_load_keypair().pubkey())


def wallet_exists() -> bool:
    return os.path.exists(KEY_FILE)


def _db_init():
    os.makedirs(os.path.dirname(WALLET_DB), exist_ok=True)
    cn = sqlite3.connect(WALLET_DB)
    cn.execute("CREATE TABLE IF NOT EXISTS wallet_meta(k TEXT PRIMARY KEY, v TEXT)")
    cn.execute("CREATE TABLE IF NOT EXISTS wallet_config(k TEXT PRIMARY KEY, v TEXT)")
    cn.execute("""CREATE TABLE IF NOT EXISTS wallet_trades(
        id INTEGER PRIMARY KEY, symbol TEXT, address TEXT, side TEXT,
        sol_amount REAL, price REAL, signature TEXT, status TEXT,
        error TEXT, ts INTEGER)""")
    cn.commit(); cn.close()


def _set_meta(k, v):
    _db_init()
    cn = sqlite3.connect(WALLET_DB)
    cn.execute("INSERT OR REPLACE INTO wallet_meta(k,v) VALUES(?,?)", (k, str(v)))
    cn.commit(); cn.close()


def _get_meta(k):
    if not os.path.exists(WALLET_DB):
        return None
    cn = sqlite3.connect(WALLET_DB)
    r = cn.execute("SELECT v FROM wallet_meta WHERE k=?", (k,)).fetchone()
    cn.close()
    return r[0] if r else None


def get_config() -> dict:
    _db_init()
    cfg = dict(DEFAULTS)
    cn = sqlite3.connect(WALLET_DB)
    for k, v in cn.execute("SELECT k,v FROM wallet_config"):
        if k in cfg:
            try:
                cfg[k] = type(DEFAULTS[k])(json.loads(v))
            except Exception:
                pass
    cn.close()
    cfg["per_trade_sol"] = min(float(cfg["per_trade_sol"]), HARD_MAX_PER_TRADE)
    cfg["daily_max_sol"] = min(float(cfg["daily_max_sol"]), HARD_MAX_DAILY)
    cfg["max_concurrent"] = min(int(cfg["max_concurrent"]), HARD_MAX_CONCURRENT)
    return cfg


def set_config(**kw) -> dict:
    _db_init()
    cn = sqlite3.connect(WALLET_DB)
    for k, v in kw.items():
        if k not in DEFAULTS:
            continue
        if k == "per_trade_sol":
            v = max(0.001, min(float(v), HARD_MAX_PER_TRADE))
        elif k == "daily_max_sol":
            v = max(0.001, min(float(v), HARD_MAX_DAILY))
        elif k == "max_concurrent":
            v = max(1, min(int(v), HARD_MAX_CONCURRENT))
        elif k == "enabled":
            v = 1 if int(v) else 0
        elif k == "slippage_bps":
            v = max(50, min(int(v), 2000))
        cn.execute("INSERT OR REPLACE INTO wallet_config(k,v) VALUES(?,?)", (k, json.dumps(v)))
    cn.commit(); cn.close()
    return get_config()


def spent_today() -> float:
    _db_init()
    since = int(time.time()) - 86400
    cn = sqlite3.connect(WALLET_DB)
    r = cn.execute("SELECT COALESCE(SUM(sol_amount),0) FROM wallet_trades "
                   "WHERE side='buy' AND status='ok' AND ts > ?", (since,)).fetchone()
    cn.close()
    return float(r[0] or 0)


def open_positions_count() -> int:
    _db_init()
    cn = sqlite3.connect(WALLET_DB)
    r = cn.execute("SELECT COUNT(*) FROM wallet_trades WHERE side='buy' AND status='ok' "
                   "AND address NOT IN (SELECT address FROM wallet_trades WHERE side='sell' AND status='ok')").fetchone()
    cn.close()
    return int(r[0] or 0)


async def get_balance() -> dict:
    import httpx
    pub = get_pubkey()
    body = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [pub]}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(RPC_URL, json=body)
        j = r.json()
    lamports = ((j.get("result") or {}).get("value") or 0)
    return {"pubkey": pub, "sol": lamports / 1_000_000_000, "lamports": lamports}


def can_trade(sol_amount: float) -> tuple:
    cfg = get_config()
    if not cfg["enabled"]:
        return False, "التداول الآلي مُطفأ"
    if not wallet_exists():
        return False, "لا محفظة محفوظة"
    if sol_amount > cfg["per_trade_sol"]:
        return False, f"يتجاوز حدّ الصفقة ({cfg['per_trade_sol']} SOL)"
    if spent_today() + sol_amount > cfg["daily_max_sol"]:
        return False, f"يتجاوز الحدّ اليومي ({cfg['daily_max_sol']} SOL)"
    if open_positions_count() >= cfg["max_concurrent"]:
        return False, f"الصفقات المتزامنة ممتلئة ({cfg['max_concurrent']})"
    return True, "مسموح"
