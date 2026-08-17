"""🌐 ماسح المنصّات — العملات الحصرية (غير الموجودة على باينانس)

📊 الكون: 68 عقداً دائماً على 6 منصّات (مقيس 17 أغسطس 2026)
   بيتجت 30 · باي بيت 28 · مكسي 25 · جيت 25 · بينج إكس 10
   يدعم OI: 41 | بلا OI: 27 (مكسي وجيت)

رادار واحد لكل المنصّات — بنية المُهايئات توحّد الواجهة.
المصادر نفس رادارك: klines · order book · funding · OI
الإشارة تحمل المنصّة: 🌐 KORUUSDT SHORT 📍 بيتجت
"""
import asyncio
import logging
import time

log = logging.getLogger("multi_scan")

CYCLE = 300
BATCH = 12
BATCH_PAUSE = 3.0
COOLDOWN = 5400

SCORE_MIN = 5.5
MIN_ATR_PCT = 0.5
MAX_SL_PCT = 8.0

W_RSI = 2.0
W_RANGE = 2.0
W_VOL = 1.5
W_WALL = 2.0
W_FUNDING = 1.5

_last: dict = {}
STATS: dict = {}
_KEYS = ("checked", "no_data", "flat", "weak_score", "wide_sl", "cooldown", "emitted")


def _hit(k):
    STATS[k] = STATS.get(k, 0) + 1


def stats_snapshot():
    s = {k: STATS.get(k, 0) for k in _KEYS}
    STATS.clear()
    return s


def _rsi(closes: list, n: int = 14) -> float:
    if len(closes) < n + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains[-n:]) / n
    al = sum(losses[-n:]) / n
    if al == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + ag / al))


def _atr_pct(highs: list, lows: list, closes: list, n: int = 14) -> float:
    if len(closes) < n + 1:
        return 0.0
    trs = []
    for i in range(1, len(closes)):
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]),
                       abs(lows[i] - closes[i - 1])))
    atr = sum(trs[-n:]) / n
    return (atr / closes[-1] * 100) if closes[-1] else 0.0


def _range_pos(highs: list, lows: list, price: float, n: int = 48) -> float:
    hi = max(highs[-n:]) if highs else price
    lo = min(lows[-n:]) if lows else price
    return ((price - lo) / (hi - lo)) if hi > lo else 0.5


async def _read(client, ccxt_symbol: str, wants_oi: bool) -> dict:
    out = {}
    try:
        k = await asyncio.to_thread(client.fetch_ohlcv, ccxt_symbol, "15m", None, 60)
        if not k or len(k) < 30:
            return {}
        out["highs"] = [float(x[2]) for x in k]
        out["lows"] = [float(x[3]) for x in k]
        out["closes"] = [float(x[4]) for x in k]
        out["vols"] = [float(x[5]) for x in k]
    except Exception as e:
        log.debug("klines %s: %s", ccxt_symbol, e)
        return {}
    try:
        ob = await asyncio.to_thread(client.fetch_order_book, ccxt_symbol, 50)
        out["bids"] = [(float(p), float(q)) for p, q in (ob.get("bids") or [])]
        out["asks"] = [(float(p), float(q)) for p, q in (ob.get("asks") or [])]
    except Exception:
        out["bids"] = out["asks"] = []
    try:
        fr = await asyncio.to_thread(client.fetch_funding_rate, ccxt_symbol)
        out["funding"] = float(fr.get("fundingRate") or 0)
    except Exception:
        out["funding"] = 0.0
    return out


