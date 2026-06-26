# ═══════════════════════════════════════════════════════════════
# EXPLOSION SCOUT — رادار الطبقة الثانية (كشّاف الانفجار)
# النوع 1: SHORT من القمم (الأعلى ربحاً → تنهار → نصطاد الانهيار)
#
# الفلسفة:
#   1. فرز دفعة (طلب واحد) → الأعلى ربحاً
#   2. كشف القمة + بداية ضعف → 🚨 تنبيه واحد فقط ("بدأنا المراقبة")
#   3. مراقبة صامتة عميقة (Order Book، تآكل bids، جدران) — لا رسائل
#   4. لحظة انهيار OB الوشيك → 🔻 إشارة SHORT نظامية + المدير
# ═══════════════════════════════════════════════════════════════
import asyncio
import logging
import sqlite3
import time
import httpx

from radars.futures.engine import (
    fetch_klines_async, rsi, stoch_rsi, macd, range_position, atr, Signal,
)

log = logging.getLogger("explosion_scout")
DB_PATH = "/opt/whalex/explosion.db"

# ─── إعدادات ───
MIN_VOLUME_USD = 15_000_000
MIN_GAIN_PCT = 30.0
LEVEL1_INTERVAL = 300         # فرز الأعلى ربحاً: كل 5 دقائق
LEVEL2_INTERVAL = 45          # مراقبة المرشّحين: كل 45 ثانية (سريع)
COOLDOWN_SIGNAL = 3600        # ساعة بين إشارتين لنفس العملة

# ═══════════════════════════════════════════════════════════════
# مقابض المعايرة (0-100): نبدأ من الوسط 50، نرفع=تساهل، ننزل=تشدد
#   المرحلة 1: عين الصقر (الفرز والدراسة)
#   المرحلة 2: الرادار (مراقبة الأوردر بوك والانهيار)
# ═══════════════════════════════════════════════════════════════
HAWK_SENSITIVITY = 0    # عين الصقر: 100=تسمح بكل شيء، 0=تمنع أي صعود
RADAR_SENSITIVITY = 50   # الرادار: 100=أي ضعف إشارة، 0=انهيار قوي جداً فقط

