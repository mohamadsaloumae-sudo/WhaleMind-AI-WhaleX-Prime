import sys, sqlite3, json, time
sys.path.insert(0, "/opt/whalex")
import ccxt
from quant_engine.ml_brain import live_context
from radars.futures.bleed_v2 import evaluate_exit
from services.market_pulse import _market_rsi

ex = ccxt.binance({"enableRateLimit": True, "timeout": 20000,
                   "options": {"defaultType": "future"}})
mr = _market_rsi(ex, 20)
print(f"🌡️ RSI السوق: {mr}  →  " +
      ("🔴 مُشبَع بيعاً — اللونج خطر" if mr < 42 else
       "⚠️ ضعيف" if mr < 46 else "✅ سليم"))
print()
p = sqlite3.connect("/opt/whalex/positions.db")
rows = [json.loads(d) for (d,) in
        p.execute("SELECT data FROM active_positions WHERE status!='closed'")]
L = [r for r in rows if r.get("direction") == "LONG"]
tk = ex.fetch_tickers()
print(f"{'العملة':13s} {'PnL':>8s} {'دفتر':>7s} {'تدفّق':>6s} {'RSI':>5s} {'الحكم'}")
verdict = []
for r in sorted(L, key=lambda z: z.get("opened_at") or 0):
    sym = r["symbol"]
    t = tk.get(f"{sym[:-4]}/USDT:USDT") or {}
    px = float(t.get("last") or 0)
    e = float(r.get("entry") or 0)
    if not px or not e:
        continue
    lv = float(r.get("leverage") or 1)
    pnl = (px - e) / e * 100 * lv
    age = (time.time() - (r.get("opened_at") or 0)) / 60
    sl = float(r.get("sl") or 0)
    slp = ((sl - e) / e * 100 * lv) if sl else -10
    pk = float(r.get("peak_price") or 0)
    peak = ((pk - e) / e * 100 * lv) if pk else max(0, pnl)
    lc = live_context(sym)
    ob = lc.get("ob_pressure")
    cv = lc.get("cvd_flow") or "?"
    # RSI العملة
    rsi = 50.0
    try:
        kl = ex.fetch_ohlcv(sym, "15m", limit=20)
        cl = [float(k[4]) for k in kl]
        g = l = 0.0
        for i in range(-14, 0):
            d = cl[i] - cl[i-1]
            g += d if d > 0 else 0
            l += -d if d < 0 else 0
        rs = (g/14) / ((l/14) or 1e-9)
        rsi = round(100 - 100/(1+rs), 1)
    except Exception:
        pass
    # حكم النظام نفسه
    closes = []
    try:
        closes = [float(k[4]) for k in ex.fetch_ohlcv(sym, "5m", limit=20)]
    except Exception:
        pass
    hit, why = evaluate_exit(pnl, slp, peak, age, closes, True)
    score = 0
    if hit: score += 3
    if ob is not None and ob < -0.15: score += 2
    if cv == "down": score += 2
    if mr < 42: score += 2
    if rsi > 65: score += 1
    if pnl < -3: score += 1
    v = ("🔴 أغلقها" if score >= 5 else
         "⚠️ راقبها" if score >= 3 else "✅ اتركها")
    obs = f"{ob:+.2f}" if ob is not None else "  —  "
    print(f"  {sym:11s} {pnl:+7.2f}% {obs:>7s} {cv:>6s} {rsi:5.1f} {v} ({score})")
    if why:
        print(f"      المدير: {why[:60]}")
    if score >= 5:
        verdict.append((sym, pnl, score, why))
print()
if verdict:
    print("═══ 🔴 حكم النظام: أغلقها ═══")
    for s, pnl, sc, why in sorted(verdict, key=lambda z: -z[2]):
        print(f"  {s:14s} {pnl:+7.2f}% | خطورة {sc}/11 {('· '+why[:40]) if why else ''}")
else:
    print("✅ النظام لا يرى لونج يستحقّ الإغلاق الفوريّ")
