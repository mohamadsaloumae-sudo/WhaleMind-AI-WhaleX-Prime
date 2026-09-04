"""🪙 عقل السبوت v1 — صيّاد قيعان التجميع (معزول كلياً عن الفيوتشر).
المنطق: قاع نطاق صامد + RSI مضغوط + دخول أموال هادئ (Taker-buy + حجم) + شرارة خضراء → BUY.
"""
import asyncio, time, logging, uuid
from datetime import datetime

import httpx

log = logging.getLogger("spot_scout")

SPOT = "https://api.binance.com"
UNIVERSE_N   = 120          # أعلى الأزواج سيولةً (التوب 50 داخلها — إضافة لا إلغاء)
UNIVERSE_TTL = 3600         # تحديث الكون كل ساعة
CYCLE        = 300          # دورة فحص كل 5 دقائق
COOLDOWN     = 4 * 3600     # لكل رمز بعد إشارة
_last_sig: dict = {}
_universe: list = []
_uni_ts = 0.0
_EXCLUDE = ("UP", "DOWN", "BULL", "BEAR")   # روافع سبوت المغلفة
# 🚫 عملات مستقرّة ومربوطة — أهداف 6-20% مستحيلة عليها
# 💎 العملات القويّة: تتحرّك 2-4% يومياً، فأهداف 6-20% تحتاج أسابيع.
#    القياس: 3 صفقات بالمنطق القديم = -3.3% | الصغيرة 148 صفقة = +32.1%
#    الحل: مسار منفصل بأهداف واقعية (+2/+3.5/+5%) ونطاق RSI أوسع.
_STRONG = {"BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "AVAX", "LINK",
           "SUI", "DOT", "MATIC", "POL", "LTC", "TRX", "TON", "NEAR", "ATOM",
           "UNI", "APT", "ICP", "ETC", "XLM", "HBAR", "FIL", "ARB", "OP"}
# 📊 معايرة على قراءات حقيقية: BTC rsi=32 taker=50% | ETH rsi=31 taker=44%
#    الأسواق العميقة متوازنة (44-50%) ولا تُظهر سيطرة شراء 55% كالصغيرة.
STRONG_RSI_MIN, STRONG_RSI_MAX = 30.0, 55.0
STRONG_RANGE_POS = 0.55
STRONG_TAKER = 0.50      # لا نشتري والبائعون مسيطرون — التوازن يكفي
STRONG_VOL = 1.00        # لا انكماش حجم (لا نطلب تضخّماً)
STRONG_TP = (1.020, 1.035, 1.050)   # +2% / +3.5% / +5%
STRONG_SL_PCT = 0.985               # -1.5%


def _is_strong(sym: str) -> bool:
    s = (sym or "").upper()
    return s.endswith("USDT") and s[:-4] in _STRONG


_STABLES = {
    "USDT", "USDC", "BUSD", "TUSD", "USDP", "DAI", "FDUSD", "USDD", "USD1",
    "PYUSD", "EURI", "EUR", "AEUR", "GBP", "TRY", "BRL", "ARS", "IDRT",
    "UAH", "ZAR", "NGN", "RUB", "PLN", "RON", "CZK", "JPY", "MXN", "COP",
    "USDS", "USDE", "USDF", "SUSD", "LUSD", "GUSD", "USDX", "XUSD", "USTC",
    "WBTC", "WBETH", "BETH", "WBNB", "PAXG", "XAUT",
    # 📊 رُصدت تمرّ رغم أنها مستقرّة (RLUSD أعطت إشارة بحركة 0.03%)
    "RLUSD", "USDG", "USDY", "USDB", "EURC", "EURT", "CHF", "CAD", "AUD",
}


def _is_stable(sym: str) -> bool:
    """يكشف الأزواج المستقرّة: الأصل نفسه عملة مستقرّة أو مربوطة."""
    s = (sym or "").upper()
    if not s.endswith("USDT"):
        return True
    base = s[:-4]
    return (not base) or (base in _STABLES)


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


_STATUS_CACHE: dict = {}
_STATUS_TS = [0.0]


async def _tradable_only(c: httpx.AsyncClient, syms: list) -> list:
    """يُبقي ما حالته TRADING فقط — يستبعد BREAK · HALT · AUCTION_MATCH."""
    import time as _t
    if _t.time() - _STATUS_TS[0] > 3600 or not _STATUS_CACHE:
        try:
            r = await c.get(f"{SPOT}/api/v3/exchangeInfo", timeout=25)
            _STATUS_CACHE.clear()
            for s in (r.json().get("symbols") or []):
                _STATUS_CACHE[s.get("symbol")] = s.get("status")
            _STATUS_TS[0] = _t.time()
        except Exception as e:
            log.warning("🪙 exchangeInfo: %s", e)
            return syms          # عند الفشل لا نحجب شيئاً
    if not _STATUS_CACHE:
        return syms
    return [s for s in syms if _STATUS_CACHE.get(s) == "TRADING"]


async def _universe_refresh(c: httpx.AsyncClient):
    global _universe, _uni_ts
    if _universe and time.time() - _uni_ts < UNIVERSE_TTL:
        return
    r = await c.get(f"{SPOT}/api/v3/ticker/24hr", timeout=15)
    rows = [x for x in r.json()
            if x.get("symbol", "").endswith("USDT")
            and not any(t in x["symbol"] for t in _EXCLUDE)
            and not _is_stable(x["symbol"])
            and float(x.get("quoteVolume", 0) or 0) > 0]
    rows.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
    _cand = [x["symbol"] for x in rows[:UNIVERSE_N * 2]]
    # ⛔ نستبعد الموقوفة عن التداول — ticker/24hr لا يحمل الحالة.
    #    UTKUSDT كانت BREAK (تداول معلّق) والرادار اصطادها:
    #    لا تظهر على الشارت، ولن يُنفَّذ عليها أمر حقيقي.
    _ok = await _tradable_only(c, _cand)
    _universe = _ok[:UNIVERSE_N]
    _uni_ts = time.time()
    log.info("🪙 كون السبوت: %d زوجاً (مُتداوَلة فعلياً · %d مستبعَدة)",
             len(_universe), len(_cand) - len(_ok))


def _trend_ok(highs, lows) -> tuple:
    """📈 الاتجاه من القمم والقيعان الفعلية.
    قاع أعلى من سابقه = صاعد ✓ | قاع أدنى = هابط ✗ (سكين، لا ندخل)
    ROBO خسرت 4 مرات متتالية لأننا دخلناها في ترند هابط."""
    if len(lows) < 30:
        return False, "بيانات قليلة"
    # نقسم آخر 30 شمعة لثلاث نوافذ ونقارن قيعانها وقممها
    w = 10
    l1, l2, l3 = min(lows[-30:-20]), min(lows[-20:-10]), min(lows[-10:])
    h1, h2, h3 = max(highs[-30:-20]), max(highs[-20:-10]), max(highs[-10:])
    # هابط: القيعان تتناقص والقمم تتناقص
    if l3 < l2 < l1 and h3 < h2:
        return False, "ترند هابط (قيعان وقمم متناقصة)"
    # القاع الأخير أدنى بكثير = ما زال ينزل
    if l3 < l2 * 0.985:
        return False, "قاع جديد أدنى — ما زال ينزل"
    return True, "الاتجاه سليم"