def _score(d: dict) -> tuple:
    closes = d["closes"]
    price = closes[-1]
    rsi = _rsi(closes)
    rpos = _range_pos(d["highs"], d["lows"], price)
    atrp = _atr_pct(d["highs"], d["lows"], closes)
    vols = d["vols"]
    vol_ratio = (vols[-1] / (sum(vols[-20:-1]) / 19)) if len(vols) > 20 and sum(vols[-20:-1]) > 0 else 1.0
    bids, asks = d.get("bids") or [], d.get("asks") or []
    bv = sum(p * q for p, q in bids[:20])
    av = sum(p * q for p, q in asks[:20])
    imb = ((bv - av) / (bv + av)) if (bv + av) > 0 else 0.0
    fund = d.get("funding", 0.0)

    sp, lp = 0.0, 0.0
    rs, rl = [], []
    if 65 <= rsi <= 80:
        sp += W_RSI; rs.append(f"RSI {rsi:.0f}")
    elif 20 <= rsi <= 38:
        lp += W_RSI; rl.append(f"RSI {rsi:.0f}")
    if rpos >= 0.72:
        sp += W_RANGE; rs.append(f"قمة النطاق {rpos*100:.0f}%")
    elif rpos <= 0.28:
        lp += W_RANGE; rl.append(f"قاع النطاق {rpos*100:.0f}%")
    if vol_ratio >= 1.5:
        sp += W_VOL; lp += W_VOL
        rs.append(f"حجم ×{vol_ratio:.1f}"); rl.append(f"حجم ×{vol_ratio:.1f}")
    if imb <= -0.20:
        sp += W_WALL; rs.append(f"جدار بيع {imb*100:.0f}%")
    elif imb >= 0.20:
        lp += W_WALL; rl.append(f"جدار شراء {imb*100:+.0f}%")
    if fund > 0.0004:
        sp += W_FUNDING; rs.append(f"تمويل {fund*100:.3f}%")
    elif fund < -0.0002:
        lp += W_FUNDING; rl.append(f"تمويل {fund*100:.3f}%")

    if sp >= lp:
        return round(sp, 2), "SHORT", rs, rsi, rpos, atrp, vol_ratio
    return round(lp, 2), "LONG", rl, rsi, rpos, atrp, vol_ratio


def _levels(price: float, direction: str, atr_pct: float) -> dict:
    sl_pct = max(2.0, min(MAX_SL_PCT, atr_pct * 2.0))
    risk = price * sl_pct / 100
    if direction == "SHORT":
        return {"sl": price + risk, "tp1": price - risk * 1.5,
                "tp2": price - risk * 3.0, "tp3": price - risk * 5.0,
                "sl_pct": sl_pct}
    return {"sl": price - risk, "tp1": price + risk * 1.5,
            "tp2": price + risk * 3.0, "tp3": price + risk * 5.0,
            "sl_pct": sl_pct}


