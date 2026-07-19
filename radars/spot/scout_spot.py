"""🪙 عقل السبوت v1 — صيّاد قيعان التجميع (معزول كلياً عن الفيوتشر).
المنطق: قاع نطاق صامد + RSI مضغوط + دخول أموال هادئ (Taker-buy + حجم) + شرارة خضراء → BUY.
"""
import asyncio, time, logging, uuid
from datetime import datetime

import httpx

log = logging.getLogger("spot_scout")

SPOT = "https://api.binance.com"
UNIVERSE_N   = 120          # أعلى الأزواج سيولةً
UNIVERSE_TTL = 3600         # تحديث الكون كل ساعة
CYCLE        = 300          # دورة فحص كل 5 دقائق
COOLDOWN     = 4 * 3600     # لكل رمز بعد إشارة
_last_sig: dict = {}
_universe: list = []
_uni_ts = 0.0
_EXCLUDE = ("UP", "DOWN", "BULL", "BEAR")   # روافع سبوت المغلفة


def _fmt_px(p):
    return f"{p:.2f}" if p>=100 else f"{p:.3f}" if p>=1 else f"{p:.4f}" if p>=0.01 else f"{p:.6f}"


def _rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    gains = losses = 0.0
    for i in range(-period, 0):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0); losses += max(-d, 0)
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return 100 - 100 / (1 + rs)


async def _universe_refresh(c: httpx.AsyncClient):
    global _universe, _uni_ts
    if _universe and time.time() - _uni_ts < UNIVERSE_TTL:
        return
    r = await c.get(f"{SPOT}/api/v3/ticker/24hr", timeout=15)
    rows = [x for x in r.json()
            if x.get("symbol", "").endswith("USDT")
            and not any(t in x["symbol"] for t in _EXCLUDE)
            and float(x.get("quoteVolume", 0) or 0) > 0]
    rows.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
    _universe = [x["symbol"] for x in rows[:UNIVERSE_N]]
    _uni_ts = time.time()
    log.info("🪙 كون السبوت: %d زوجاً (سيولة أعلى)", len(_universe))