async def _book_ok(c: httpx.AsyncClient, sym: str, price: float) -> tuple:
    """📖 الأوردر بوك: هل توجد طلبات شراء حقيقية تسند السعر؟
    بلا مشترين في الكتاب، لا شيء يوقف الهبوط."""
    try:
        r = await c.get(f"{SPOT}/api/v3/depth?symbol={sym}&limit=100", timeout=8)
        if r.status_code != 200:
            return True, "لا بيانات كتاب (تساهل)"
        d = r.json()
        bids = [(float(p), float(q)) for p, q in d.get("bids", [])]
        asks = [(float(p), float(q)) for p, q in d.get("asks", [])]
        if not bids or not asks:
            return True, "كتاب فارغ (تساهل)"
        bv = sum(p * q for p, q in bids[:20])
        av = sum(p * q for p, q in asks[:20])
        if (bv + av) <= 0:
            return True, "كتاب صفري"
        imb = (bv - av) / (bv + av)
        if imb < -0.25:
            return False, f"بائعون مسيطرون في الكتاب ({imb*100:+.0f}%)"
        # جدار شراء: أكبر مستوى مقابل المتوسط
        lv = [p * q for p, q in bids[:50]]
        avg = sum(lv) / len(lv) if lv else 0
        wall = max(lv) if lv else 0
        if avg > 0 and wall < avg * 2.0:
            return False, "لا جدار شراء يسند"
        return True, f"كتاب داعم (اختلال {imb*100:+.0f}%)"
    except Exception:
        return True, "خطأ كتاب (تساهل)"


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
    # 📈 الاتجاه أولاً: لا ندخل سكيناً هابطة
    _t_ok, _t_why = _trend_ok(highs, lows)
    if not _t_ok:
        return
    # 📊 تحليل 124 صفقة: 6-12 UTC = +74.9% (فوز 58%) | 18-24 = -36.5% | 0-6 = -7%
    from datetime import datetime as _dt
    if _dt.utcnow().hour >= 18 or _dt.utcnow().hour < 6:
        return
    # 📊 الموقع 25-45% = -1.2% (فوز 37%) | 0-25% = +47.2%
    if range_pos > 0.25:
        return
    _strong = _is_strong(sym)
    if _strong:
        _rsi_dbg = _rsi(closes)
        _v8d, _t8d = sum(vols[-8:]), sum(tbuys[-8:])
        _tkd = (_t8d / _v8d) if _v8d > 0 else 0
        _vavgd = sum(vols[-48:-8]) / 40 if len(vols) >= 48 else 1
        _vinfd = (_v8d / 8) / _vavgd if _vavgd > 0 else 0
        if range_pos <= STRONG_RANGE_POS and STRONG_RSI_MIN <= _rsi_dbg <= STRONG_RSI_MAX:
            log.info("💎 قويّة %s: pos=%.0f%% rsi=%.0f taker=%.0f%% vol=%.2fx",
                     sym, range_pos * 100, _rsi_dbg, _tkd * 100, _vinfd)
    _max_pos = STRONG_RANGE_POS if _strong else 0.45
    if range_pos > _max_pos:
        return
    rsi_v = _rsi(closes)
    # 🧠 RSI لم يعد إقصائياً — يُحسب ضمن النقاط أدناه.
    #    كانت عملة بـRSI 62 وجدار شراء وحجم x3 تُرفض هنا فوراً.
    if min(lows[-6:]) < lo * 0.985:
        return  # كسر قاعٍ جديد — ليس صموداً
    v8, t8 = sum(vols[-8:]), sum(tbuys[-8:])
    taker = (t8 / v8) if v8 > 0 else 0
    v_avg = sum(vols[-48:-8]) / 40 if len(vols) >= 48 else (sum(vols[:-8]) / max(1, len(vols) - 8))
    v_infl = (v8 / 8) / v_avg if v_avg > 0 else 0
    # ═══ 🧠 نظام النقاط: الأدلّة تجتمع، ولا مؤشّر واحد يحكم ═══
    _pts, _why = 0.0, []
    if 30 <= rsi_v <= 55:
        _pts += 2.5; _why.append(f"RSI {rsi_v:.0f}")
    elif 55 < rsi_v <= 68 and v_infl >= 1.5:
        _pts += 2.0; _why.append(f"زخم RSI {rsi_v:.0f}")
    elif 25 <= rsi_v < 30:
        _pts += 1.5; _why.append(f"مُشبع {rsi_v:.0f}")
    if taker >= 0.60:
        _pts += 2.5; _why.append(f"ضغط {taker*100:.0f}%")
    elif taker >= 0.52:
        _pts += 1.5; _why.append(f"شراء {taker*100:.0f}%")
    if v_infl >= 2.0:
        _pts += 2.0; _why.append(f"حجم x{v_infl:.1f}")
    elif v_infl >= 1.3:
        _pts += 1.2; _why.append(f"حجم x{v_infl:.1f}")
    if range_pos <= 0.35:
        _pts += 1.5; _why.append(f"قاع {range_pos*100:.0f}%")
    elif range_pos <= 0.55:
        _pts += 0.8
    if closes[-1] > sum(closes[-6:-1]) / 5:
        _pts += 1.0; _why.append("شرارة")
    SPOT_SCORE_MIN = 6.0
    if _pts < SPOT_SCORE_MIN:
        return
    # ⚠️ الشرطان القديمان (شرارة خضراء · taker>=0.53) أُزيلا:
    #    صارا مكرّرين بعد نظام النقاط — فكانا يقتلان ما تجتازه النقاط.
    #    UTKUSDT: نقاط 6.0 (RSI 53 · حجم x9.07 · قاع 10%) ثم رُفضت لأن taker=49%.
    log.info("🪙🔎 مرشّح: %s نقاط=%.1f | %s", sym, _pts, " · ".join(_why))
    grade = "A" if _pts >= 7.5 else "B"

    # 📖 آخر فحص قبل الدخول: هل يوجد مشترون في الكتاب يسندون السعر؟
    _b_ok, _b_why = await _book_ok(c, sym, price)
    if not _b_ok:
        log.info("🪙📖 %s رُفض: %s", sym, _b_why)
        return

    entry = price
    if _strong:
        sl = max(lo * 0.99, price * STRONG_SL_PCT)   # -1.5% للقويّة
        tp1, tp2, tp3 = (entry * STRONG_TP[0], entry * STRONG_TP[1], entry * STRONG_TP[2])
    else:
        sl = max(lo * 0.985, price * 0.98)
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
    # نحسب معايير الدماغ من الشموع المتاحة. ولا نبتلع الخطأ صامتاً:
    #   القيم تبقى None فيمرّ الدماغ بالأساس بدل أن يُعطَّل بلا أثر.
    _z_v = _bb_v = _rsi2_v = _atr_v = None
    _path_name = "pullback"
    try:
        from radars.spot.std_filter import zscore as _zf, bb_position as _bf, rsi_n as _rf
        _z_v = _zf(closes)
        _bb_v = _bf(closes)
        _rsi2_v = _rf(closes, 2)
        if len(closes) >= 15:
            _d = [abs(closes[i] - closes[i - 1]) for i in range(-14, 0)]
            _atr_v = round(sum(_d) / 14 / (closes[-1] or 1) * 100, 3)
    except Exception as _fe:
        log.debug("معايير الدماغ: %s", _fe)

    # 🪙🧠 الدماغ الثاني — نموذج أوزان مُدرَّب على 446 صفقة بـ28 حقلاً.
    #   القديم مات: 180 صفّاً و65% بلا نتيجة وآخر تسجيل قبل 308 ساعة.
    #   وأبرز ما كشفه التدريب: taker 0.55-0.65 فوز 50% · حجم معتدل
    #   (1.2-2×) فوز 50% بينما المتطرّف (2-4×) فوز 34.6% · واختراق
    #   فوز 47.1% بينما الارتداد (79% من صفقاتنا) فوز 34.5%.
    #   ويمنع دون احتمال 30%.
    try:
        from quant_engine.spot_brain_v2 import should_enter as _se2
        _feats = {"taker": taker, "vol_infl": v_infl, "rsi14": rsi_v,
                  "range_pos": range_pos, "path": _path_name,
                  "rsi2": _rsi2_v, "bb_pos": _bb_v, "zscore": _z_v,
                  "atr_pct": _atr_v, "hour_utc": _t.gmtime().tm_hour}
        _ok2, _pp, _note = _se2(_feats)
        log.info("🪙🧠 الدماغ: %s نجاح %.0f%% | %s", sym, _pp * 100, _note[:60])
        if not _ok2:
            log.info("🪙🛑 %s مُنعت — %s", sym, _note[:60])
            return
    except Exception as _be:
        log.debug("spot brain2: %s", _be)

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
            try:
                from services.notifier import push_note
                await push_note("spot", "signal", f"🪙 إشارة سبوت جديدة: {sym}")
            except Exception:
                pass
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
# ═══ 🌊 الخروج الديناميكي: يقرأ ضغط الشراء لحظياً بدل رقم جامد ═══
#   القياس: reversal (قراءة لحظية) = +7.52% | القفل الجامد = +2.21%
DYN_STRONG_TAKER = 0.55
DYN_WEAK_TAKER   = 0.48
DYN_HARVEST_PNL  = 2.5
DYN_MIN_PROFIT   = 1.0      # كان 2.0 — قياس 50 مساراً: عتبة 1.0 تُعطي
                            # +31.8 نقطة مقابل +23.2 لعتبة 2.0
