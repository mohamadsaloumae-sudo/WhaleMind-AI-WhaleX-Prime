"""🪙🌐 تنفيذ السبوت على المنصّات السبع.

كان التنفيذ محصوراً بباينانس، فإشارة من باي بيت أو مكسي تُرسَل ولا تُنفَّذ.
الآن: الإشارة تُنفَّذ على منصّتها هي، بمفتاح صاحبها هناك.
"""
import logging, sqlite3, time
log = logging.getLogger("spot_exec")
DB_PATH = "/opt/whalex/db/whalex.db"
MIN_SPEND = 5.0
_ADAPTERS = {}

def _adapter(ex: str):
    ex = (ex or "binance").lower()
    if ex in _ADAPTERS: return _ADAPTERS[ex]
    mod = {"binance":("binance_adapter","BinanceAdapter"),
           "bybit":("bybit_adapter","BybitAdapter"),
           "okx":("okx_adapter","OkxAdapter"),
           "bitget":("bitget_adapter","BitgetAdapter"),
           "gate":("gate_adapter","GateAdapter"),
           "mexc":("mexc_adapter","MexcAdapter"),
           "bingx":("bingx_adapter","BingxAdapter")}.get(ex)
    if not mod: return None
    import importlib
    m = importlib.import_module(f"services.exchanges.{mod[0]}")
    a = getattr(m, mod[1])()
    _ADAPTERS[ex] = a
    return a

def _init_table():
    try:
        c = sqlite3.connect(DB_PATH)
        c.execute("""CREATE TABLE IF NOT EXISTS spot_positions_multi(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, exchange TEXT,
            symbol TEXT, qty REAL, entry REAL, spend REAL, order_id TEXT,
            status TEXT, ts INTEGER, closed_ts INTEGER, exit_price REAL, pnl_pct REAL)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_spm ON spot_positions_multi(user_id,status)")
        c.commit(); c.close()
    except Exception as e:
        log.debug("init: %s", e)

def spot_traders_for(exchange: str) -> list:
    ex = (exchange or "binance").lower()
    out = []
    try:
        from services.binance_trader import decrypt
    except Exception:
        return out
    try:
        c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row
        rows = c.execute("SELECT * FROM user_binance_credentials WHERE spot_auto_enabled=1").fetchall()
        c.close()
    except Exception as e:
        log.debug("traders: %s", e); return out
    for r in rows:
        if (r["exchange"] or "binance").lower() != ex: continue
        if r["disabled_reason"]: continue
        try:
            k = decrypt(r["api_key_encrypted"]); s = decrypt(r["api_secret_encrypted"])
            p = ""
            try:
                if r["api_passphrase_encrypted"]: p = decrypt(r["api_passphrase_encrypted"])
            except Exception: p = ""
        except Exception as e:
            log.warning("🔑 فكّ مفتاح %s: %s", str(r["user_id"])[:8], e); continue
        out.append((r["user_id"], k, s, p, float(r["spot_trade_amount"] or 5),
                    int(r["spot_max_positions"] or 0), bool(r["is_testnet"])))
    return out

def _open_count(user_id: str, exchange: str) -> int:
    try:
        c = sqlite3.connect(DB_PATH)
        n = c.execute("SELECT COUNT(*) FROM spot_positions_multi WHERE user_id=? AND exchange=? AND status='open'",
                      (user_id, exchange)).fetchone()[0]
        c.close(); return int(n)
    except Exception:
        return 0

def buy(exchange: str, symbol: str, entry: float) -> list:
    import os
    if os.path.exists("/opt/whalex/db/trading_freeze.flag"):
        return [{"ok": False, "error": "التداول مجمّد"}]
    _init_table()
    ad = _adapter(exchange)
    if not ad: return [{"ok": False, "error": f"لا محوّل لـ{exchange}"}]
    results = []
    for uid, key, sec, pw, amount, maxp, testnet in spot_traders_for(exchange):
        try:
            if maxp > 0 and _open_count(uid, exchange) >= maxp:
                results.append({"ok": False, "user": uid, "error": f"حدّ الصفقات ({maxp})"}); continue
            c = ad.client(key, sec, pw, futures=False, testnet=testnet)
            try:
                bal = float((c.fetch_balance().get("USDT") or {}).get("free") or 0)
            except Exception as e:
                results.append({"ok": False, "user": uid, "error": f"رصيد: {str(e)[:50]}"}); continue
            spend = min(amount, bal)
            if spend < MIN_SPEND:
                results.append({"ok": False, "user": uid, "error": f"رصيد {exchange} غير كافٍ ({bal:.2f}$)"}); continue
            r = ad.open(c, symbol, "BUY", spend, lev=1.0, futures=False)
            if not r.get("ok"):
                results.append({"ok": False, "user": uid, "error": r.get("error")}); continue
            cn = sqlite3.connect(DB_PATH)
            cn.execute("INSERT INTO spot_positions_multi"
                       "(user_id,exchange,symbol,qty,entry,spend,order_id,status,ts) VALUES(?,?,?,?,?,?,?,?,?)",
                       (uid, exchange, symbol, r.get("qty",0), float(entry or r.get("price",0)),
                        spend, r.get("id",""), "open", int(time.time())))
            cn.commit(); cn.close()
            log.info("🪙✅ %s شراء %s كمية=%s مبلغ=%.2f$ (%s)", exchange, symbol,
                     r.get("qty"), spend, str(uid)[:8])
            results.append({"ok": True, "user": uid, "qty": r.get("qty"), "spend": spend})
        except Exception as e:
            log.error("🪙❌ %s شراء %s: %s", exchange, symbol, e)
            results.append({"ok": False, "user": uid, "error": str(e)[:80]})
    return results

def sell_all(exchange: str, symbol: str, exit_price: float = 0.0) -> list:
    _init_table()
    ad = _adapter(exchange)
    if not ad: return [{"ok": False, "error": f"لا محوّل لـ{exchange}"}]
    results = []
    try:
        cn = sqlite3.connect(DB_PATH); cn.row_factory = sqlite3.Row
        rows = cn.execute("SELECT * FROM spot_positions_multi WHERE exchange=? AND symbol=? AND status='open'",
                          (exchange, symbol)).fetchall()
        cn.close()
    except Exception as e:
        return [{"ok": False, "error": str(e)}]
    creds = {u: (k, s, p, t) for u, k, s, p, _a, _m, t in spot_traders_for(exchange)}
    for row in rows:
        uid = row["user_id"]
        if uid not in creds: continue
        k, s, p, testnet = creds[uid]
        try:
            c = ad.client(k, s, p, futures=False, testnet=testnet)
            r = ad.close(c, symbol, futures=False)
            pnl = 0.0
            if row["entry"] and exit_price:
                pnl = (float(exit_price)-float(row["entry"]))/float(row["entry"])*100
            cn = sqlite3.connect(DB_PATH)
            cn.execute("UPDATE spot_positions_multi SET status=?, closed_ts=?, exit_price=?, pnl_pct=? WHERE id=?",
                       ("closed" if r.get("ok") else "error", int(time.time()),
                        float(exit_price or 0), round(pnl,3), row["id"]))
            cn.commit(); cn.close()
            log.info("🪙🔴 %s بيع %s | %s | %+.2f%%", exchange, symbol,
                     "نجح" if r.get("ok") else r.get("error"), pnl)
            results.append({"ok": r.get("ok"), "user": uid, "pnl": pnl, "error": r.get("error")})
        except Exception as e:
            log.error("🪙❌ %s بيع %s: %s", exchange, symbol, e)
            results.append({"ok": False, "user": uid, "error": str(e)[:80]})
    return results