async def _emit(row, sc, direction, reasons, price, lv, rsi, rpos, vr, pm_fn):
    from radars.futures.engine import Signal
    from services.exchanges import get as get_adapter
    ad = get_adapter(row["exchange"])
    lev = max(3.0, min(10.0, round(10.0 / lv["sl_pct"], 1)))
    sig = Signal(
        symbol=row["symbol"], direction=direction, grade="A",
        score=sc, confidence=round(min(92.0, 60.0 + sc * 4), 1),
        entry=price, sl=round(lv["sl"], 8), tp1=round(lv["tp1"], 8),
        tp2=round(lv["tp2"], 8), tp3=round(lv["tp3"], 8), leverage=lev,
        strategies="\n".join([f"🌐 {ad.name_en} · {ad.name_ar}"] + reasons),
        radar_type="futures", tier="MX",
        rr_tp1=1.5, rr_tp2=3.0, rr_tp3=5.0,
        strategy_count=len(reasons), btc_trend="NEUTRAL",
        rsi=round(rsi, 2), range_pos=round(rpos, 4), volume_ratio=round(vr, 2),
    )
    try:
        from ml_recorder import record_signal
        record_signal(sig)
    except Exception as e:
        log.debug("MX record: %s", e)
    # 📱 حفظ في جدول signals — بلاه لا تظهر في «الإشارات الحيّة» بالتطبيق
    try:
        from radars.futures.service import save_signal
        await save_signal(sig)
    except Exception as e:
        log.error("MX save_signal: %s", e)
    log.info("🌐📡 إشارة: %s %s @%.6g | %s | نقاط %.1f | %s",
             row["symbol"], direction, price, ad.name_en, sc, " · ".join(reasons))
    msg = (
        f"🌐 <b>WhaleX Multi</b> — عملة حصرية\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <code>{row['symbol']}</code>  {direction}\n"
        f"📍 <b>{ad.name_en}</b> ({ad.name_ar})\n\n"
        f"Entry   <code>{price:.6g}</code>\n"
        f"Stop    <code>{lv['sl']:.6g}</code>  ({lv['sl_pct']:.1f}%)\n"
        f"TP1     <code>{lv['tp1']:.6g}</code>\n"
        f"TP2     <code>{lv['tp2']:.6g}</code>\n"
        f"TP3     <code>{lv['tp3']:.6g}</code>\n\n"
        f"Lev <b>{lev:.1f}x</b> · نقاط <b>{sc:.1f}</b>/10\n"
        f"حجم 24س: ${row['volume_24h']:,.0f}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(f"✅ {x}" for x in reasons) +
        f"\n━━━━━━━━━━━━━━━━━━━\n🐋 <i>WhaleMind Prime</i>"
    )
    try:
        from services.telegram import send_message
        from core.config import get_settings
        ch = get_settings().telegram_channel_futures
        if ch:
            await send_message(ch, msg)
    except Exception as e:
        log.error("MX broadcast: %s", e)
    _last[row["symbol"]] = time.time()
    _hit("emitted")
    if pm_fn:
        try:
            await pm_fn(sig)
        except Exception as e:
            log.error("MX open %s: %s", row["symbol"], e)


async def multi_scan_loop(position_manager_fn=None):
    from radars.multi.universe import refresh, load
    from services.exchanges import get as get_adapter
    log.info("🌐 WhaleX Multi بدأ — العملات الحصرية على 6 منصّات")
    _clients = {}
    _last_refresh = 0.0
    while True:
        try:
            if time.time() - _last_refresh > 3600:
                await asyncio.to_thread(refresh)
                _last_refresh = time.time()
            rows = load()
            if not rows:
                await asyncio.sleep(CYCLE)
                continue
            for i in range(0, len(rows), BATCH):
                for row in rows[i:i + BATCH]:
                    _hit("checked")
                    sym = row["symbol"]
                    if time.time() - _last.get(sym, 0) < COOLDOWN:
                        _hit("cooldown")
                        continue
                    ex = row["exchange"]
                    try:
                        if ex not in _clients:
                            _clients[ex] = get_adapter(ex).client("", "", futures=True)
                        d = await _read(_clients[ex], row["ccxt_symbol"],
                                        bool(row["supports_oi"]))
                        if not d:
                            _hit("no_data")
                            continue
                        sc, direction, reasons, rsi, rpos, atrp, vr = _score(d)
                        if atrp < MIN_ATR_PCT:
                            _hit("flat")
                            continue
                        if sc < SCORE_MIN:
                            _hit("weak_score")
                            continue
                        price = d["closes"][-1]
                        lv = _levels(price, direction, atrp)
                        if lv["sl_pct"] > MAX_SL_PCT:
                            _hit("wide_sl")
                            continue
                        await _emit(row, sc, direction, reasons, price, lv,
                                    rsi, rpos, vr, position_manager_fn)
                    except Exception as e:
                        log.debug("MX %s: %s", sym, e)
                await asyncio.sleep(BATCH_PAUSE)
            st = stats_snapshot()
            if st.get("checked"):
                log.info("🌐 فُحص %d | بلا داتا %d | ساكنة %d | نقاط %d | وقف واسع %d | تهدئة %d | صدر %d",
                         st["checked"], st["no_data"], st["flat"], st["weak_score"],
                         st["wide_sl"], st["cooldown"], st["emitted"])
        except Exception as e:
            log.warning("MX loop: %s", e)
        await asyncio.sleep(CYCLE)
