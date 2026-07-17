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
    if range_pos > 0.30:
        return
    rsi_v = _rsi(closes)
    if not (25 <= rsi_v <= 45):
        return
    if min(lows[-6:]) < lo * 0.995:
        return  # كسر قاعٍ جديد — ليس صموداً
    v8, t8 = sum(vols[-8:]), sum(tbuys[-8:])
    taker = (t8 / v8) if v8 > 0 else 0
    v_avg = sum(vols[-48:-8]) / 40 if len(vols) >= 48 else (sum(vols[:-8]) / max(1, len(vols) - 8))
    v_infl = (v8 / 8) / v_avg if v_avg > 0 else 0
    if taker < 0.52 or v_infl < 1.15:
        return
    if closes[-1] <= float(k[-1][1]) or closes[-1] <= sum(closes[-6:-1]) / 5:
        return  # لا شرارة خضراء فوق المتوسط القريب

    grade = "A" if (taker >= 0.55 and v_infl >= 1.30) else "B"
    if grade != "A":
        return  # v1: نبثّ النخبة فقط

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
                f"Entry  <b>{entry:.6g}</b>\n"
                f"Stop   {sl:.6g}\n"
                f"TP1    {tp1:.6g}  (+6%)\n"
                f"TP2    {tp2:.6g}  (+12%)\n"
                f"TP3    {tp3:.6g}  (+20%)\n\n"
                f"Grade <b>{grade}</b> · Conf <b>{conf:.0f}%</b> · RSI {rsi_v:.0f}\n"
                f"Taker-Buy <b>{taker*100:.0f}%</b> · Volume <b>{v_infl:.2f}x</b>\n"
                f"🐋 <i>WhaleMind Spot</i>")
    except Exception as _te:
        log.error("spot channel send: %s", _te)


async def spot_loop():
    """حلقة العقل — قائمة بذاتها، أخطاؤها لا تغادرها."""
    log.info("🪙 Spot brain v1 starting")
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