SPOT_STALL_SEC   = 300      # القمّة راكدة خمس دقائق → نحصد
SPOT_HARVEST_MIN = 1.0
DYN_TRAIL_GIVE   = 3.0
REENTRY_COOLDOWN = 1800
# 🚪 قطع الخسارة بالتدفّق (لا بالسعر وحده)
FLOW_CHECK_LOSS = -0.6      # نبدأ استشارة الأوردر بوك من هذه الخسارة
FLOW_EXIT_TAKER = 0.45      # تدفّق أضعف من هذا = بائعون مسيطرون
FLOW_MAX_LOSS = -2.0        # دون هذا يتولّى الوقف
_taker_cache: dict = {}


async def _live_taker(c, sym: str):
    """ضغط الشراء الآن (آخر 8 شموع 15د). كاش 90ث."""
    _now = time.time()
    _h = _taker_cache.get(sym)
    if _h and _now - _h[0] < 90:
        return _h[1]
    try:
        r = await c.get(f"{SPOT}/api/v3/klines?symbol={sym}&interval=15m&limit=10", timeout=8)
        if r.status_code != 200:
            return None
        k = r.json()
        # 🔬 مثبَت بالقياس: x[7] حجم بالدولار و x[9] شراء بالعملة الأساس —
        #    قسمتهما تعطي 0.000 لبيتكوين و5.683 لدوجي (والنسبة يستحيل تخرج 0-1).
        #    الصحيح: أساس÷أساس [9]/[5] — أعطى 0.519 و0.512 وهي القيم الحقيقية.
        v = sum(float(x[5]) for x in k[-8:])
        tb = sum(float(x[9]) for x in k[-8:])
        tk = (tb / v) if v > 0 else None
        if tk is not None:
            _taker_cache[sym] = (_now, tk)
        return tk
    except Exception:
        return None


_track: dict = {}           # sig_id -> stage (0 لم يلمس، 1/2 بعد TP1/TP2)
_peak: dict = {}
# ⏱ الوقت — كان يُستورَد محلّياً في دالة واحدة، فحصاد الركود
#    يفشل بـ"name '_t' is not defined" (16 مرّة في 15 دقيقة).
import time as _t

_peak_at: dict = {}
# 🔧 ظروف الدخول — كانت تُهمَل فلا نتعلّم من الصفقات الميّتة شيئاً.
#    مقيس: 66 صفقة في 24 ساعة بفوز 27%، وأعمدة rsi/taker/range_pos
#    فارغة كلّها، فلا سبيل لمعرفة ما يُميّز الميّتة عن الرابحة.
_entry_ctx: dict = {}      # 🌾 متى ارتفعت القمّة آخر مرّة — لقراءة الركود            # sig_id -> أعلى سعر بلغته الصفقة (للقفل المتحرك وكشف الانعكاس)
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


_MULTI_EX_CACHE = {}
_BN_ONLY = {"syms": set(), "ts": 0.0}


def _binance_only_syms() -> set:
    """رموز مصدرها باينانس فقط — غيرها يُسعَّر من منصّته."""
    import sqlite3, time as _t
    if _t.time() - _BN_ONLY["ts"] < 300 and _BN_ONLY["syms"]:
        return _BN_ONLY["syms"]
    try:
        cn = sqlite3.connect("/opt/whalex/spot_universe.db")
        rows = cn.execute("SELECT symbol FROM spot_universe WHERE exchange='binance'").fetchall()
        cn.close()
        _syms = {r[0] for r in rows}
        # 🕳️ سدّ الثغرة: عملة خرجت من الكون ونصّ إشارتها "باينانس"
        #    كانت تسقط بين الحارسين — _open_symbols_by_ex تتخطّاها
        #    لأن منصّتها باينانس، وهذه القائمة لا تشملها لأنها خارج
        #    الكون. فلا سعر لها أبداً ولا تُغلق.
        #    مقيس: MMTUSDT عمرها 150 ساعة و9BIT 64، وكلّها بسعر صفر.
        _syms |= _open_binance_syms()
        _BN_ONLY["syms"] = _syms
        _BN_ONLY["ts"] = _t.time()
    except Exception:
        pass
    return _BN_ONLY["syms"]


def _open_binance_syms() -> set:
    """رموز الصفقات المفتوحة التي منصّتها باينانس أو مجهولة."""
    out = set()
    try:
        from db.database import get_session, Signal
        db = get_session()
        try:
            rows = [(x.symbol, x.strategies) for x in db.query(Signal).filter(
                Signal.radar_type == "spot", Signal.is_active == True).all()]
        finally:
            db.close()
        for sym, strat in rows:
            ex = _ex_from_sig(strat) or "binance"
            if ex == "binance":
                out.add(sym)
    except Exception as e:
        log.debug("رموز المفتوحة الباينانسية: %s", e)
    return out


def _multi_prices_sync() -> dict:
    """
    🌐 أسعار العملات غير الباينانسية من منصّاتها هي.
    السبب: XMRUSDT على مكسي بـ425$ ورمز مختلف على باينانس بـ118$ —
    فقراءة سعر باينانس أعطت خسارة وهمية -72% وأغلقت صفقة رابحة.
    """
    import sqlite3
    out = {}
    try:
        cn = sqlite3.connect("/opt/whalex/spot_universe.db")
        rows = cn.execute("SELECT symbol,exchange,ccxt_symbol FROM spot_universe "
                          "WHERE exchange != 'binance'").fetchall()
        cn.close()
    except Exception:
        return out
    by_ex = {}
    for sym, ex, ck in rows:
        by_ex.setdefault(ex, []).append((sym, ck))
    import ccxt
    for ex, items in by_ex.items():
        try:
            e = _MULTI_EX_CACHE.get(ex)
            if e is None:
                e = getattr(ccxt, ex)({"enableRateLimit": True, "timeout": 20000,
                                       "options": {"defaultType": "spot"}})
                _MULTI_EX_CACHE[ex] = e
            tk = e.fetch_tickers([ck for _s, ck in items])
            for sym, ck in items:
                t = tk.get(ck) or {}
                px = t.get("last") or t.get("close")
                if px:
                    out[sym] = float(px)
        except Exception as _e:
            log.debug("🪙 multi px %s: %s", ex, _e)
    return out