# تتبّع قراءة OB السابقة (لكشف التآكل)
PREV_OB = {}


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            symbol TEXT PRIMARY KEY,
            gain_pct REAL, volume_usd REAL,
            peak_price REAL, added_at INTEGER,
            last_check INTEGER, status TEXT DEFAULT 'watching',
            signal_sent INTEGER DEFAULT 0,
            alert_sent INTEGER DEFAULT 0
        )
    """)
    # ترقية: إضافة alert_sent إن لم يوجد
    try:
        conn.execute("ALTER TABLE watchlist ADD COLUMN alert_sent INTEGER DEFAULT 0")
    except Exception:
        pass
    conn.commit()
    conn.close()


async def fetch_top_gainers() -> list[dict]:
    """المستوى 1: كل العملات بطلب واحد + فلتر."""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://fapi.binance.com/fapi/v1/ticker/24hr")
            data = r.json()
        out = []
        for d in data:
            if not d["symbol"].endswith("USDT"):
                continue
            gain = float(d["priceChangePercent"])
            vol = float(d["quoteVolume"])
            if gain >= MIN_GAIN_PCT and vol >= MIN_VOLUME_USD:
                out.append({"symbol": d["symbol"], "gain": gain,
                            "volume": vol, "price": float(d["lastPrice"])})
        return sorted(out, key=lambda x: x["gain"], reverse=True)
    except Exception as e:
        log.error("fetch_top_gainers error: %s", e)
        return []


async def fetch_ob_deep(symbol: str) -> dict:
    """تحليل Order Book العميق (500 مستوى): جدران، اختلال، تمييز الجدار الوهمي."""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"https://fapi.binance.com/fapi/v1/depth?symbol={symbol}&limit=500")
            d = r.json()
        bids_raw = [(float(b[0]), float(b[1])) for b in d.get("bids", [])]
        asks_raw = [(float(a[0]), float(a[1])) for a in d.get("asks", [])]
        if not bids_raw or not asks_raw:
            return {"valid": False}
        bid_vol = sum(b[1] for b in bids_raw)
        ask_vol = sum(a[1] for a in asks_raw)
        total = bid_vol + ask_vol
        imbalance = (bid_vol - ask_vol) / total if total > 0 else 0
        max_ask_wall = max((a[1] for a in asks_raw), default=0)
        avg_ask = ask_vol / len(asks_raw) if asks_raw else 0
        sell_wall_ratio = max_ask_wall / avg_ask if avg_ask > 0 else 0
        max_bid_wall = max((b[1] for b in bids_raw), default=0)
        avg_bid = bid_vol / len(bids_raw) if bids_raw else 0
        bid_wall_ratio = max_bid_wall / avg_bid if avg_bid > 0 else 0
        near_ask = sum(a[1] for a in asks_raw[:10])
        near_bid = sum(b[1] for b in bids_raw[:10])
        near_imb = (near_bid - near_ask) / (near_bid + near_ask) if (near_bid + near_ask) > 0 else 0
        return {
            "valid": True,
            "imbalance": imbalance,
            "near_imbalance": near_imb,
            "sell_wall_ratio": sell_wall_ratio,
            "bid_wall_ratio": bid_wall_ratio,
            "sell_pressure": ask_vol / total if total > 0 else 0.5,
            "bid_vol": bid_vol,
            "ask_vol": ask_vol,
            "max_ask_wall": max_ask_wall,
            "max_bid_wall": max_bid_wall,
        }
    except Exception:
        return {"valid": False}


async def classify_wall(symbol: str, side: str = "ask") -> dict:
    """تمييز الجدار عبر المحلل الاحترافي الموحّد (order_book_analyzer).
    يكشف spoofing (وهمي) + iceberg (جبل ثلجي). نظام واحد، لا تكرار."""
    try:
        from quant_engine.order_book_analyzer import analyze_order_book
        a = await analyze_order_book(symbol, check_spoofing=True)
        if not a:
            return {"type": "غير_معروف", "valid": False}
        spoof = getattr(a, "spoofing_detected", False)
        spoof_side = getattr(a, "spoofing_side", "none")
        iceberg = getattr(a, "iceberg_detected", False)
        walls = a.bid_walls if side == "bid" else a.ask_walls
        if spoof and spoof_side == side:
            wtype = "وهمي"
        elif iceberg:
            wtype = "جبل_ثلجي"
        elif walls:
            wtype = "حقيقي"
        else:
            wtype = "لا_جدار"
        return {"type": wtype, "valid": True,
                "spoofing": spoof, "iceberg": iceberg}
    except Exception as _e:
        log.debug("classify_wall unified %s: %s", symbol, _e)
        return {"type": "غير_معروف", "valid": False}


def cvd_flow(candles) -> float:
    flow = 0.0
    for c in candles[-14:]:
        bv = getattr(c, "buy_volume", c.volume / 2)
        flow += (bv - (c.volume - bv))
    return flow


def is_clean_top(candles) -> bool:
    """قمة نظيفة (لا تذبذب فوضوي): صعدت بقوة ثم تستقر/تضعف.
    نرفض الفوضى: عدة شمعات ضخمة متناوبة (±3%) = خطر، ليست قمة نظيفة."""
    if len(candles) < 8:
        return False
    big_moves = 0
    for c in candles[-8:]:
        body = abs(c.close - c.open) / c.open if c.open > 0 else 0
        if body > 0.03:  # شمعة ضخمة >3%
            big_moves += 1
    # أكثر من 3 شمعات ضخمة في آخر 8 = تذبذب فوضوي (نرفض)
    return big_moves <= 3


async def detect_top_forming(symbol: str, peak_price: float) -> dict:
    """كشف تشكّل القمة (للتنبيه): قمة + ضعف مبدئي + نظافة."""
    candles = await fetch_klines_async(symbol, "15m", 50)
    if len(candles) < 20:
        return {"forming": False}
    closes = [c.close for c in candles]
    price = closes[-1]
    r = rsi(closes)
    r_prev = rsi(closes[:-3])
    pos = range_position(candles, 20)
    clean = is_clean_top(candles)

    # قمة تتشكّل = موقع عالٍ + RSI كان مرتفعاً + قمة نظيفة (لا فوضى)
    at_top = (pos > 0.72) and (r_prev >= 62 or r >= 62)
    forming = at_top and clean
    return {
        "forming": forming, "clean": clean, "price": price,
        "rsi": r, "rsi_prev": r_prev, "range_pos": pos, "candles": candles,
    }


async def detect_collapse(symbol: str, peak_price: float, candles) -> dict:
    """كشف انهيار OB الوشيك (للإشارة): قراءة عمق دفتر الأوامر."""
    deep = await fetch_ob_deep(symbol)
    prev = PREV_OB.get(symbol)
    PREV_OB[symbol] = deep

    if not deep.get("valid"):
        return {"collapse": False, "signals": []}

    signals = []
    if deep["near_imbalance"] < -0.30:
        signals.append("اختلال_قرب_السعر")
    if deep["sell_wall_ratio"] > 5.0:
        signals.append("جدار_بيع_ضخم")
    if deep["sell_pressure"] > 0.62:
        signals.append("ضغط_بيع_عام")
    if prev and prev.get("valid") and deep["bid_vol"] < prev["bid_vol"] * 0.85:
        signals.append("تآكل_المشترين")

    closes = [c.close for c in candles]
    r = rsi(closes)
    sk, sd = stoch_rsi(closes)

    # ═══ فلتر السلامة اللحظي (المحرّك الاحترافي): يمنع فخّ الشورت ═══
    # بدل شموع 4h المتأخّرة (سبب دخول RIF الصاعدة): نعتمد تحليل OB الاحترافي اللحظي.
    # safe_for_short=False إذا: اختلال شراء قوي، spoofing على ask، جدار شراء يمنع الهبوط.
    ob_safe_short = True
    try:
        from quant_engine.order_book_analyzer import analyze_order_book
        _a = await analyze_order_book(symbol, check_spoofing=True)
        if _a is not None:
            ob_safe_short = _a.safe_for_short
    except Exception as _e:
        log.debug("ob_analyzer %s: %s", symbol, _e)
        ob_safe_short = True

    # ═══ المرحلة 1: عين الصقر — تدرس فقط، لا تقرر ═══
    # تُرجع البروفايل (المرحلة + قرب القمة/القاع). القرار للرادار:
    # Peak Hunter شورت فقط → القمم فقط (near_period_high)،
    # ويرفض القيعان (near_period_low): الشورت قربها متأخّر (مشكلة SIREN).
    hawk_ok = True
    hawk_phase = ""
    hawk_block_reason = ""
    try:
        from quant_engine.hawk_eye import read_market_structure
        ms = await read_market_structure(symbol, fetch_klines_async)
        hawk_phase = ms.phase
        # نافذة بداية الهبوط: نصطاد إذا هبطت 3-10% من القمّة (أكّدت الانعكاس، لم تتأخّر).
        #   <3%: ما زالت عند القمّة، الانعكاس غير مؤكّد. >10%: هبطت كثيراً، شورت متأخّر.
        #   (peak_price = قمّة الرادار المخزّنة، أدقّ من period_high)
        _cur = closes[-1] if closes else 0
        _drop = (peak_price - _cur) / peak_price * 100 if peak_price > 0 else 0
        if _drop < 3.0:
            hawk_ok = False
            hawk_block_reason = f"عند القمّة ({_drop:.1f}% — لم تؤكّد الانعكاس)"
        elif _drop > 10.0:
            hawk_ok = False
            hawk_block_reason = f"هبطت كثيراً ({_drop:.1f}% — شورت متأخّر)"
        # مساحة الهبوط: لا شورت إن كان السعر ملاصقاً للدعم (قاع تصحيح، الارتداد محتمل).
        #   support_distance_pct موجب = فوق الدعم. نطلب مسافة ≥3% (مساحة هبوط أمام السعر).
        elif hawk_ok and 0 <= ms.support_distance_pct < 3.0:
            hawk_ok = False
            hawk_block_reason = f"ملاصق للدعم ({ms.support_distance_pct:.1f}% — قاع تصحيح، ارتداد محتمل)"
    except Exception as _e:
        log.debug("hawk in collapse %s: %s", symbol, _e)
        hawk_ok = True

    # ═══ المرحلة 2: الرادار (مقبض RADAR_SENSITIVITY) ═══
    # يراقب انهيار الشراء/السيولة في الأوردر بوك. المقبض يحدد كم علامة يطلب.
    has_imbalance = "اختلال_قرب_السعر" in signals
    has_erosion = "تآكل_المشترين" in signals      # إلزامي: انهيار طلب حقيقي لا جدار وهمي
    if RADAR_SENSITIVITY >= 70:
        radar_ok = has_imbalance and len(signals) >= 1      # تساهل
    elif RADAR_SENSITIVITY >= 40:
        radar_ok = has_imbalance and len(signals) >= 2   # وسط: اختلال + إشارة ثانية (تآكل مفضّل لا إلزامي)
    else:
        radar_ok = has_imbalance and has_erosion and len(signals) >= 3   # تشدد + تآكل إلزامي

    # القرار اللحظي: انعكاس OB مؤكّد (radar_ok) + قرب القمة (hawk) + لا فخّ (safe_short) + RSI.
    # لا شموع 4h متأخّرة — دخول فوري عند انقلاب الأوردر بوك الحقيقي (رؤية التداول اللحظي).
    _ns=True
    try:
        from quant_engine.ob_stream import get_signals
        _sw=symbol.replace("/","").replace("-","")
        if not _sw.endswith("USDT"): _sw+="USDT"
        if any(x["side"]=="bid" for x in get_signals(_sw).get("spoof",[])): _ns=False
    except Exception: pass
    collapse = radar_ok and hawk_ok and ob_safe_short and r > 45 and _ns

    if radar_ok and not collapse:
        log.debug("🦅 %s: OB إشارات لكن مُنع (hawk=%s safe_short=%s)", symbol, hawk_ok, ob_safe_short)
    return {
        "collapse": collapse, "signals": signals, "deep": deep,
        "rsi": r, "stoch_k": sk, "stoch_d": sd,
    }


def _build_signal(symbol: str, price: float, candles: list, peak: float,
                  ob_signals: list, rsi_v: float) -> Signal:
    """إشارة SHORT نظامية كاملة (SL/TP من ATR) — grade A."""
    atr_v = atr(candles)
    if atr_v <= 0:
        atr_v = price * 0.01
    sl = price + atr_v * 1.5
    tp1 = price - atr_v * 1.5
    tp2 = price - atr_v * 3.0
    tp3 = price - atr_v * 5.0
    risk = abs(price - sl)
    rr1 = abs(tp1 - price) / risk if risk > 0 else 0
    rr2 = abs(tp2 - price) / risk if risk > 0 else 0
    rr3 = abs(tp3 - price) / risk if risk > 0 else 0
    drop = (peak - price) / peak * 100 if peak > 0 else 0
    conf = min(92.0, 72.0 + len(ob_signals) * 5.0)
    strats = ["🔭 Explosion Scout — انهيار OB"] + ob_signals + [f"هبوط من الذروة: -{drop:.1f}%"]
    return Signal(
        symbol=symbol, direction="SHORT", grade="A",
        score=round(6.5 + len(ob_signals) * 0.3, 2),
        confidence=round(conf, 1), entry=price,
        sl=round(sl, 8), tp1=round(tp1, 8), tp2=round(tp2, 8), tp3=round(tp3, 8),
        leverage=3.0, strategies="\n".join(strats), radar_type="futures", tier="PH",
        rr_tp1=round(rr1, 2), rr_tp2=round(rr2, 2), rr_tp3=round(rr3, 2),
        strategy_count=len(strats), btc_trend="NEUTRAL",
        rsi=rsi_v,
    )


async def _send_alert_once(symbol: str, res: dict, peak: float):
    """One-time alert: monitoring started."""
    price = res["price"]
    drop = (peak - price) / peak * 100 if peak > 0 else 0
    msg = (
        f"🎯 <b>PEAK HUNTER</b> — Watch Started\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📡 <code>{symbol}</code>   ▼ {drop:.0f}% from peak\n\n"
        f"Price   <code>{price:.6g}</code>\n"
        f"Peak    <code>{peak:.6g}</code>\n"
        f"RSI     {res['rsi']:.0f}  ·  Position {res['range_pos']:.0%}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 Now reading order-book depth silently.\n"
        f"SHORT signal fires when the book collapses."
    )
    log.info("🔭🚨 PEAK HUNTER alert (once): %s", symbol)
    try:
        from services.telegram import send_message
        from core.config import get_settings
        ch = get_settings().telegram_channel_futures
        if ch:
            await send_message(ch, msg)
    except Exception as e:
        log.error("scout alert error: %s", e)


def _filter_line(name: str, value: str, triggered: bool) -> str:
    icon = "✅" if triggered else "⬜"
    return f"{icon} {name:<16}<code>{value}</code>"


def _save_to_signals_table(sig, strategies_text):
    """يحفظ إشارة Peak Hunter في جدول signals (نفس مصدر الواجهة) بـ radar_type=explosion"""
    try:
        from db.database import get_session, Signal
        db = get_session()
        try:
            row = Signal(
                radar_type="explosion", symbol=sig.symbol, direction=sig.direction,
                grade=sig.grade, score=getattr(sig, "score", 0.0), confidence=sig.confidence,
                entry=sig.entry, sl=sig.sl, tp1=sig.tp1, tp2=sig.tp2, tp3=sig.tp3,
                leverage=sig.leverage, strategies=strategies_text,
            )
            db.add(row); db.commit()
        finally:
            db.close()
    except Exception as _e:
        log.debug("Peak Hunter save_to_signals error: %s", _e)


async def _send_signal_and_open(symbol: str, price: float, candles: list, peak: float,
                                 col: dict, position_manager_fn):
    """Full systematic SHORT signal + open in manager."""
    sig = _build_signal(symbol, price, candles, peak, col["signals"], col["rsi"])
    # تسجيل الإشارة في ml_training (يكمل الحلقة: عند الإغلاق update_result_by_match يجدها)
    try:
        from ml_recorder import record_signal
        record_signal(sig)
    except Exception as _e:
        log.debug("Peak Hunter ml_record error: %s", _e)
    drop = (peak - price) / peak * 100 if peak > 0 else 0
    deep = col["deep"]
    sigs = col["signals"]
    n_trig = len(sigs)

    # detection filters (real values + triggered state)
    near_imb = deep.get("near_imbalance", 0)
    sell_p = deep.get("sell_pressure", 0) * 100
    wall = deep.get("sell_wall_ratio", 0)
    f_imb = _filter_line("Near Imbalance", f"{near_imb:+.2f}", "اختلال_قرب_السعر" in sigs)
    f_prs = _filter_line("Sell Pressure", f"{sell_p:.0f}%", "ضغط_بيع_عام" in sigs)
    f_wal = _filter_line("Sell Wall", f"{wall:.1f}x", "جدار_بيع_ضخم" in sigs)
    f_ero = _filter_line("Buyer Erosion", "yes" if "تآكل_المشترين" in sigs else "no", "تآكل_المشترين" in sigs)
    f_rsi = _filter_line("RSI", f"{col['rsi']:.0f}", col['rsi'] >= 58)

    msg = (
        f"🎯 <b>PEAK HUNTER</b> — 🔻 SHORT\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <code>{symbol}</code>   ▼ {drop:.0f}% from peak\n\n"
        f"Entry   <code>{sig.entry:.6g}</code>\n"
        f"Stop    <code>{sig.sl:.6g}</code>\n"
        f"TP1     <code>{sig.tp1:.6g}</code>\n"
        f"TP2     <code>{sig.tp2:.6g}</code>\n"
        f"TP3     <code>{sig.tp3:.6g}</code>\n\n"
        f"Grade <b>{sig.grade}</b>  ·  Conf <b>{sig.confidence:.0f}%</b>  ·  Lev <b>{sig.leverage:.0f}x</b>\n"
        f"R:R   {sig.rr_tp1} / {sig.rr_tp2} / {sig.rr_tp3}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>DETECTION FILTERS</b>   {n_trig}/5\n"
        f"{f_imb}\n{f_prs}\n{f_wal}\n{f_ero}\n{f_rsi}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔻 Reversal confirmed — entering descent\n"
        f"🐋 <i>WhaleMind Prime</i>"
    )
    log.info("🔭🔻 PEAK HUNTER SIGNAL: %s SHORT @%.6g grade=%s [%s]",
             symbol, price, sig.grade, "+".join(sigs))
    # نفتح أولاً، ونرسل البطاقة للقناة فقط إن فُتحت الصفقة فعلاً (لا بطاقة لصفقة مُنعت/مكرّرة)
    opened_ok = False
    if position_manager_fn:
        try:
            _result = await position_manager_fn(sig)
            opened_ok = (_result is not None)   # open_from_signal يرجع pos عند الفتح، None عند المنع
        except Exception as e:
            log.error("scout → manager error: %s", e)

    if opened_ok:
        try:
            from services.telegram import send_message
            from core.config import get_settings
            ch = get_settings().telegram_channel_futures
            if ch:
                await send_message(ch, msg)
        except Exception as e:
            log.error("scout signal error: %s", e)
        _save_to_signals_table(sig, "🎯 Peak Hunter SHORT\n" + "\n".join(sigs))
        log.info("🔭📈 Peak Hunter → manager: %s SHORT (opened)", symbol)
    else:
        log.info("🔭⏭️ Peak Hunter: %s SHORT لم تُفتح (مفتوحة بالفعل/مُنعت) — لا بطاقة للقناة", symbol)



# ═══════════════════════════════════════════════════════════════
# الحلقة الجديدة: مراقبة صارمة دائمة (فلسفة المستخدم)
#   • القائمة صغيرة (3-25) → نراقبها كلها كل 10s (صرامة)
#   • الفرز كل 60s (تحديث القائمة سريعاً)
#   • العملة لا تموت: بعد إشارة → cooldown 10د → تعود للمراقبة
#   • depth ذكي: فقط للقريبة من القمة (توفير API)
# ═══════════════════════════════════════════════════════════════

# الإعدادات الجديدة (تستبدل القديمة):
#   LEVEL1_INTERVAL = 60   (فرز كل دقيقة بدل 5 دقائق)
#   MONITOR_INTERVAL = 10  (مراقبة صارمة كل 10 ثوانٍ)
#   SIGNAL_COOLDOWN = 600  (10 دقائق بعد إشارة ثم تعود)

async def scout_loop(broadcast_fn=None, position_manager_fn=None):
    """مراقبة صارمة دائمة: لا عملة تموت، القائمة الصغيرة تُراقب كل 10s."""
    _init_db()
    log.info("🔭 Peak Hunter بدأ — مراقبة صارمة (فرز 60s + مراقبة كل 10s، لا توقّف)")
    last_level1 = 0
    MONITOR_INTERVAL = 15   # صرامة: كل 15 ثانية (آمن من rate limit، 20× أسرع من القديم)
    FRESH_INTERVAL = 60     # فرز القائمة كل دقيقة
    SIGNAL_COOLDOWN = 1800  # بعد إشارة: 30 دقيقة ثم تعود (يمنع يغلق/يفتح المتكرر)

    while True:
        try:
            now = time.time()

            # ═══ الفرز (كل 60s): تحديث القائمة ═══
            if now - last_level1 >= FRESH_INTERVAL:
                last_level1 = now
                gainers = await fetch_top_gainers()
                conn = sqlite3.connect(DB_PATH)
                for g in gainers[:25]:
                    conn.execute("""
                        INSERT OR IGNORE INTO watchlist
                        (symbol, gain_pct, volume_usd, peak_price, added_at, last_check)
                        VALUES (?,?,?,?,?,?)
                    """, (g["symbol"], g["gain"], g["volume"], g["price"], int(now), int(now)))
                    conn.execute("UPDATE watchlist SET peak_price=MAX(peak_price, ?), gain_pct=? WHERE symbol=?",
                                 (g["price"], g["gain"], g["symbol"]))
                conn.commit()
                conn.close()
                log.info("🔭 [فرز] %d عملة في الأعلى ربحاً (مراقبة صارمة)", len(gainers))

            # ═══ المراقبة الصارمة (كل 10s): كل العملات النشطة ═══
            conn = sqlite3.connect(DB_PATH)
            # نراقب كل العملات إلا التي في cooldown (signaled حديثاً)
            rows = conn.execute("""
                SELECT symbol, peak_price, alert_sent, signal_sent, last_check, status
                FROM watchlist
            """).fetchall()
            conn.close()

            for symbol, peak, alert_sent, signal_sent, last_check, status in rows:
                try:
                    # العملة في cooldown بعد إشارة؟ (لا تموت — تعود بعد 10د)
                    if status == "signaled":
                        if now - (last_check or 0) < SIGNAL_COOLDOWN:
                            continue  # ما زالت في الراحة القصيرة
                        # 🔭 كسر الحلقة: إن خسرت آخر صفقة خلال ساعتين، لا تُعاد بعد (INX خسرت 3 مرّات متتالية صاعدة)
                        try:
                            _cc = sqlite3.connect("/opt/whalex/ml_training.db")
                            _last = _cc.execute(
                                "SELECT pnl_pct, closed_at FROM training_signals "
                                "WHERE symbol=? AND tier='PH' AND pnl_pct IS NOT NULL "
                                "ORDER BY closed_at DESC LIMIT 1", (symbol,)).fetchone()
                            _cc.close()
                            if _last and _last[0] is not None and _last[0] <= 0 and _last[1] and (now - int(_last[1])) < 7200:
                                log.info("🔭 %s: خسرت آخر صفقة (%.2f%%) قبل <ساعتين — كسر الحلقة، لا إعادة اصطياد", symbol, _last[0])
                                continue
                        except Exception as _e:
                            log.debug("loop-break check %s: %s", symbol, _e)
                        # انتهى cooldown + لم تخسر حديثاً → تعود للمراقبة (تُحيا)
                        conn = sqlite3.connect(DB_PATH)
                        conn.execute("UPDATE watchlist SET status='watching', signal_sent=0 WHERE symbol=?", (symbol,))  # alert_sent يبقى — لا Watch مكرّر
                        conn.commit()
                        conn.close()
                        log.info("🔭 %s عادت للمراقبة (cooldown انتهى)", symbol)

                    # مرحلة 1: لم يُنبَّه → نكشف تشكّل القمة
                    if not alert_sent:
                        res = await detect_top_forming(symbol, peak)
                        if res["forming"]:
                            await _send_alert_once(symbol, res, peak)
                            conn = sqlite3.connect(DB_PATH)
                            conn.execute("UPDATE watchlist SET alert_sent=1, last_check=? WHERE symbol=?", (int(now), symbol))
                            conn.commit()
                            conn.close()
                        continue

                    # مرحلة 2: نُبِّه → مراقبة OB صارمة للانهيار
                    candles = await fetch_klines_async(symbol, "15m", 50)
                    col = await detect_collapse(symbol, peak, candles)
                    if col["collapse"]:
                        # 🔭 إعادة فحص السيولة الحيّة قبل الصيد — HANA دخلت بـ15M ثمّ انهارت لـ0.9M (تلاعب)
                        try:
                            async with httpx.AsyncClient(timeout=8) as _vc:
                                _vr = await _vc.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol}")
                                _vol_now = float(_vr.json().get("quoteVolume", 0))
                            if _vol_now < MIN_VOLUME_USD:
                                log.info("🔭 %s: سيولة انهارت (%.1fM < %.0fM) — حذف من watchlist، لا صيد",
                                         symbol, _vol_now/1e6, MIN_VOLUME_USD/1e6)
                                conn = sqlite3.connect(DB_PATH)
                                conn.execute("DELETE FROM watchlist WHERE symbol=?", (symbol,))
                                conn.commit()
                                conn.close()
                                continue
                        except Exception as _ve:
                            log.debug("liquidity recheck %s: %s", symbol, _ve)
                        price = candles[-1].close
                        await _send_signal_and_open(symbol, price, candles, peak, col, position_manager_fn)
                        conn = sqlite3.connect(DB_PATH)
                        # signaled + cooldown (لا تموت — تعود بعد 10د)
                        conn.execute("UPDATE watchlist SET signal_sent=1, status='signaled', last_check=? WHERE symbol=?", (int(now), symbol))
                        conn.commit()
                        conn.close()
                        log.info("🔭 %s: انهيار OB → إشارة (ثم cooldown 10د)", symbol)
                except Exception as e:
                    log.debug("scout monitor %s: %s", symbol, e)
                await asyncio.sleep(0.2)  # فاصل صغير بين العملات (تخفيف API)

        except Exception as e:
            log.error("scout_loop error: %s", e)

        await asyncio.sleep(MONITOR_INTERVAL)  # مراقبة كل 10s (صرامة)