async def _scan_one(c: httpx.AsyncClient, sym: str):
    if time.time() - _last_sig.get(sym, 0) < COOLDOWN:
        return
    try:  # حارس ضد التكرار: عملة لها إشارة سبوت نشطة لا تُعاد
        from db.database import get_session, Signal
        _db = get_session()
        try:
            if _db.query(Signal).filter(Signal.radar_type == "spot",
                                        Signal.symbol == sym, Signal.is_active == True).first():
                _last_sig[sym] = time.time()
                return
        finally:
            _db.close()
    except Exception:
        pass
    r = await c.get(f"{SPOT}/api/v3/klines?symbol={sym}&interval=4h&limit=60", timeout=10)
    k = r.json()
    if not isinstance(k, list) or len(k) < 50:
        return
    closes = [float(x[4]) for x in k]
    highs  = [float(x[2]) for x in k]
    lows   = [float(x[3]) for x in k]
    vols   = [float(x[5]) for x in k]
    tbuys  = [float(x[9]) for x in k]
    price  = closes[-1]
    pk, lo = max(highs), min(lows)
    rng = pk - lo
    if rng <= 0 or price <= 0:
        return
    range_pos = (price - lo) / rng

    # ① الثلث السفلي  ② RSI مضغوط  ③ قاع صامد  ④ بصمة تجميع  ⑤ شرارة
    if range_pos > 0.45:
        return
    rsi_v = _rsi(closes)
    if not (20 <= rsi_v <= 52):
        return
    if min(lows[-6:]) < lo * 0.985:
        return  # كسر قاعٍ جديد — ليس صموداً
    v8, t8 = sum(vols[-8:]), sum(tbuys[-8:])
    taker = (t8 / v8) if v8 > 0 else 0
    v_avg = sum(vols[-48:-8]) / 40 if len(vols) >= 48 else (sum(vols[:-8]) / max(1, len(vols) - 8))
    v_infl = (v8 / 8) / v_avg if v_avg > 0 else 0
    if taker < 0.50 or v_infl < 1.08:
        return
    log.info("🪙🔎 مرشّح قريب: %s taker=%.0f%% vol=%.2fx rsi=%.0f pos=%.0f%%",
             sym, taker*100, v_infl, rsi_v, range_pos*100)
    if closes[-1] < sum(closes[-6:-1]) / 5 * 0.99:
        return  # لا شرارة خضراء فوق المتوسط القريب

    grade = "A" if (taker >= 0.55 and v_infl >= 1.30) else "B"
    if taker < 0.51 or v_infl < 1.10:
        return  # نبثّ A والقوي من B — انتقاء عالٍ بفرص أكثر

    entry = price
    sl    = lo * 0.985
    tp1, tp2, tp3 = entry * 1.06, entry * 1.12, entry * 1.20
    conf  = min(95, 60 + (taker - 0.52) * 400 + (v_infl - 1.15) * 20)
    _last_sig[sym] = time.time()

    strategies = ("🪙 Spot Accumulation\n"
                  "قاع_نطاق_صامد\n"
                  "تجميع_هادئ_بالقاع\n"
                  "ضغط_شراء_عام\n"
                  f"RSI مضغوط ({rsi_v:.0f})")

    log.info("🪙🎯 SPOT SIGNAL: %s BUY @%.6g grade=%s taker=%.0f%% vol=%.2fx rsi=%.0f",
             sym, entry, grade, taker * 100, v_infl, rsi_v)
    try:
        from quant_engine.spot_brain import record_spot_signal, predict_spot
        _pp, _note = predict_spot(taker, v_infl, rsi_v, range_pos)
        log.info("🪙🧠 توقّع النموذج: %s نجاح %.0f%% | %s", sym, _pp * 100, _note)
        record_spot_signal(sym, taker, v_infl, rsi_v, range_pos)
    except Exception as _be:
        log.debug("spot brain: %s", _be)

    # ── حفظ للميني آب (معزول: radar_type='spot') ──
    try:
        from db.database import get_session, Signal
        db = get_session()
        try:
            db.add(Signal(id=str(uuid.uuid4()), radar_type="spot", symbol=sym,
                          direction="LONG", grade=grade, score=round(v_infl, 2),
                          confidence=round(conf, 1), entry=entry, sl=sl,
                          tp1=tp1, tp2=tp2, tp3=tp3, leverage=None,
                          strategies=strategies, is_active=True,
                          created_at=datetime.utcnow()))
            db.commit()
        finally:
            db.close()
    except Exception as _se:
        log.error("❌ Spot save FAILED %s: %s", sym, _se)

    # ── بثّ لقناة السبوت ──
    try:
        from services.telegram import send_message
        from core.config import get_settings
        ch = get_settings().telegram_spot_channel_id
        if ch:
            await send_message(ch,
                f"🪙 <b>WhaleX Spot — BUY</b>\n"
                f"⚡ <b>{sym}</b>  ·  قاع تجميع مؤكّد\n\n"
                f"Entry  <b>{_fmt_px(entry)}</b>\n"
                f"Stop   {_fmt_px(sl)}\n"
                f"TP1    {_fmt_px(tp1)}  (+6%)\n"
                f"TP2    {_fmt_px(tp2)}  (+12%)\n"
                f"TP3    {_fmt_px(tp3)}  (+20%)\n\n"
                f"Grade <b>{grade}</b> · Conf <b>{conf:.0f}%</b> · RSI {rsi_v:.0f}\n"
                f"Taker-Buy <b>{taker*100:.0f}%</b> · Volume <b>{v_infl:.2f}x</b>\n"
                f"🐋 <i>WhaleMind Spot</i>")
    except Exception as _te:
        log.error("spot channel send: %s", _te)

    # ── تنفيذ حقيقي على Binance Spot (لمن فعّل المفتاح ولديه رصيد Spot) ──
    try:
        from services.binance_trader import get_active_spot_traders, execute_spot_buy
        for _uid in get_active_spot_traders():
            _rr = await execute_spot_buy(_uid, {"symbol": sym, "entry": entry})
            if not _rr.get("success"):
                log.info("🪙⚠️ Spot buy skip %s: %s", sym, _rr.get("error"))
                try:
                    from services.telegram import send_message
                    from core.config import get_settings as _gs
                    _adm = _gs().telegram_admin_chat_id
                    if _adm:
                        await send_message(_adm, f"🪙⚠️ <b>سبوت</b> {sym}: تعذّر التنفيذ الحقيقي\n<code>{_rr.get('error')}</code>")
                except Exception:
                    pass
    except Exception as _ee:
        log.error("spot auto-exec: %s", _ee)


_prices: dict = {}          # كاش أسعار السبوت (يحدّثه المتتبع كل دقيقة — تقرؤه الواجهة)
_track: dict = {}           # sig_id -> stage (0 لم يلمس، 1/2 بعد TP1/TP2)
_peak: dict = {}            # sig_id -> أعلى سعر بلغته الصفقة (للقفل المتحرك وكشف الانعكاس)
_TRACK_STARTED = False