_OUT_OF_UNIVERSE = set()


def _ex_from_sig(txt) -> str:
    """منصّة الإشارة من نصّها — الكون يُعاد بناؤه كل ساعة ويحذف
    ما هبط حجمه، فتفقد الصفقة المفتوحة منصّتها وتبقى بلا سعر."""
    import re as _re
    m = _re.search(r"المنصّة:\s*([a-z]+)", str(txt or ""))
    return m.group(1) if m else ""


def _open_symbols_by_ex() -> dict:
    """رموز الصفقات المفتوحة غير الباينانسية، مجمَّعة بمنصّتها."""
    import sqlite3
    out = {}
    try:
        from db.database import get_session, Signal
        db = get_session()
        try:
            rows_sig = [(x.symbol, x.strategies) for x in db.query(Signal).filter(
                Signal.radar_type == "spot", Signal.is_active == True).all()]
        finally:
            db.close()
        syms = [x[0] for x in rows_sig]
        if not syms:
            return out
        cn = sqlite3.connect("/opt/whalex/spot_universe.db")
        q = ",".join("?" * len(syms))
        known = {}
        for sym, ex, ck in cn.execute(
                f"SELECT symbol,exchange,ccxt_symbol FROM spot_universe "
                f"WHERE symbol IN ({q})", syms):
            known[sym] = (ex, ck)
        cn.close()
        for sym, strat in rows_sig:
            ex, ck = known.get(sym, ("", ""))
            if not ex:
                # 🛡️ سقطت من الكون — نأخذ منصّتها من نصّ الإشارة
                ex = _ex_from_sig(strat)
                base = sym[:-4] if sym.upper().endswith("USDT") else sym
                ck = f"{base}/USDT"
                if ex and sym not in _OUT_OF_UNIVERSE:
                    _OUT_OF_UNIVERSE.add(sym)
                    log.info("🪙🛡️ %s خارج الكون — منصّتها من الإشارة: %s", sym, ex)
            if ex and ex != "binance" and ck:
                out.setdefault(ex, []).append((sym, ck))
    except Exception as e:
        log.warning("🪙⚠️ تعذّر جلب رموز المفتوحة: %s", e)
    return out


def _open_prices_sync() -> dict:
    """أسعار الصفقات المفتوحة وحدها — نداء واحد لكل منصّة."""
    got = {}
    import ccxt
    for ex, items in _open_symbols_by_ex().items():
        try:
            e = _MULTI_EX_CACHE.get(ex)
            if e is None:
                e = getattr(ccxt, ex)({"enableRateLimit": True, "timeout": 15000,
                                       "options": {"defaultType": "spot"}})
                _MULTI_EX_CACHE[ex] = e
            tk = e.fetch_tickers([ck for _s, ck in items])
            for sym, ck in items:
                t = tk.get(ck) or {}
                px = t.get("last") or t.get("close")
                if px:
                    got[sym] = float(px)
        except Exception as _e:
            log.debug("🪙⚡ %s: %s", ex, _e)
    return got


def _cooldown_load() -> dict:
    """🛡️ التبريد من القاعدة — كانت إعادة التشغيل تُعيد نفس الإشارة فوراً."""
    import sqlite3, time as _t
    out = {}
    try:
        c = sqlite3.connect("/opt/whalex/db/whalex.db")
        cut = int(_t.time()) - 4 * 3600
        for sym, ts in c.execute("SELECT symbol,ts FROM spot_cooldown WHERE ts>?", (cut,)):
            out[sym] = float(ts)
        c.execute("DELETE FROM spot_cooldown WHERE ts<?", (cut,))
        c.commit(); c.close()
        if out:
            log.info("🛡️ استُعيد تبريد %d عملة", len(out))
    except Exception as e:
        log.warning("🛡️ تبريد: %s", e)
    return out


def _cooldown_save(symbol):
    import sqlite3, time as _t
    try:
        c = sqlite3.connect("/opt/whalex/db/whalex.db")
        c.execute("INSERT OR REPLACE INTO spot_cooldown VALUES(?,?)",
                  (symbol, int(_t.time())))
        c.commit(); c.close()
    except Exception:
        pass


def _state_load() -> dict:
    """
    🛡️ القمم من القاعدة — الذاكرة تُمحى مع كل إعادة تشغيل.
    صفقة بلغت +30% كانت تفقد قمّتها فلا يُقفَل ربحها. الميم يحفظها
    في peak_price منذ البداية؛ والسبوت لم يكن يحفظها إطلاقاً.
    """
    import sqlite3
    out = {}
    try:
        c = sqlite3.connect("/opt/whalex/db/whalex.db")
        for sid, pk, st in c.execute("SELECT sig_id,peak,stage FROM spot_state"):
            if pk:
                out[sid] = float(pk)
            if st is not None:
                _track[sid] = int(st)
        c.close()
        if out:
            log.info("🛡️ استُعيدت %d قمّة من القاعدة", len(out))
    except Exception as e:
        log.warning("🛡️ استعادة الحالة: %s", e)
    return out


def _state_save(sig_id, peak=None, stage=None):
    import sqlite3, time as _t
    try:
        c = sqlite3.connect("/opt/whalex/db/whalex.db")
        c.execute("INSERT INTO spot_state(sig_id,peak,stage,updated) VALUES(?,?,?,?) "
                  "ON CONFLICT(sig_id) DO UPDATE SET "
                  "peak=COALESCE(MAX(excluded.peak, spot_state.peak), spot_state.peak), "
                  "stage=COALESCE(excluded.stage, spot_state.stage), "
                  "updated=excluded.updated",
                  (str(sig_id), peak, stage, int(_t.time())))
        c.commit(); c.close()
    except Exception as e:
        log.debug("🛡️ حفظ الحالة: %s", e)


async def _open_prices_loop():
    """
    ⚡ الصفقات المفتوحة تُسعَّر كل 5 ثوانٍ لا 45.

    مقيس: FLYAIUSDT وقفها -6% فأُغلقت -43.14% لأن سعرها كان عمره
    45 ثانية. ومحاكاة نفس المسار: التردّد الثابت يخرج عند -45%
    والمتكيّف عند -10% — فرق 35 نقطة في الصفقة الواحدة.
    """
    while True:
        try:
            got = await asyncio.to_thread(_open_prices_sync)
            if got:
                _prices.update(got)
        except Exception as e:
            log.debug("🪙⚡ open prices: %s", e)
        await asyncio.sleep(5)


async def _multi_prices_loop():
    """يُحدّث أسعار المنصّات الأخرى كل 45 ثانية."""
    while True:
        try:
            got = await asyncio.to_thread(_multi_prices_sync)
            if got:
                _prices.update(got)
                log.debug("🪙🌐 أسعار من منصّات أخرى: %d", len(got))
        except Exception as e:
            log.warning("🪙🌐 multi prices: %s", e)
        await asyncio.sleep(45)


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
                            # 🛡️ بثّ باينانس لعملاتها وحدها
                            if s and pr and s in _binance_only_syms():
                                _prices[s] = float(pr)
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
    asyncio.create_task(_multi_prices_loop())   # 🌐 كل عملة من منصّتها
    _peak.update(_state_load())                 # 🛡️ القمم تنجو من إعادة التشغيل
    _last_sig.update(_cooldown_load())          # 🛡️ والتبريد كذلك
    asyncio.create_task(_open_prices_loop())    # ⚡ المفتوحة كل 5ث
    _last_rest = 0.0
    async with httpx.AsyncClient() as c:
        while True:
            try:
                if time.time() - _last_rest > 60:
                    _last_rest = time.time()
                    try:
                        r = await c.get(f"{SPOT}/api/v3/ticker/price", timeout=15)
                        _bn = _binance_only_syms()
                        for row in r.json():
                            # 🛡️ لا نكتب سعر باينانس فوق عملة منصّتها أخرى
                            if row["symbol"] in _bn:
                                _prices[row["symbol"]] = float(row["price"])
                    except Exception: pass

                db = get_session()
                try:
                    sigs = db.query(Signal).filter(Signal.radar_type == "spot",
                                                   Signal.is_active == True).all()
                    now = time.time()
                    for s in sigs:
                        px = _prices.get(s.symbol)
                        if not px:
                            # 🕐 مهلة قصوى للصفقة التي لا يُقرأ سعرها.
                            #    مقيس: MMTUSDT عمرها 150 ساعة و9BIT 64،
                            #    وكلّها خرجت من الكون أو تغيّرت منصّتها،
                            #    فلا سعر لها ولا تُغلق أبداً — تبقى معلّقة.
                            try:
                                _ca = getattr(s, "created_at", None)
                                _ts = _ca.timestamp() if hasattr(_ca, "timestamp") else 0
                                _ag = (now - _ts) if _ts else 0
                                if _ag > 72 * 3600:
                                    s.is_active = False
                                    s.pnl_pct = 0.0
                                    s.close_reason = "expired_no_price"
                                    s.closed_at = datetime.utcnow()
                                    db.commit()
                                    _log_result(0, "expired_no_price")
                                    # 💵 نبيع بسعر السوق ولو تعذّرت قراءته —
                                    #    السجلّ لا يُغلق دون تنفيذ حقيقيّ.
                                    try:
                                        await _sell_on_exchange(s.symbol,
                                                                "expired_no_price", 0.0)
                                    except Exception as _se:
                                        log.error("🪙💵 بيع %s بلا سعر: %s",
                                                  s.symbol, _se)
                                    log.warning("🪙⌛ %s أُغلقت بلا سعر بعد %.0f ساعة",
                                                s.symbol, _ag / 3600)
                            except Exception as _ee:
                                log.debug("مهلة بلا سعر %s: %s", s.symbol, _ee)
                            continue
                        st = _track.get(s.id)
                        if st is None:  # أول رؤية (أو بعد restart): هيّئ الطور بصمت
                            st = 2 if px >= s.tp2 else (1 if px >= s.tp1 else 0)
                            _track[s.id] = st
                        age = now - (s.created_at.timestamp() if s.created_at else now)
                        pnl = (px - s.entry) / s.entry * 100 if s.entry else 0.0
                        # 🪙🧠 نبضة تتبّع المسار — تُغذّي الدماغ بـMAE و MFE وزمن
                        #    القمّة. فبلا مسار يتعلّم النتيجة ولا يعرف الرحلة:
                        #    صفقة ربحت 2% بعد أن نزلت -5% تختلف جذرياً عن أخرى
                        #    ربحت 2% مباشرةً.
                        try:
                            from services.lifecycle_recorder import track as _lt2
                            _lt2(s.symbol, 'LONG', float(s.entry or 0), float(px), 1.0)
                        except Exception:
                            pass

                        async def _announce(txt):
                            if ch:
                                try:
                                    from services.notifier import push_note
                                    await push_note("spot", "closed", txt)
                                except Exception: pass
                                try: await send_message(ch, txt)
                                except Exception as _te: log.debug("spot ann: %s", _te)

                        def _log_result(outcome, reason):
                            # 🧠 نُغذّي الدماغ من كل إغلاق لا من ثلاثة مسارات.
                            #    مقيس: 180 صفّاً فقط وآخر تسجيل قبل 163 ساعة،
                            #    لأن record_spot_outcome كانت في locked و sl و tp
                            #    فقط — و flow_cut يُغلق 62% من الصفقات ولا يُسجَّل.
                            #    فالدماغ يرى الرابحة ولا يرى الخاسرة، ويُرجع
                            #    "المتوسط العام" لأغلب الحالات لأنه لم يتعلّم.
                            try:
                                from quant_engine.spot_brain import record_spot_outcome
                                record_spot_outcome(s.symbol, int(outcome),
                                                    float(pnl))
                            except Exception as _be:
                                log.debug("🧠 دماغ السبوت %s: %s", s.symbol, _be)
                            # 🪙🧠 الدماغ الثاني — الصفّ كاملاً بـ28 حقلاً
                            #    مع مسار الصفقة، فيتعلّم كيف ربح وكيف خسر
                            #    لا النتيجة وحدها.
                            try:
                                from quant_engine.spot_brain_v2 import record as _r2
                                from services.lifecycle_recorder import finish as _lf2
                                _mp = _lf2(s.symbol, "LONG", reason) or {}
                                _rs = str(reason or "").lower()
                                _bar = ("sl" if "sl" in _rs else
                                        "time" if ("stall" in _rs or "expire" in _rs)
                                        else "tp" if ("harvest" in _rs or "lock" in _rs)
                                        else "tactical")
                                _r2({
                                    "symbol": s.symbol,
                                    "exchange": getattr(s, "exchange", None),
                                    "path": getattr(s, "path", None),
                                    "entry": float(entry), "exit_price": float(price),
                                    "pnl_pct": float(pnl), "outcome": int(outcome),
                                    "opened_ts": int(opened),
                                    "closed_ts": int(_t.time()),
                                    "duration_min": _mp.get("duration_min"),
                                    "rsi14": getattr(s, "rsi", None),
                                    "range_pos": getattr(s, "range_pos", None),
                                    "taker": getattr(s, "taker", None),
                                    "vol_infl": getattr(s, "vol_infl", None),
                                    "mae_pct": _mp.get("mae_pct"),
                                    "mfe_pct": _mp.get("mfe_pct"),
                                    "time_to_peak_min": _mp.get("time_to_peak_min"),
                                    "barrier": _bar, "reason": reason,
                                    "hour_utc": _t.gmtime().tm_hour,
                                })
                                log.info("🪙🧠 سُجّل: %s %+.2f%% | أعمق %s | أعلى %s | %s",
                                         s.symbol, pnl, _mp.get("mae_pct"),
                                         _mp.get("mfe_pct"), _bar)
                            except Exception as _b2:
                                log.warning("🪙🧠 تسجيل الدماغ %s: %s", s.symbol, _b2)
                            try:
                                import sqlite3
                                cx = sqlite3.connect("/opt/whalex/db/whalex.db")
                                # 📋 السجلّ الكامل: وقت الدخول والمنصّة والمسار —
                                #    كانت المدّة غير محسوبة والمنصّة مجهولة في المغلقة.
                                _op = 0
                                try:
                                    _op = int(s.created_at.timestamp()) if s.created_at else 0
                                except Exception:
                                    _op = 0
                                _ex = _sym_exchange(s.symbol)
                                _strat = str(getattr(s, "strategies", "") or "")
                                _path = ("dip" if "صيد القاع" in _strat else
                                         "pullback" if "ارتداد" in _strat else
                                         "breakout" if "اختراق" in _strat else "")
                                _ctx = _entry_ctx.get(s.symbol) or {}
                                import datetime as _dt
                                cx.execute(
                                    "INSERT INTO spot_results(symbol,entry,exit_price,pnl_pct,"
                                    "outcome,reason,ts,opened_ts,exchange,path,strategies,"
                                    "rsi,range_pos,taker,vol_infl,hour_utc) "
                                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                    (s.symbol, s.entry, px, round(pnl, 2), outcome, reason,
                                     int(now), _op, _ex, _path, _strat[:400],
                                     _ctx.get("rsi"), _ctx.get("range_pos"),
                                     _ctx.get("taker"), _ctx.get("vol_infl"),
                                     _dt.datetime.utcfromtimestamp(_op or now).hour
                                     if (_op or now) else None))
                                cx.commit(); cx.close()
                            except Exception as _re:
                                # ⚠️ كان log.debug فابتُلع الخطأ 31 ساعة:
                                #    "15 values for 16 columns" — فلم يُسجَّل
                                #    أي إغلاق سبوت رغم عشرات الإغلاقات.
                                log.error("🪙📋 فشل تسجيل نتيجة %s: %s",
                                          s.symbol, _re)

                        # 🔒 تتبّع القمة + رفع الوقف عند كل هدف (قفل الربح)
                        _pk = _peak.get(s.id, s.entry)
                        if px > _pk:
                            _pk = px; _peak[s.id] = px; _state_save(s.id, peak=px)
                        _locked_sl = s.sl
                        if px >= s.tp2:
                            _locked_sl = max(_locked_sl, s.entry * 1.06)   # قفل +6%
                        elif px >= s.tp1:
                            _locked_sl = max(_locked_sl, s.entry)          # تعادل
                        # 🧠 كشف انعكاس ذكي: في ربح، وارتد ≥1.5% عن القمة بزخم أحمر → إغلاق فوري
                        _peak_pnl = (_pk - s.entry) / s.entry * 100 if s.entry else 0
                        # 🔒 سلّم جني سريع — أرباح السبوت خفيفة فلا ننتظرها تتبخر
                        _drop = (_pk - px) / _pk * 100 if _pk else 0
                        _tk = None
                        # 📊 161 صفقة: الخروج بالأوردر بوك أربح مسار (+7.26% متوسطاً · 21 صفقة)
                        #    لكنه كان يُستشار عند الربح فقط — فالخاسرة تنزف للوقف (-2.53% · 72 صفقة)
                        #    الآن نستشيره في الخسارة أيضاً من -0.6%: إن انقلب التدفّق نخرج مبكراً
                        if (pnl >= DYN_MIN_PROFIT or _peak_pnl >= DYN_MIN_PROFIT
                                or pnl <= FLOW_CHECK_LOSS):
                            try:
                                # 🌐 من منصّة العملة نفسها — مقيس: FILUSDT
                                #    باينانس 0.535 «أبقِ» بينما أوكي إكس 0.188 «اقطع»
                                from radars.spot.eyes_spot import taker_flow as _tf
                                _tk = await _tf(s.symbol)
                                if _tk is None:
                                    _tk = await _live_taker(c, s.symbol)
                            except Exception:
                                _tk = None
                        _dyn_exit = False
                        _dyn_why = ""
                        if _tk is not None and pnl >= DYN_MIN_PROFIT:
                            if _tk >= DYN_STRONG_TAKER:
                                if _drop >= DYN_TRAIL_GIVE:
                                    _dyn_exit, _dyn_why = True, "trail_strong"
                            elif _tk < DYN_WEAK_TAKER:
                                _dyn_exit, _dyn_why = True, "flow_flip"
                            elif pnl >= DYN_HARVEST_PNL:
                                _dyn_exit, _dyn_why = True, "harvest"

                        # 🌾 حصاد الركود — لا يحتاج تدفّقاً.
                        #    مقيس: 112 صفقة (54%) تموت حول الصفر بصافي
                        #    -79.4%، والحصاد بعتبة 1.0% يوفّر 31.8 نقطة
                        #    على 50 مساراً حقيقياً.
                        if not _dyn_exit and pnl >= SPOT_HARVEST_MIN:
                            _pat = _peak_at.get(s.id)
                            if _pat is None or _peak_pnl > _pat[0] + 0.15:
                                _peak_at[s.id] = (_peak_pnl, _t.time())
                            else:
                                if (_t.time() - _pat[1]) >= SPOT_STALL_SEC:
                                    _dyn_exit = True
                                    _dyn_why = "harvest_stall"
                        if _peak_pnl >= 2.5:
                            _locked_sl = max(_locked_sl, s.entry * 1.020)
                        if _peak_pnl >= 8.0:
                            _locked_sl = max(_locked_sl, _pk * 0.97)
                        # 🚪 التدفّق انقلب ونحن خاسرون → خروج فوري بخسارة صغيرة
                        # 🪙 منطق DCA بدل القطع الفوريّ.
                        #   مقيس على 157 مساراً بمحاكاة شمعةً بشمعة (24 ساعة):
                        #     القطع الحاليّ  -26.7% | فوز 40%
                        #     DCA أمان -2/-4 · هدف 2%  +177.9% | فوز 84%
                        #   والسبب: 36% من العملات التي قطعناها صعدت بعد خروجنا.
                        #   وأي خطأ هنا يرجع للقطع القديم.
                        _dca_on = not _os.path.exists(
                            "/opt/whalex/db/spot_dca.off")
                        if _dca_on:
                            try:
                                from radars.spot.dca_manager import decide as _dd
                                _act, _inf = _dd(
                                    float(pos.get("first_entry") or entry),
                                    price,
                                    pos.get("lots") or [(entry, 1.0)],
                                    pos.get("dca_levels") or [],
                                    (_t.time() - opened) / 3600.0)
                                if _act == "take_profit":
                                    _dyn_exit, _dyn_why = True, "dca_tp"
                                elif _act == "stop":
                                    _dyn_exit, _dyn_why = True, "dca_stop"
                                elif _act == "safety":
                                    _lv = _inf.get("level")
                                    _lots = list(pos.get("lots")
                                                 or [(entry, 1.0)])
                                    _lots.append((price, 1.0))
                                    pos["lots"] = _lots
                                    pos["dca_levels"] = list(
                                        pos.get("dca_levels") or []) + [_lv]
                                    pos["first_entry"] = float(
                                        pos.get("first_entry") or entry)
                                    from radars.spot.dca_manager import (
                                        avg_entry as _ae)
                                    entry = _ae(_lots)
                                    pos["entry"] = entry
                                    log.info("🪙➕ %s أمان %.1f%% @%.8g "
                                             "— المتوسط %.8g (%d أوامر)",
                                             sym, _lv, price, entry, len(_lots))
                            except Exception as _de:
                                log.error("🪙 DCA %s: %s — نرجع للقطع", sym, _de)
                                _dca_on = False
                        if (not _dca_on and _tk is not None
                                and _tk < FLOW_EXIT_TAKER
                                and FLOW_MAX_LOSS <= pnl <= FLOW_CHECK_LOSS):
                            _dyn_exit, _dyn_why = True, "flow_cut"
                        # 👁️ عين الانقلاب — الفيوتشر عنده دفتر 100 مستوى
                        #    والسبوت كان بلا بوّابة أصلاً. لا نستشيرها إلا
                        #    عند خسارة حقيقية أو تراجع عن قمّة (توفير النداءات).
                        if not _dyn_exit and (pnl <= -1.0 or (_peak_pnl >= 3.0 and _drop >= 1.0)):
                            try:
                                from radars.spot.eyes_spot import is_reversal as _isrev
                                _rv, _rwhy = await _isrev(s.symbol, pnl)
                                if _rv:
                                    _dyn_exit, _dyn_why = True, "ob_reversal"
                                    log.info("🪙👁️ %s %s | PnL %+.2f%%", s.symbol, _rwhy, pnl)
                            except Exception as _re:
                                log.debug("spot eye %s: %s", s.symbol, _re)

                        _smart_rev = _dyn_exit or (pnl >= 2.0 and _peak_pnl >= 3.0 and _drop >= 1.2)

                        if _smart_rev:
                            s.is_active = False; s.pnl_pct = round(pnl, 2); s.close_reason = (_dyn_why or "reversal"); s.closed_at = datetime.utcnow(); db.commit()
                            _log_result(1 if pnl > 0 else 0, (_dyn_why or "reversal"))
                            if pnl > 0:
                                _last_sig[s.symbol] = time.time() - (COOLDOWN - REENTRY_COOLDOWN)
                            try:
                                await _sell_on_exchange(s.symbol, "reversal", px)
                            except Exception: pass
                            try:
                                from quant_engine.spot_brain import record_spot_outcome
                                record_spot_outcome(s.symbol, 1 if pnl > 0 else 0, pnl)
                            except Exception: pass
                            await _announce(f"🧠 <b>{s.symbol}</b> — انعكاس مُكتشف، أغلقنا لحفظ الربح\nالنتيجة: <b>{pnl:+.1f}%</b> (القمة كانت {_peak_pnl:+.0f}%)\n🪙 <i>WhaleMind Spot</i>")
                            log.info("🪙🧠 %s reversal-exit %.1f%% (peak %.0f%%)", s.symbol, pnl, _peak_pnl)
                        elif px <= _locked_sl and _locked_sl > s.sl:
                            px = _exec_px(px, _locked_sl)
                            pnl = (px - s.entry) / s.entry * 100
                            s.is_active = False; s.pnl_pct = round(pnl, 2); s.close_reason = "locked"; s.closed_at = datetime.utcnow(); db.commit()
                            _log_result(1 if pnl > 0 else 0, "locked")
                            try:
                                await _sell_on_exchange(s.symbol, "locked", px)
                            except Exception: pass
                            try:
                                from quant_engine.spot_brain import record_spot_outcome
                                record_spot_outcome(s.symbol, 1 if pnl > 0 else 0, pnl)
                            except Exception: pass
                            await _announce(f"🔒 <b>{s.symbol}</b> — قفل الربح عند الارتداد\nالنتيجة: <b>{pnl:+.1f}%</b>\n🪙 <i>WhaleMind Spot</i>")
                            log.info("🪙🔒 %s locked %.1f%%", s.symbol, pnl)
                        elif px <= s.sl:
                            px = _exec_px(px, s.sl)
                            pnl = (px - s.entry) / s.entry * 100
                            s.is_active = False; s.pnl_pct = round(pnl, 2); s.close_reason = "sl"; s.closed_at = datetime.utcnow(); db.commit()
                            _log_result(0, "sl")
                            try:
                                await _sell_on_exchange(s.symbol, "sl", px)
                            except Exception: pass
                            try:
                                from quant_engine.spot_brain import record_spot_outcome
                                record_spot_outcome(s.symbol, 0, pnl)
                            except Exception: pass
                            await _announce(f"🔴 <b>{s.symbol}</b> — ضرب الوقف\nالنتيجة: <b>{pnl:+.1f}%</b>\n🪙 <i>WhaleMind Spot</i>")
                            log.info("🪙🔴 %s SL %.1f%%", s.symbol, pnl)
                        elif px >= s.tp3:
                            s.is_active = False; s.pnl_pct = round(pnl, 2); s.close_reason = "tp3"; s.closed_at = datetime.utcnow(); db.commit()
                            _log_result(1, "tp3")
                            try:
                                await _sell_on_exchange(s.symbol, "tp3", px)
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
                            s.is_active = False; s.pnl_pct = round(pnl, 2); s.close_reason = "expired"; s.closed_at = datetime.utcnow(); db.commit()
                            _log_result(0, "expired")
                            # 💵 لا إغلاق في السجلّ بلا بيع على المنصّة —
                            #    وإلا بقيت العملة في محفظة المشترك.
                            try:
                                await _sell_on_exchange(s.symbol, "expired", px)
                            except Exception as _se:
                                log.error("🪙💵 بيع %s عند المهلة: %s", s.symbol, _se)
                            log.info("🪙⌛ %s expired %.1f%%", s.symbol, pnl)
                finally:
                    db.close()
            except Exception as e:
                log.error("spot tracker: %s", e)
            await asyncio.sleep(3)