def _ensure_results_table():
    try:
        import sqlite3
        cx = sqlite3.connect("/opt/whalex/db/whalex.db")
        cx.execute("""CREATE TABLE IF NOT EXISTS spot_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, entry REAL,
            exit_price REAL, pnl_pct REAL, outcome INTEGER, reason TEXT, ts INTEGER)""")
        cx.commit(); cx.close()
    except Exception as _e:
        log.debug("results table: %s", _e)


async def _ws_price_feed():
    # تيار أسعار حي عبر WebSocket لكل عملات السبوت
    import json
    url = "wss://stream.binance.com:9443/ws/!ticker@arr"
    while True:
        try:
            import websockets
            async with websockets.connect(url, ping_interval=20, close_timeout=5) as ws:
                log.info("🪙🔌 Spot WS connected")
                async for msg in ws:
                    try:
                        for t in json.loads(msg):
                            s = t.get("s"); pr = t.get("c")
                            if s and pr: _prices[s] = float(pr)
                    except Exception: pass
        except Exception as e:
            log.warning("🪙🔌 Spot WS drop: %s", e)
            await asyncio.sleep(10)


async def tracker_loop():
    """📡 متتبع مصير الإشارات: TP متدرج، SL صادق، تنظيف 72 ساعة."""
    log.info("🪙📡 Spot tracker starting")
    _ensure_results_table()
    from db.database import get_session, Signal
    from core.config import get_settings
    from services.telegram import send_message
    ch = get_settings().telegram_spot_channel_id
    asyncio.create_task(_ws_price_feed())
    _last_rest = 0.0
    async with httpx.AsyncClient() as c:
        while True:
            try:
                if time.time() - _last_rest > 60:
                    _last_rest = time.time()
                    try:
                        r = await c.get(f"{SPOT}/api/v3/ticker/price", timeout=15)
                        for row in r.json():
                            _prices.setdefault(row["symbol"], float(row["price"]))
                    except Exception: pass

                db = get_session()
                try:
                    sigs = db.query(Signal).filter(Signal.radar_type == "spot",
                                                   Signal.is_active == True).all()
                    now = time.time()
                    for s in sigs:
                        px = _prices.get(s.symbol)
                        if not px:
                            continue
                        st = _track.get(s.id)
                        if st is None:  # أول رؤية (أو بعد restart): هيّئ الطور بصمت
                            st = 2 if px >= s.tp2 else (1 if px >= s.tp1 else 0)
                            _track[s.id] = st
                        age = now - (s.created_at.timestamp() if s.created_at else now)
                        pnl = (px - s.entry) / s.entry * 100 if s.entry else 0.0

                        async def _announce(txt):
                            if ch:
                                try: await send_message(ch, txt)
                                except Exception as _te: log.debug("spot ann: %s", _te)

                        def _log_result(outcome, reason):
                            try:
                                import sqlite3
                                cx = sqlite3.connect("/opt/whalex/db/whalex.db")
                                cx.execute("INSERT INTO spot_results(symbol,entry,exit_price,pnl_pct,outcome,reason,ts) VALUES(?,?,?,?,?,?,?)",
                                           (s.symbol, s.entry, px, round(pnl, 2), outcome, reason, int(now)))
                                cx.commit(); cx.close()
                            except Exception as _re:
                                log.debug("spot result: %s", _re)

                        # 🔒 تتبّع القمة + رفع الوقف عند كل هدف (قفل الربح)
                        _pk = _peak.get(s.id, s.entry)
                        if px > _pk:
                            _pk = px; _peak[s.id] = px
                        _locked_sl = s.sl
                        if px >= s.tp2:
                            _locked_sl = max(_locked_sl, s.entry * 1.06)   # قفل +6%
                        elif px >= s.tp1:
                            _locked_sl = max(_locked_sl, s.entry)          # تعادل
                        # 🧠 كشف انعكاس ذكي: في ربح، وارتد ≥1.5% عن القمة بزخم أحمر → إغلاق فوري
                        _peak_pnl = (_pk - s.entry) / s.entry * 100 if s.entry else 0
                        _drop = (_pk - px) / _pk * 100 if _pk else 0
                        _smart_rev = (pnl >= 2.0 and _peak_pnl >= 4.0 and _drop >= 1.5)

                        if _smart_rev:
                            s.is_active = False; db.commit()
                            _log_result(1 if pnl > 0 else 0, "reversal")
                            try:
                                from services.binance_trader import close_spot_all
                                await close_spot_all(s.symbol, "reversal")
                            except Exception: pass
                            try:
                                from quant_engine.spot_brain import record_spot_outcome
                                record_spot_outcome(s.symbol, 1 if pnl > 0 else 0, pnl)
                            except Exception: pass
                            await _announce(f"🧠 <b>{s.symbol}</b> — انعكاس مُكتشف، أغلقنا لحفظ الربح\nالنتيجة: <b>{pnl:+.1f}%</b> (القمة كانت {_peak_pnl:+.0f}%)\n🪙 <i>WhaleMind Spot</i>")
                            log.info("🪙🧠 %s reversal-exit %.1f%% (peak %.0f%%)", s.symbol, pnl, _peak_pnl)
                        elif px <= _locked_sl and _locked_sl > s.sl:
                            s.is_active = False; db.commit()
                            _log_result(1 if pnl > 0 else 0, "locked")
                            try:
                                from services.binance_trader import close_spot_all
                                await close_spot_all(s.symbol, "locked")
                            except Exception: pass
                            try:
                                from quant_engine.spot_brain import record_spot_outcome
                                record_spot_outcome(s.symbol, 1 if pnl > 0 else 0, pnl)
                            except Exception: pass
                            await _announce(f"🔒 <b>{s.symbol}</b> — قفل الربح عند الارتداد\nالنتيجة: <b>{pnl:+.1f}%</b>\n🪙 <i>WhaleMind Spot</i>")
                            log.info("🪙🔒 %s locked %.1f%%", s.symbol, pnl)
                        elif px <= s.sl:
                            s.is_active = False; db.commit()
                            _log_result(0, "sl")
                            try:
                                from services.binance_trader import close_spot_all
                                await close_spot_all(s.symbol, "sl")
                            except Exception: pass
                            try:
                                from quant_engine.spot_brain import record_spot_outcome
                                record_spot_outcome(s.symbol, 0, pnl)
                            except Exception: pass
                            await _announce(f"🔴 <b>{s.symbol}</b> — ضرب الوقف\nالنتيجة: <b>{pnl:+.1f}%</b>\n🪙 <i>WhaleMind Spot</i>")
                            log.info("🪙🔴 %s SL %.1f%%", s.symbol, pnl)
                        elif px >= s.tp3:
                            s.is_active = False; db.commit()
                            _log_result(1, "tp3")
                            try:
                                from services.binance_trader import close_spot_all
                                await close_spot_all(s.symbol, "tp3")
                            except Exception: pass
                            try:
                                from quant_engine.spot_brain import record_spot_outcome
                                record_spot_outcome(s.symbol, 1, pnl)
                            except Exception: pass
                            await _announce(f"🏆 <b>{s.symbol}</b> — الهدف الثالث!\nالنتيجة: <b>{pnl:+.1f}%</b> 🎉\n🪙 <i>WhaleMind Spot</i>")
                            log.info("🪙🏆 %s TP3 %.1f%%", s.symbol, pnl)
                        elif px >= s.tp2 and st < 2:
                            _track[s.id] = 2
                            await _announce(f"🎯 <b>{s.symbol}</b> — الهدف الثاني (+12%)\nنواصل نحو الثالث 🚀")
                        elif px >= s.tp1 and st < 1:
                            _track[s.id] = 1
                            await _announce(f"✅ <b>{s.symbol}</b> — الهدف الأول (+6%)\nربح مؤمّن، نواصل 📈")
                        elif age > 72 * 3600 and st == 0:
                            s.is_active = False; db.commit()
                            _log_result(0, "expired")
                            log.info("🪙⌛ %s expired %.1f%%", s.symbol, pnl)
                finally:
                    db.close()
            except Exception as e:
                log.error("spot tracker: %s", e)
            await asyncio.sleep(3)


async def spot_loop():
    """حلقة العقل — قائمة بذاتها، أخطاؤها لا تغادرها."""
    log.info("🪙 Spot brain v1 starting")
    global _TRACK_STARTED
    if not _TRACK_STARTED:
        _TRACK_STARTED = True
        asyncio.create_task(tracker_loop())
    async with httpx.AsyncClient() as c:
        while True:
            try:
                await _universe_refresh(c)
                sem = asyncio.Semaphore(6)
                async def _g(s):
                    async with sem:
                        try:
                            await _scan_one(c, s)
                        except Exception as _e:
                            log.debug("spot scan %s: %s", s, _e)
                        await asyncio.sleep(0.15)
                await asyncio.gather(*[_g(s) for s in list(_universe)])
            except Exception as e:
                log.error("spot_loop: %s", e)
            await asyncio.sleep(CYCLE)