MAX_OPEN_SPOT = 12          # 🛡️ سقف الصفقات المتزامنة — 131 كانت جنوناً
MIN_GRADE_OPEN = "A"        # لا نفتح إلا للأقوى حين يقترب السقف


def _open_spot_count() -> int:
    try:
        from db.database import get_session, Signal
        db = get_session()
        try:
            return db.query(Signal).filter(Signal.radar_type == "spot",
                                           Signal.is_active == True).count()
        finally:
            db.close()
    except Exception:
        return 0


def _exec_px(px_seen: float, level: float, slip: float = 0.004) -> float:
    """
    💵 سعر التنفيذ الواقعيّ — لا قاع الذيل الخاطف.

    مقيس: DEVERSEUSDT قفلها عند التعادل 0.4375، ونزلت شمعة واحدة
    بذيل إلى 0.35 ثم عادت 0.4949 في الدقيقة نفسها — فسُجّلت -20%
    وكان الصحيح -0.4%. وFLYAIUSDT وقفها -6% فسُجّلت -43.14%.
    مجموع الفجوة في حالتين: 57 نقطة.

    الوقف أمر معلّق عند المستوى؛ فحين يُخترَق يُنفَّذ عنده زائد
    انزلاق صغير — لا في قاع ذيل يستمرّ ثوانيَ.
    """
    if not level or level <= 0 or not px_seen:
        return px_seen
    worst = level * (1 - slip)
    return max(px_seen, worst) if px_seen < level else px_seen


def _sym_exchange(symbol: str) -> str:
    """🌐 منصّة العملة من كون السبوت — بيع الأصل حيث اشتريناه."""
    try:
        import sqlite3 as _sq
        c = _sq.connect("/opt/whalex/spot_universe.db")
        r = c.execute("SELECT exchange FROM spot_universe WHERE symbol=?",
                      (symbol,)).fetchone()
        c.close()
        return (r[0] if r else "binance")
    except Exception:
        return "binance"


async def _sell_on_exchange(symbol: str, reason: str, price: float = 0.0):
    """🔴 بيع على منصّة العملة نفسها — لا باينانس دائماً."""
    ex = _sym_exchange(symbol)
    try:
        from services.spot_exec import sell_all
        res = await asyncio.to_thread(sell_all, ex, symbol, price)
        for r in res:
            log.info("🪙🔴 %s بيع %s (%s) | %s", ex, symbol, reason,
                     "نجح" if r.get("ok") else r.get("error"))
        return res
    except Exception as e:
        log.error("🪙 بيع %s: %s", symbol, e)
        return []


async def _emit_signal(r: dict):
    """🪙 إصدار إشارة السبوت: قاعدة + قناة + تنفيذ — من منصّة العملة نفسها."""
    sym = r["symbol"]; ex = r.get("exchange", "binance")
    # 🛡️ سقف الانكشاف: لا نفتح بلا حدّ
    _open = _open_spot_count()
    if _open >= MAX_OPEN_SPOT:
        log.info("🪙🛑 %s مُؤجَّلة — السقف %d/%d", sym, _open, MAX_OPEN_SPOT)
        return
    if _open >= MAX_OPEN_SPOT * 0.7 and r.get("grade") != MIN_GRADE_OPEN:
        log.info("🪙🛑 %s مُؤجَّلة — قرب السقف، الدرجة %s", sym, r.get("grade"))
        return
    # 🎯 بوّابة الجودة — جودة لا كثرة.
    #    مقيس على 222 صفقة pullback: الكلّ فوز 28% (+10.5%)،
    #    والمختارة (تصحيح 6%+ مع حجم مؤكَّد) 55 صفقة فوز 43% (+33.6%).
    #    واختبار نصف/نصف: 30%→47% و27%→38%، والنصف الثاني كان
    #    خاسراً (-11.5%) فصار رابحاً (+5.0%).
    try:
        from radars.spot.quality import check as _qcheck
        # why قائمة أسباب — نضمّها نصّاً واحداً كما يُحفَظ في السجلّ
        _wl = r.get("why") or []
        _wtxt = " | ".join(str(v) for v in _wl) if isinstance(_wl, (list, tuple)) else str(_wl)
        _qok, _qwhy = _qcheck(_wtxt, r.get("path") or "", sym)
        if not _qok:
            log.info("🪙🎯 %s مرفوضة — %s", sym, _qwhy)
            return
    except Exception as _qe:
        log.warning("🪙🎯 بوّابة الجودة %s: %s", sym, _qe)

    # 🛡️ بوّابة العمق — نرفض ما ينهار سعره بأمر صغير.
    #    مقيس: 3 كوارث على bingx حملت -86.5% من خسارة السبوت كلّها،
    #    وبدونها الصافي +18.9% موجب. والحجم اليوميّ لا يكشفها
    #    (ALPHAX كانت 4.64M وانهارت 38% في دقيقة) — أمّا عمق الدفتر
    #    فيكشفها: DEVERSE أفضل شراء 6.6$ فقط.
    try:
        from radars.spot.depth_gate import (measure as _dmeasure,
                                            verdict as _dverdict,
                                            cached as _dcached,
                                            remember as _dremember)
        _hit = _dcached(sym)
        if _hit is None:
            from radars.spot.eyes_spot import order_book as _dob
            _ob = await _dob(sym)
            _usd, _sp = _dmeasure(_ob or {})
            _ok, _why = _dverdict(_usd, _sp)
            _dremember(sym, _ok, _why)
        else:
            _ok, _why = _hit
        if not _ok:
            log.info("🪙🛡️ %s مرفوضة — %s", sym, _why)
            return
    except Exception as _de:
        log.warning("🪙🛡️ بوّابة العمق %s: %s", sym, _de)

    entry, sl = r["entry"], r["sl"]
    tp1, tp2, tp3 = r["tp1"], r["tp2"], r["tp3"]
    grade, conf = r["grade"], r["confidence"]

    strategies = (f"{r['label']}\n"
                  f"المنصّة: {ex}\n"
                  f"الحالة: {r['regime']}\n"
                  + "\n".join(r.get("why", [])))

    # القيم داخل meta لا في جذر القاموس، واسم الحجم v_infl
    _m = r.get("meta") or {}
    _entry_ctx[sym] = {
        "rsi": _m.get("rsi"),
        "range_pos": _m.get("range_pos"),
        "taker": _m.get("taker"),
        "vol_infl": _m.get("v_infl"),
        "score": r.get("score"),
    }
    _cooldown_save(sym)
    log.info("🪙🎯 SPOT %s | %s %s | %s | نقاط %.1f %s",
             sym, ex, r["path"], f"@{entry:.6g}", r["score"], grade)

    # ── القاعدة (radar_type='spot' كما كان) ──
    try:
        from db.database import get_session, Signal
        db = get_session()
        try:
            db.add(Signal(id=str(uuid.uuid4()), radar_type="spot", symbol=sym,
                          direction="LONG", grade=grade, score=r["score"],
                          confidence=conf, entry=entry, sl=sl,
                          tp1=tp1, tp2=tp2, tp3=tp3, leverage=None,
                          strategies=strategies, is_active=True,
                          created_at=datetime.utcnow()))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        log.error("❌ Spot save %s: %s", sym, e)

    # ── تسجيل للتعلّم ──
    try:
        from ml_recorder import record_signal
        class _T: pass
        t = _T()
        t.symbol = sym; t.direction = "LONG"; t.entry = entry
        t.sl = sl; t.tp1 = tp1; t.tp2 = tp2; t.tp3 = tp3
        t.score = r["score"]; t.confidence = conf
        t.grade = grade; t.tier = "SP"
        t.strategies = strategies
        t.regime = r.get("regime", ""); t.range_pos = r["meta"].get("range_pos", 0.0)
        t.rsi = r["meta"].get("rsi", 0.0)
        t.volume_ratio = r["meta"].get("v_infl", 0.0)
        t.leverage = 1.0
        record_signal(t)
    except Exception as e:
        log.debug("spot ml: %s", e)

    # ── قناة تيليجرام ──
    try:
        from services.telegram import send_message
        from core.config import get_settings
        ch = get_settings().telegram_spot_channel_id
        if ch:
            try:
                from services.notifier import push_note
                await push_note("spot", "signal", f"🪙 إشارة سبوت: {sym}")
            except Exception:
                pass
            _p = lambda x: (x / entry - 1) * 100
            await send_message(ch,
                f"🪙 <b>WhaleX Spot — BUY</b>\n"
                f"⚡ <b>{sym}</b> · {ex}\n"
                f"{r['label']}\n\n"
                f"Entry  <b>{_fmt_px(entry)}</b>\n"
                f"Stop   {_fmt_px(sl)}  ({_p(sl):+.1f}%)\n"
                f"TP1    {_fmt_px(tp1)}  ({_p(tp1):+.1f}%)\n"
                f"TP2    {_fmt_px(tp2)}  ({_p(tp2):+.1f}%)\n"
                f"TP3    {_fmt_px(tp3)}  ({_p(tp3):+.1f}%)\n\n"
                f"Grade <b>{grade}</b> · Conf <b>{conf:.0f}%</b>\n"
                + " · ".join(r.get("why", [])[:4]) + "\n"
                f"🐋 <i>WhaleMind Spot</i>")
    except Exception as e:
        log.error("spot channel: %s", e)

    # ── 🌐 تنفيذ حقيقي على منصّة الإشارة نفسها (سبع منصّات) ──
    try:
        from services.spot_exec import buy as _spot_buy
        _res = await asyncio.to_thread(_spot_buy, ex, sym, entry)
        for _r in _res:
            if _r.get("ok"):
                log.info("🪙✅ %s نُفّذت على %s (%s)", sym, ex, str(_r.get("user"))[:8])
            elif _r.get("error"):
                log.info("🪙⚠️ %s على %s: %s", sym, ex, _r.get("error"))
    except Exception as e:
        log.error("spot exec: %s", e)


async def spot_loop():
    """حلقة العقل — قائمة بذاتها، أخطاؤها لا تغادرها."""
    log.info("🪙 Spot brain v1 starting")
    global _TRACK_STARTED
    if not _TRACK_STARTED:
        _TRACK_STARTED = True
        asyncio.create_task(tracker_loop())
    # 🪙🌐 الماسح الجديد: سبع منصّات · مساران مستقلّان (قاع · ارتداد · اختراق)
    #    القديم كان يطلب ترنداً صاعداً وقاعاً معاً — متناقضان، فصمت في السوق الصاعد.
    from radars.spot.universe_spot import refresh as _u_refresh, load as _u_load, age_sec as _u_age
    from radars.spot.scanner_spot import scan_universe as _scan_all
    while True:
        try:
            if _u_age() > 3600:
                await asyncio.to_thread(_u_refresh)
            rows = _u_load()
            if not rows:
                log.warning("🪙 كون السبوت فارغ — نعيد البناء")
                await asyncio.to_thread(_u_refresh)
                rows = _u_load()
            await _scan_all(rows, on_signal=_emit_signal,
                            cooldown=_last_sig, cooldown_sec=COOLDOWN)
        except Exception as e:
            log.error("spot_loop: %s", e)
        await asyncio.sleep(CYCLE)
