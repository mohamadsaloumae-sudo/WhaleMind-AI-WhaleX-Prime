"""
WhaleMind-Prime-Core — position_manager.py
═══════════════════════════════════════════════════════════════════
المنفذ السريع ومدير الطوارئ:

1. Pyramiding       — بدء 2x → رفع تلقائي عند تأكيد الانفجار
2. Trailing Stop    — متحرك ديناميكي بناءً على ATR
3. Claude AI        — استشارة طارئة عند تغير Order Book
4. Force Close      — إغلاق فوري بسعر السوق (يكسر حلقة AI)
5. Kill Switch      — إغلاق كل الصفقات دفعة واحدة
6. هروب تكتيكي      — استباقي قبل ضرب SL
7. إحصائيات         — لوحة التحكم في Mini App
═══════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import asyncio, logging, time, json
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from .engine import Signal

log = logging.getLogger("position_manager")

# تأكيد الاستمرارية للعين: يخزّن إنذار الانقلاب من الدورة السابقة لكل صفقة.
#   المفتاح: "SYMBOL_L" أو "SYMBOL_S". لا نغلق إلا إن صمد الانقلاب عبر قراءتين.
_reversal_warn = {}

# ═══════════════════════════════════════════════════════════════
# ─── DATA STRUCTURES ────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

class ExitReason(Enum):
    SL_HIT      = "sl_hit"
    TP1_HIT     = "tp1_hit"
    TP2_HIT     = "tp2_hit"
    TP3_HIT     = "tp3_hit"
    EXPLOSION   = "explosion"
    TACTICAL    = "tactical_exit"
    FORCE_CLOSE = "force_close"
    KILL_SWITCH = "kill_switch"

@dataclass
class Position:
    id: str
    user_id: str
    symbol: str
    direction: str
    entry: float
    amount: float
    leverage: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    tier: str = "B"
    grade: str = "B"
    # حالة TP
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    # Trailing
    trailing_active: bool = False
    trailing_sl: float = 0.0
    # Pyramiding
    pyramid_level: int = 1         # 1=2x, 2=5x, 3=10x
    pyramid_confirmed: bool = False
    original_leverage: float = 2.0
    # Explosion Mode
    explosion_mode: bool = False
    explosion_extreme: float = 0.0
    # AI Cooldown
    ai_last_called: int = 0
    ai_cooldown: int = 180  # 3 دقائق بين استدعاءات Claude
    # Tracking
    peak_price: float = 0.0
    status: str = "open"
    opened_at: int = field(default_factory=lambda: int(time.time()))
    last_warned: int = 0
    # Force Close Lock — لا AI بعد قرار المستخدم
    force_close_lock: bool = False
    # FVG zone من الإشارة
    fvg_zone: Optional[float] = None
    # نوع الرادار (futures للرئيسي وبيك هنتر، يُميَّز بـ tier)
    radar_type: str = "futures"
    breathe_alerted: bool = False   # أُرسل تنبيه اقتراب الوقف للقناة؟ (مرّة واحدة)


# ═══════════════════════════════════════════════════════════════
# ─── STATS ──────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

STATS = {
    "total": 0, "wins": 0, "losses": 0, "tactical": 0, "force_close": 0,
    "tp1_count": 0, "tp2_count": 0, "tp3_count": 0, "explosion_count": 0,
    "total_pnl_pct": 0.0,
}

def update_stats(reason: ExitReason, pnl_pct: float):
    STATS["total"] += 1
    STATS["total_pnl_pct"] += pnl_pct
    if reason == ExitReason.SL_HIT:
        STATS["losses"] += 1
    elif reason == ExitReason.FORCE_CLOSE:
        STATS["force_close"] += 1
        if pnl_pct > 0:
            STATS["wins"] += 1
        else:
            STATS["losses"] += 1
    elif reason == ExitReason.TACTICAL:
        STATS["tactical"] += 1
        if pnl_pct > 0:
            STATS["wins"] += 1
    else:
        STATS["wins"] += 1
        if reason == ExitReason.TP1_HIT:
            STATS["tp1_count"] += 1
        elif reason == ExitReason.TP2_HIT:
            STATS["tp2_count"] += 1
        elif reason in (ExitReason.TP3_HIT, ExitReason.EXPLOSION):
            STATS["tp3_count"] += 1
            if reason == ExitReason.EXPLOSION:
                STATS["explosion_count"] += 1

def get_stats_msg() -> str:
    t = STATS["total"]
    if t == 0:
        return "لا توجد إحصائيات بعد"
    wr = STATS["wins"] / t * 100
    avg = STATS["total_pnl_pct"] / t
    return (
        f"📊 <b>إحصائيات WhaleMind Prime</b>\n{'─' * 24}\n"
        f"إجمالي الإشارات: <b>{t}</b>\n"
        f"رابحة: <b>{STATS['wins']}</b> | خاسرة: <b>{STATS['losses']}</b>\n"
        f"هروب تكتيكي: <b>{STATS['tactical']}</b>\n"
        f"Force Close: <b>{STATS['force_close']}</b>\n"
        f"نسبة الفوز: <b>{wr:.1f}%</b>\n"
        f"متوسط الربح: <b>{avg:+.2f}%</b>\n"
        f"{'─' * 24}\n"
        f"TP1: {STATS['tp1_count']} | TP2: {STATS['tp2_count']} | "
        f"TP3+: {STATS['tp3_count']} | 💥: {STATS['explosion_count']}"
    )

def get_stats_dict() -> dict:
    t = STATS["total"]
    return {
        "total": t,
        "wins": STATS["wins"],
        "losses": STATS["losses"],
        "win_rate": round(STATS["wins"] / t * 100, 1) if t > 0 else 0,
        "avg_pnl": round(STATS["total_pnl_pct"] / t, 2) if t > 0 else 0,
        "tp1_count": STATS["tp1_count"],
        "tp2_count": STATS["tp2_count"],
        "explosion_count": STATS["explosion_count"],
    }


# ═══════════════════════════════════════════════════════════════
# ─── ACTIVE POSITIONS STORE ─────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

ACTIVE: dict[str, Position] = {}

# ═══════════════════════════════════════════════════════════════
# PERSISTENCE — حفظ الصفقات في DB (تبقى عبر restart)
# ═══════════════════════════════════════════════════════════════
import sqlite3 as _sqlite
import json as _json
import time as _time
from dataclasses import asdict as _asdict, fields as _fields

POS_DB = "/opt/whalex/positions.db"


def _pos_db_init():
    conn = _sqlite.connect(POS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS active_positions (
            id TEXT PRIMARY KEY,
            data TEXT,
            status TEXT,
            updated_at INTEGER
        )
    """)
    conn.commit()
    conn.close()


def _pos_save(pos):
    """Save/update a position in DB."""
    try:
        conn = _sqlite.connect(POS_DB)
        conn.execute(
            "INSERT OR REPLACE INTO active_positions (id, data, status, updated_at) VALUES (?,?,?,?)",
            (pos.id, _json.dumps(_asdict(pos)), pos.status, int(_time.time()))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.error("pos_save error: %s", e)


def _pos_delete(pos_id):
    """Delete a position from DB."""
    try:
        conn = _sqlite.connect(POS_DB)
        conn.execute("DELETE FROM active_positions WHERE id=?", (pos_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        log.error("pos_delete error: %s", e)


def _pos_load_all():
    """Load all open positions from DB (on startup)."""
    try:
        _pos_db_init()
        conn = _sqlite.connect(POS_DB)
        rows = conn.execute("SELECT data FROM active_positions WHERE status='open'").fetchall()
        conn.close()
        valid = {f.name for f in _fields(Position)}
        out = []
        for (data,) in rows:
            d = _json.loads(data)
            d = {k: v for k, v in d.items() if k in valid}
            out.append(Position(**d))
        return out
    except Exception as e:
        log.error("pos_load_all error: %s", e)
        return []


async def add_position(pos: Position):
    pos.peak_price = pos.entry
    ACTIVE[pos.id] = pos
    _pos_save(pos)
    log.info("Position opened: %s %s @%.6f lev=%.0fx", pos.symbol, pos.direction, pos.entry, pos.leverage)
    src = "Peak Hunter" if pos.radar_type == "futures" and getattr(pos, "tier", "") == "PH" else "Radar"
    msg = (
        f"🟢 <b>POSITION OPENED</b> · {pos.direction} · {pos.leverage:.0f}x\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"<code>{pos.symbol}</code>\n\n"
        f"Entry   <code>{pos.entry:.6g}</code>\n"
        f"Stop    <code>{pos.sl:.6g}</code>\n"
        f"TP1     <code>{pos.tp1:.6g}</code>\n"
        f"TP2     <code>{pos.tp2:.6g}</code>\n"
        f"TP3     <code>{pos.tp3:.6g}</code>\n\n"
        f"Grade <b>{pos.grade}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📡 Now monitoring · auto-managed"
    )
    # بيك هنتر يرسل رسالته الغنية بنفسه → لا نكرر POSITION OPENED له
    is_peak_hunter = (pos.radar_type == "futures" and getattr(pos, "tier", "") == "PH")
    if not is_peak_hunter:
        try:
            await notify(pos.user_id, msg)
        except Exception as e:
            log.debug("open notify error: %s", e)

async def remove_position(pos_id: str):
    ACTIVE.pop(pos_id, None)
    _pos_delete(pos_id)

async def force_close_all(reason: str = "kill_switch"):
    """Kill Switch — إغلاق كل الصفقات فوراً"""
    positions = list(ACTIVE.values())
    for pos in positions:
        pos.force_close_lock = True
        price = await get_price(pos.symbol)
        if price:
            pnl_pct = calc_pnl(pos, price)
            await _close_position(pos, price, ExitReason.KILL_SWITCH, pnl_pct)
    log.critical("Kill Switch: %d positions closed", len(positions))


# ═══════════════════════════════════════════════════════════════
# ─── PRICE FETCHER ──────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def get_price(symbol: str) -> Optional[float]:
    try:
        import httpx
        sym = symbol.replace("/", "").replace("-", "")
        if not sym.endswith("USDT"):
            sym += "USDT"
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={sym}")
            return float(r.json()["price"])
    except:
        return None

async def get_order_book(symbol: str) -> dict:
    try:
        import httpx
        sym = symbol.replace("/", "").replace("-", "")
        if not sym.endswith("USDT"):
            sym += "USDT"
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"https://fapi.binance.com/fapi/v1/depth?symbol={sym}&limit=20")
            d = r.json()
            bids = sum(float(b[1]) for b in d.get("bids", [])[:10])
            asks = sum(float(a[1]) for a in d.get("asks", [])[:10])
            return {
                "bids": bids,
                "asks": asks,
                "imbalance": (bids - asks) / (bids + asks) if (bids + asks) > 0 else 0,
                "spread": float(d["asks"][0][0]) - float(d["bids"][0][0]) if d.get("asks") and d.get("bids") else 0,
            }
    except:
        return {}


# ═══════════════════════════════════════════════════════════════
# ─── PYRAMIDING — التعزيز الهرمي ────────────────────────────────
# ═══════════════════════════════════════════════════════════════

PYRAMID_LEVELS = {
    1: {"leverage_mult": 1.0, "desc": "دخول أولي 2x"},   # 2x
    2: {"leverage_mult": 2.5, "desc": "تأكيد TP1 → 5x"},  # 5x
    3: {"leverage_mult": 5.0, "desc": "انفجار مؤكد → 10x"}, # 10x
}

async def check_pyramiding(pos: Position, price: float) -> bool:
    """
    التعزيز الهرمي:
    TP1 مُصاب + موافقة Guardian → رفع الرافعة
    يعيد True إذا تم التعزيز
    """
    if pos.pyramid_level >= 3 or pos.force_close_lock:
        return False

    is_long = pos.direction == "LONG"

    # شرط الانتقال للمستوى 2 (2x → 5x)
    if pos.pyramid_level == 1 and pos.tp1_hit:
        # تأكيد إضافي: الدلتا إيجابية
        ob = await get_order_book(pos.symbol)
        imbalance = ob.get("imbalance", 0)

        confirm = (imbalance > 0.2 if is_long else imbalance < -0.2)
        if confirm:
            new_lev = pos.original_leverage * 2.5
            pos.leverage = min(new_lev, 25.0)
            pos.pyramid_level = 2
            await notify(pos.user_id,
                f"📈 <b>PYRAMIDING · Level 2</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"<code>{pos.symbol}</code> · {pos.direction}\n\n"
                f"TP1 secured ✅\n"
                f"Leverage raised → <b>{pos.leverage:.0f}x</b>\n"
                f"OBI {imbalance:+.2f} · momentum positive")
            log.info("Pyramid L2: %s lev=%.0fx", pos.symbol, pos.leverage)
            return True

    # شرط الانتقال للمستوى 3 (5x → 10x)
    if pos.pyramid_level == 2 and pos.tp2_hit and pos.explosion_mode:
        new_lev = pos.original_leverage * 5.0
        pos.leverage = min(new_lev, 50.0)
        pos.pyramid_level = 3
        await notify(pos.user_id,
            f"💥 <b>Pyramiding Level 3 — EXPLOSION MODE</b>\n"
            f"{pos.symbol} | رافعة → <b>{pos.leverage:.0f}x</b>\n"
            f"⚡ الانفجار مؤكد — الكل مع الحوت!")
        log.info("Pyramid L3: %s lev=%.0fx", pos.symbol, pos.leverage)
        return True

    return False


# ═══════════════════════════════════════════════════════════════
# ─── CLAUDE AI EMERGENCY ADVISOR ────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def claude_emergency_analysis(pos: Position, price: float, ob: dict, alert_reason: str) -> Optional[str]:
    """
    استشارة Claude AI الطارئة — غير متزامن تماماً
    يُستدعى فقط عند:
    1. تغير مفاجئ في Order Book ضد الصفقة
    2. شذوذ في الدلتا
    3. حركة سعرية مفاجئة
    لا يُستدعى بشكل متكرر — cooldown 3 دقائق
    """
    now = int(time.time())
    if now - pos.ai_last_called < pos.ai_cooldown:
        return None

    pos.ai_last_called = now

    is_long = pos.direction == "LONG"
    pnl_pct = calc_pnl(pos, price)

    prompt = f"""أنت مستشار تداول طارئ لنظام WhaleMind Prime. حلل هذا الوضع وأعطِ قرارك في 2 جملة فقط:

الصفقة: {pos.symbol} {pos.direction} | دخول: {pos.entry:.4f} | الآن: {price:.4f}
PnL الحالي: {pnl_pct:+.2f}%
الرافعة: {pos.leverage}x | Grade: {pos.grade}
Order Book: Bids={ob.get('bids', 0):.0f} Asks={ob.get('asks', 0):.0f} Imbalance={ob.get('imbalance', 0):+.3f}
سبب الاستدعاء: {alert_reason}

هل تنصح بـ:
A) الاستمرار — الوضع مؤقت
B) هروب تكتيكي — اخرج الآن بـ {pnl_pct:+.2f}%
C) انتظار — ضع SL أقرب

أجب بحرف واحد (A/B/C) ثم جملة تفسيرية واحدة بالعربية."""

    try:
        import httpx
        from core.config import get_settings
        s = get_settings()

        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": s.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-5",
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            result = r.json()
            reply = result["content"][0]["text"].strip()
            log.info("Claude AI: %s %s → %s", pos.symbol, alert_reason, reply[:50])
            return reply
    except Exception as e:
        log.error("Claude AI error: %s", e)
        return None


# ═══════════════════════════════════════════════════════════════
# ─── TACTICAL EXIT ANALYZER ─────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def is_real_reversal(symbol: str, is_long: bool, opened_at: float = 0) -> tuple[bool, str]:
    """تمييز الانقلاب الحقيقي من الزبزبة — قراءة عمق OB (depth=100).
    فلسفة: القمة عند الانهيار = معركة شرسة (تذبذب طبيعي).
    لا نخرج للزبزبة. نخرج فقط عند انقلاب بنيوي مؤكّد:
      • اختلال قوي مستمر قرب السعر + جدار معاكس ضخم + تآكل صفّنا."""
    # ═══════════════════════════════════════════════════════════
    # العين الذكية (V2) — ميزان ديناميكي + وعي الموقع
    #   pressure_score: -1 (بائعون مسيطرون) → +1 (مشترون مسيطرون)
    #   العتبة تتدرّج بالموقع: مرنة عند القاع، يقظة عند القمة
    # ═══════════════════════════════════════════════════════════
    try:
        from quant_engine.order_book_analyzer import analyze_order_book
        from quant_engine.hawk_eye import read_market_structure
        from radars.futures.engine import fetch_klines_async as _fk_eye

        _a = await analyze_order_book(symbol, check_spoofing=True)
        if _a is not None:
            _ps = getattr(_a, "pressure_score", 0.0)

            # الموقع: range_pos من القمة/القاع التاريخي (30 يوم)
            _range_pos = 0.5
            try:
                _ms = await read_market_structure(symbol, _fk_eye)
                _hi = getattr(_ms, "period_high", 0.0)
                _lo = getattr(_ms, "period_low", 0.0)
                _pr = _hi - (getattr(_ms, "resistance_distance_pct", 0.0) / 100.0 * _hi) if _hi else 0.0
                # نحسب السعر الحالي مباشرة من آخر شمعة (أوثق)
                _kl = await _fk_eye(symbol, "15m", 3)
                _cur = _kl[-1].close if _kl else 0.0
                if _hi > _lo > 0 and _cur > 0:
                    _range_pos = max(0.0, min(1.0, (_cur - _lo) / (_hi - _lo)))
            except Exception as _e2:
                log.debug("eye range_pos %s: %s", symbol, _e2)

            # العتبة حسب الموقع — منطق معكوس لكل تكتيك:
            if is_long:
                # LONG: يقظ عند القمة (يخشى الهبوط)، مرن عند القاع (مكانه المثالي)
                if _range_pos < 0.40:
                    _thr = 0.45
                elif _range_pos < 0.70:
                    _thr = 0.30
                else:
                    _thr = 0.15
            else:
                # SHORT: مرن عند القمة (الهبوط بدأ، مكانه المثالي — نصبر على الارتداد البسيط)،
                #   يقظ عند القاع (هبط كثيراً، قد يرتدّ — نحمي الربح)
                if _range_pos > 0.60:
                    _thr = 0.45
                elif _range_pos > 0.30:
                    _thr = 0.30
                else:
                    _thr = 0.15

            # تأكيد الاستمرارية: لا نغلق على لقطة واحدة (تذبذب/امتصاص لحظي).
            #   الانقلاب يجب أن يصمد عبر قراءتين متتاليتين (~10s) ليُعتبر حقيقياً.
            _against = (is_long and _ps < -_thr) or ((not is_long) and _ps > _thr)
            _wkey = f"{symbol}_{'L' if is_long else 'S'}"
            if _against:
                if _reversal_warn.get(_wkey):
                    _reversal_warn.pop(_wkey, None)
                    _side_txt = "بائعون مسيطرون" if is_long else "مشترون مسيطرون"
                    return True, f"انقلاب مؤكّد ({_side_txt} {_ps:+.2f} @ موقع {_range_pos:.0%}, صمد قراءتين)"
                else:
                    _reversal_warn[_wkey] = True
                    log.debug("إنذار انقلاب %s: ضغط %+.2f @ موقع %.0f%% — بانتظار تأكيد القراءة التالية",
                              _wkey, _ps, _range_pos*100)
            else:
                _reversal_warn.pop(_wkey, None)
    except Exception as _e:
        log.debug("smart eye V2 %s: %s", symbol, _e)
    # الخطوة 0: فخاخ WebSocket اللحظية — ارتداد مفتعل بفخ وهمي؟ لا نخرج (تنفّس)
    try:
        from quant_engine.ob_stream import get_signals
        _sw = symbol.replace("/","").replace("-","")
        if not _sw.endswith("USDT"): _sw += "USDT"
        _sp = get_signals(_sw).get("spoof", [])
        if not is_long and any(x["side"]=="bid" for x in _sp):
            return False, "فخ شراء وهمي لحظي — ارتداد مفتعل، الهبوط مستمر"
        if is_long and any(x["side"]=="ask" for x in _sp):
            return False, "فخ بيع وهمي لحظي — هبوط مفتعل، الصعود مستمر"
    except Exception as _e:
        log.debug("ob reversal %s: %s", symbol, _e)
    # ─── الخطوة 1: عين الصقر — هل وصل السعر الدعم/المقاومة فعلاً؟ ───
    # فلسفة فخ القطيع: لو السعر لم يصل الدعم بعد، فأي ارتداد الآن = فخ
    # (الحيتان يخيفون القطيع ليهربوا، ثم يكمل الهبوط). لا نخرج للفخ.
    try:
        from radars.futures.engine import fetch_klines_async
        from quant_engine.hawk_eye import read_market_structure
        ms = await read_market_structure(symbol, fetch_klines_async)
        # ملاحظة: التنفّس صار رأياً لا قراراً (العين الديناميكية + الجدار يقرّران).
        #   نسجّل فقط، لا return — فلا يُحتجَز LONG/SHORT خاسر بانتظار مستوى بعيد (درس GWEI -15%).
        if not is_long:  # SHORT
            if ms.support_distance_pct > 1.5 and not ms.at_support:
                log.debug("breathe-advisory %s SHORT: لم يصل الدعم (%+.1f%%) — رأي لا قرار",
                          symbol, ms.support_distance_pct)
        else:  # LONG
            if ms.resistance_distance_pct > 1.5 and not ms.at_resistance:
                log.debug("breathe-advisory %s LONG: لم يصل المقاومة (%+.1f%%) — رأي لا قرار",
                          symbol, ms.resistance_distance_pct)
    except Exception as _e:
        log.debug("hawk in reversal %s: %s", symbol, _e)

    # ─── الخطوة 2: الفجوات السعرية — هل توجد فجوة لم تُملأ تجذب السعر؟ ───
    # الحيتان تترك فجوات عند الدفع العنيف، والسعر يعود لملئها.
    # للـSHORT: فجوة صاعدة تحت السعر = السعر سينزل لها = الهبوط مستمر = لا نخرج
    try:
        from radars.futures.engine import fetch_klines_async as _fk, find_fvg as _ffvg
        k15 = await _fk(symbol, "15m", 60)
        if k15 and len(k15) >= 10:
            cur_price = k15[-1].close
            fvgs = _ffvg(k15)
            if not is_long:  # SHORT
                # فجوة صاعدة تحت السعر الحالي ولم تُملأ بعد (top أقل من السعر)
                gap_below = [g for g in fvgs if g["type"] == "bullish" and g["top"] < cur_price * 0.998]
                if gap_below:
                    nearest = max(gap_below, key=lambda g: g["top"])
                    dist = (cur_price - nearest["mid"]) / cur_price * 100
                    if dist > 0.8:
                        log.debug("breathe-advisory %s SHORT: فجوة صاعدة (%.1f%% تحت) — رأي لا قرار", symbol, dist)
            else:  # LONG
                gap_above = [g for g in fvgs if g["type"] == "bearish" and g["bottom"] > cur_price * 1.002]
                if gap_above:
                    nearest = min(gap_above, key=lambda g: g["bottom"])
                    dist = (nearest["mid"] - cur_price) / cur_price * 100
                    if dist > 0.8:
                        log.debug("breathe-advisory %s LONG: فجوة هابطة (%.1f%% فوق) — رأي لا قرار", symbol, dist)
    except Exception as _e:
        log.debug("fvg in reversal %s: %s", symbol, _e)

    try:
        import httpx
        sym = symbol.replace("/", "").replace("-", "")
        if not sym.endswith("USDT"):
            sym += "USDT"
        async with httpx.AsyncClient(timeout=6) as cl:
            r = await cl.get(f"https://fapi.binance.com/fapi/v1/depth?symbol={sym}&limit=100")
            d = r.json()
        bids_raw = [(float(b[0]), float(b[1])) for b in d.get("bids", [])]
        asks_raw = [(float(a[0]), float(a[1])) for a in d.get("asks", [])]
        if not bids_raw or not asks_raw:
            return False, ""

        bid_vol = sum(b[1] for b in bids_raw)
        ask_vol = sum(a[1] for a in asks_raw)
        # اختلال قرب السعر (أول 15 مستوى = الأهم)
        near_bid = sum(b[1] for b in bids_raw[:15])
        near_ask = sum(a[1] for a in asks_raw[:15])
        near_imb = (near_bid - near_ask) / (near_bid + near_ask) if (near_bid + near_ask) > 0 else 0
        # جدار معاكس ضخم
        avg_b = bid_vol / len(bids_raw) if bids_raw else 0
        avg_a = ask_vol / len(asks_raw) if asks_raw else 0
        max_bid_wall = max((b[1] for b in bids_raw), default=0)
        max_ask_wall = max((a[1] for a in asks_raw), default=0)
        bid_wall_ratio = max_bid_wall / avg_b if avg_b > 0 else 0
        ask_wall_ratio = max_ask_wall / avg_a if avg_a > 0 else 0

        # للـSHORT: انقلاب صاعد حقيقي = مشترون يسيطرون بعمق
        #   near_imb موجب قوي (>0.45) + جدار شراء ضخم (>6x)
        # للـLONG: انقلاب هابط حقيقي = بائعون يسيطرون بعمق
        # كشف الانقلاب المبدئي (القراءة الأولى)
        if not is_long:  # SHORT
            strong = near_imb > 0.45 and bid_wall_ratio > 6.0
        else:  # LONG
            strong = near_imb < -0.45 and ask_wall_ratio > 6.0
        if not strong:
            return False, ""

        # ═══ تمييز الجدار بالأداة الموحّدة (نفس عين الرادار): حقيقي/وهمي/جبل ثلجي ═══
        # الجدار الحقيقي أو الجبل الثلجي → انقلاب فعلي (نخرج). الوهمي → فخ قطيع (نصبر).
        try:
            from radars.explosion.scout import classify_wall
            wside = "bid" if not is_long else "ask"  # SHORT يراقب جدار الشراء (دعم/انقلاب صاعد)
            w = await classify_wall(sym, side=wside)
        except Exception:
            return False, ""
        if not w.get("valid"):
            return False, ""
        wtype = w.get("type", "")
        # فترة السماح: صفقة وليدة (<10د) لا تُغلق بإشارة الجدار — فقط الميزان الديناميكي العنيف يقرّر
        import time as _t_wall
        # الجدار صار رأياً لا قراراً: الميزان الديناميكي (pressure_score) يشمل الجدران
        #   والـ iceberg أصلاً، ومحميّ بتأكيد الاستمرارية. نسجّل فقط، لا نغلق هنا (درس ETH "جبل ثلجي 0x").
        if wtype == "حقيقي":
            log.debug("wall-advisory %s: جدار حقيقي معاكس %.0fx — رأي (الميزان يقرّر)", symbol, w.get('ratio',0))
        if wtype == "جبل_ثلجي":
            log.debug("wall-advisory %s: جبل ثلجي معاكس — رأي (الميزان يقرّر)", symbol)
        if wtype == "وهمي":
            return False, "جدار وهمي اختفى — فخ قطيع، الاتجاه مستمر"
        return False, ""  # لا_جدار أو غير معروف → لا انقلاب
    except Exception:
        return False, ""


async def should_tactical_exit(pos: Position, price: float, ob: dict, ls_change: float) -> tuple[bool, str]:
    """خروج تكتيكي — انقلاب الأوردر بوك الحقيقي فقط (فلسفة صيد القمم).
    لا نخرج للزبزبة، لا لحركة سعر، لا لـspread. فقط انقلاب OB بنيوي عميق.
    SL و TP منفصلان في monitor_position (يبقيان للحماية والجني)."""
    if pos.force_close_lock:
        return False, ""

    is_long = pos.direction == "LONG"
    pnl_pct = calc_pnl(pos, price)

    # ضابط الوقت: لا خروج تكتيكي في أول 90 ثانية
    import time as _t
    age_sec = _t.time() - getattr(pos, "opened_at", 0)
    if age_sec < 90:
        return False, ""

    # الشرط الوحيد: انقلاب الأوردر بوك البنيوي الحقيقي (depth=100 + جدار ضخم)
    real_rev, rev_reason = await is_real_reversal(pos.symbol, is_long, getattr(pos, "opened_at", 0))
    if real_rev:
        return True, f"🔻 {rev_reason} | PnL {pnl_pct:+.1f}%"

    return False, ""


# ═══════════════════════════════════════════════════════════════
# ─── POSITION MONITOR ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def calc_pnl(pos: Position, price: float) -> float:
    if pos.direction == "LONG":
        return (price - pos.entry) / pos.entry * 100 * pos.leverage
    else:
        return (pos.entry - price) / pos.entry * 100 * pos.leverage

async def notify(user_id: str, msg: str, event_type: str = "alert", data: dict = None, to_channel: bool = True):
    """إرسال إشعار: للقناة + للمستخدم + WebSocket"""
    if to_channel:
        try:
            from services.telegram import send_message, _kb_channel
            from core.config import get_settings
            s = get_settings()
            ch = s.telegram_channel_futures
            if ch:
                await send_message(ch, msg, reply_markup=_kb_channel())
        except Exception as e:
            log.debug("notify channel error: %s", e)
    try:
        if user_id and str(user_id).lstrip("-").isdigit():
            from services.telegram import TG
            await TG.send_message(user_id, msg)
    except Exception as e:
        log.debug("notify user error: %s", e)
    try:
        from routers.ws import registry
        await registry.broadcast({"event": event_type, "user_id": user_id, "message": msg, "data": data or {}})
    except Exception as e:
        log.debug("notify ws error: %s", e)

# ═══════════════════════════════════════════════════════════
#  العيون عند الإغلاق: نغلق أم نتنفّس؟ (يخدم بوّابتَي SL و HARD_STOP)
#  أرضية pnl صلبة لا تُخترق. فوقها نستشير is_real_reversal:
#    انقلاب مؤكد→نغلق | فخ مكشوف→نتنفّس | صمت→نغلق (احترام الوقف).
#  القرار يُخزَّن 60 ثانية لكل صفقة (يمنع إغراق Binance وتضارب البوّابتين).
# ═══════════════════════════════════════════════════════════
PNL_HARD_FLOOR = -15.0   # أرضية الخسارة المطلقة (pnl مُرفّع)
_REV_CACHE: dict = {}    # pos.id -> (ts, breathe, reason)

async def _should_breathe(pos: "Position", price: float, pnl_pct: float) -> tuple:
    """True = تنفّس (لا تغلق هذه الدورة). False = أغلق. السبب للّوج."""
    if pnl_pct <= PNL_HARD_FLOOR:
        return False, f"أرضية صلبة {pnl_pct:.1f}% <= {PNL_HARD_FLOOR:.0f}%"
    import time as _t
    _now = _t.time()
    _c = _REV_CACHE.get(pos.id)
    if _c and (_now - _c[0]) < 60:
        return _c[1], _c[2]
    real_rev, reason = await is_real_reversal(pos.symbol, pos.direction == "LONG", getattr(pos, "opened_at", 0))
    if real_rev:
        dec = (False, f"انقلاب مؤكد — {reason}")
    elif reason:
        dec = (True, reason)
    else:
        dec = (False, "لا دليل فخ — احترام الوقف")
    _REV_CACHE[pos.id] = (_now, dec[0], dec[1])
    return dec


async def monitor_position(pos: Position):
    """
    المراقبة الحية لصفقة واحدة:
    SL/TP → Trailing → Pyramiding → Claude AI → Tactical Exit
    """
    price = await get_price(pos.symbol)
    if not price:
        return

    ob = await get_order_book(pos.symbol)
    is_long = pos.direction == "LONG"
    pnl_pct = calc_pnl(pos, price)

    # تحديث قمة السعر
    if is_long:
        if price > pos.peak_price:
            pos.peak_price = price
    else:
        if price < pos.peak_price or pos.peak_price == 0:
            pos.peak_price = price

    # ls_change تقريبي
    ls_change = (price - pos.entry) / pos.entry * 100 if pos.entry > 0 else 0

    # Force Close lock — لا شيء بعد قرار المستخدم
    if pos.force_close_lock:
        return

    # ─ تنبيه استباقيّ: السعر يقترب من الوقف المكتوب — نُعلم المشترك قبل ضربه ─
    #   ليملك وقتاً لرفع وقفه أو إلغائه إن أراد متابعة البوت. مرّة واحدة لكل صفقة.
    if pos.entry > 0 and pos.sl > 0 and not pos.breathe_alerted:
        _dist_sl = abs(price - pos.sl) / pos.sl * 100
        _approaching = (is_long and price > pos.sl) or (not is_long and price < pos.sl)
        if _approaching and _dist_sl <= 1.5:
            pos.breathe_alerted = True
            await notify(pos.user_id,
                f"⚠️ <b>{pos.symbol} {pos.direction} — السعر يقترب من الوقف</b>\n"
                f"البوت يراقب لحظياً. إن رصد تذبذباً مؤقّتاً (لا انعكاساً), سيستمرّ في الصفقة.\n"
                f"📌 <b>استعدّ: ارفع وقف الخسارة أو ألغِه إن أردت متابعة البوت.</b>\n"
                f"<i>نُغلق فوراً عند تأكّد انقلاب حقيقيّ.</i>")

    # ─ شبكة أمان مطلقة: أرضية pnl صلبة (كل دورة، قبل أي منطق وقف) ─
    if pnl_pct <= PNL_HARD_FLOOR:
        log.warning("PNL FLOOR %s %s pnl=%.1f%% — إغلاق فوري",
                    pos.symbol, pos.direction, pnl_pct)
        await _close_position(pos, price, ExitReason.SL_HIT, pnl_pct)
        return

    # ─ حد أقصى صلب للخسارة (شبكة أمان مطلقة — يمنع كوارث -34%) ─
    #   مهما كان SL المحسوب (ATR قد يكون واسعاً)، لا نسمح بخسارة > 8%
    # HARD STOP بحركة السعر (لا pnl المُرفّع): يمنع الطرد عند ضوضاء العملات المتذبذبة.
    #   السبب: pnl=-5% مع رافعة 3x = حركة 1.67% فقط = داخل ضوضاء عملة تتذبذب ±13%،
    #   فكان يطرد الشورت الصحيح عند أول ارتداد. الآن: حركة سعر فعلية ≥7% (خارج الضوضاء).
    price_move_pct = abs(price - pos.entry) / pos.entry * 100 if pos.entry > 0 else 0
    against = (is_long and price < pos.entry) or (not is_long and price > pos.entry)
    HARD_STOP_MOVE = 4.5  # حركة 4.5% (=13.5% مع رافعة): يقص الخسائر الكبيرة، الأرباح (TP) تبقى
    if against and price_move_pct >= HARD_STOP_MOVE:
        _br, _why = await _should_breathe(pos, price, pnl_pct)
        if _br:
            log.info("HARD STOP مؤجَّل (تنفّس) %s: %s | حركة=%.1f%% pnl=%.1f%%",
                     pos.symbol, _why, price_move_pct, pnl_pct)
        else:
            log.warning("HARD STOP %s %s @ حركة=%.1f%% pnl=%.1f%% (%s)",
                        pos.symbol, pos.direction, price_move_pct, pnl_pct, _why)
            await _close_position(pos, price, ExitReason.SL_HIT, pnl_pct)
            return

    # ─ SL / Trailing Stop ─
    sl_hit = (is_long and price <= pos.sl) or (not is_long and price >= pos.sl)
    if sl_hit:
        # Trailing رابح (جني فوري) أم SL خسارة (استشر العيون)؟
        if pos.tp1_hit and pnl_pct > 0:
            # Trailing Stop بعد TP1 = إغلاق رابح، يُؤخذ فوراً بلا تنفّس
            await notify(pos.user_id,
                f"🔒 <b>Trailing Stop — ربح محمي</b>\n"
                f"{pos.symbol} {pos.direction}\n"
                f"💰 الربح المُحقق: <b>+{pnl_pct:.2f}%</b>\n"
                f"✅ تم تأمين الأرباح بعد TP1\n"
                f"<i>Trailing Stop يحمي مكاسبك</i>")
            await _close_position(pos, price, ExitReason.TP1_HIT, pnl_pct)
            return
        # SL خسارة: العيون تقرّر — انقلاب مؤكد نغلق، فخ مكشوف نتنفّس
        _br, _why = await _should_breathe(pos, price, pnl_pct)
        if _br:
            log.info("SL مؤجَّل (تنفّس) %s: %s | pnl=%.1f%%", pos.symbol, _why, pnl_pct)
        else:
            log.info("SL إغلاق %s: %s | pnl=%.1f%%", pos.symbol, _why, pnl_pct)
            await _close_position(pos, price, ExitReason.SL_HIT, pnl_pct)
            return

    # ─ TP1 ─
    tp1_hit = (is_long and price >= pos.tp1) or (not is_long and price <= pos.tp1)
    if tp1_hit and not pos.tp1_hit:
        pos.tp1_hit = True
        pos.trailing_active = True
        # تحريك SL إلى نقطة التعادل
        pos.sl = pos.entry * (1.001 if is_long else 0.999)
        pos.trailing_sl = pos.sl

        profit = abs((price - pos.tp1) / pos.entry * 100)
        await notify(pos.user_id,
            f"🎯 <b>TARGET 1 HIT</b> · +{profit:.2f}%\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<code>{pos.symbol}</code> · {pos.direction}\n\n"
            f"Profit secured  <b>+{profit:.2f}%</b>\n"
            f"Stop moved to   breakeven 🛡️\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"▶ Holding for TP2 · capital protected")

        # Pyramiding check
        await check_pyramiding(pos, price)

    # ─ TP2 ─
    tp2_hit = (is_long and price >= pos.tp2) or (not is_long and price <= pos.tp2)
    if tp2_hit and not pos.tp2_hit and pos.tp1_hit:
        pos.tp2_hit = True
        pos.explosion_mode = True

        await notify(pos.user_id,
            f"🚀 <b>TARGET 2 HIT</b> · Explosion Mode\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<code>{pos.symbol}</code> · {pos.direction}\n\n"
            f"💥 Breakout confirmed\n"
            f"⬆️ Next target: TP3")

        await check_pyramiding(pos, price)

    # ─ TP3 ─
    tp3_hit = (is_long and price >= pos.tp3) or (not is_long and price <= pos.tp3)
    if tp3_hit and pos.tp2_hit:
        profit = abs(pnl_pct)
        await notify(pos.user_id,
            f"🏆 <b>TP3 مصاب</b> — {pos.symbol}\n"
            f"💰 الربح الكامل: <b>+{profit:.2f}%</b>\n"
            f"✅ تم إغلاق الصفقة بالكامل\n"
            f"🎊 <i>إشارة WhaleMind Prime ناجحة!</i>")
        await _close_position(pos, price, ExitReason.TP3_HIT, pnl_pct)
        return

    # ─ Trailing Stop ─
    if pos.trailing_active and pos.trailing_sl > 0:
        # المسافة موسّعة (0.5→1.2): trailing يتحمّل تذبذب العملات المنفجرة،
        # لا يخرج على ارتداد بسيط — يركب الهبوط/الصعود الكامل (BEAT واصلت -27%).
        TRAIL_MULT = 1.2
        if is_long:
            new_sl = price - (pos.tp1 - pos.entry) * TRAIL_MULT
            if new_sl > pos.trailing_sl:
                pos.trailing_sl = new_sl
                pos.sl = new_sl
        else:
            new_sl = price + (pos.entry - pos.tp1) * TRAIL_MULT
            if new_sl < pos.trailing_sl or pos.trailing_sl == 0:
                pos.trailing_sl = new_sl
                pos.sl = new_sl

    # ─ Claude AI Emergency ─
    now = int(time.time())
    imbalance = ob.get("imbalance", 0)
    ai_alert_needed = (
        (is_long and imbalance < -0.35) or
        (not is_long and imbalance > 0.35)
    )

    if False and ai_alert_needed and now - pos.ai_last_called > pos.ai_cooldown:
        alert_reason = f"OB Imbalance انقلب ({imbalance:+.2f})"
        ai_reply = await claude_emergency_analysis(pos, price, ob, alert_reason)

        if ai_reply:
            # إرسال تحليل Claude للمستخدم
            await notify(pos.user_id,
                f"🤖 <b>Claude AI تحليل طارئ</b> — {pos.symbol}\n"
                f"{'📈' if is_long else '📉'} {pos.direction} | PnL: {pnl_pct:+.2f}%\n"
                f"⚠️ {alert_reason}\n"
                f"{'─' * 20}\n"
                f"<i>{ai_reply}</i>")

            # إذا قرر Claude B (هروب) → تنفيذ تكتيكي
            if ai_reply.upper().startswith("B") and pnl_pct > -1.0:
                await _close_position(pos, price, ExitReason.TACTICAL, pnl_pct)
                return

    # ─ Tactical Exit Check ─
    # مراقبة ديناميكية: شديدة بعد TP1 (حماية الربح)، يقظة قبله (خروج وقائي).
    #   الحلقة الضائعة كانت 300ث (نوم 5 دقائق) — الانقلاب يضرب الستوب قبل الفحص.
    _tac_interval = 20 if pos.tp1_hit else 45
    if now - pos.last_warned > _tac_interval:
        tactical, reason = await should_tactical_exit(pos, price, ob, ls_change)
        if tactical:
            pos.last_warned = now
            tp_status = "TP2" if pos.tp2_hit else "TP1" if pos.tp1_hit else "قبل TP1"
            profit_str = f"+{abs(pnl_pct):.2f}%" if pnl_pct > 0 else f"{pnl_pct:.2f}%"

            # الهروب التكتيكي = إغلاق فوري دائماً (حماية استباقية حقيقية)
            # عند انقلاب Order Book ضدنا، البقاء = خسارة أكبر عند SL
            # رسالة واحدة فقط (POSITION CLOSED من _close_position) — لا تكرار
            log.info("Tactical exit %s: %s", pos.symbol, reason)
            await _close_position(pos, price, ExitReason.TACTICAL, pnl_pct)
            return


# ═══════════════════════════════════════════════════════════════
# ─── POSITION CLOSE ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def _close_position(pos: Position, price: float, reason: ExitReason, pnl_pct: float):
    """إغلاق الصفقة وإرسال الإشعار"""
    pos.status = "closed"
    await remove_position(pos.id)
    update_stats(reason, pnl_pct)
    # ═══ ربط النتيجة بالنموذج (يكمل درس التعلّم: فتح + نتيجة) ═══
    try:
        from ml_recorder import update_result_by_match
        _result = "win" if pnl_pct > 0 else "loss"
        update_result_by_match(pos.symbol, pos.direction, pos.entry,
                               _result, price, pnl_pct)
    except Exception as _e:
        log.debug("ML update error: %s", _e)

    emoji = {
        ExitReason.SL_HIT: "🔴",
        ExitReason.TP1_HIT: "🟡",
        ExitReason.TP2_HIT: "🟠",
        ExitReason.TP3_HIT: "🟢",
        ExitReason.EXPLOSION: "💥",
        ExitReason.TACTICAL: "🏃",
        ExitReason.FORCE_CLOSE: "🛑",
        ExitReason.KILL_SWITCH: "🚨",
    }.get(reason, "⚪")

    is_profit = pnl_pct >= 0
    head_emoji = "✅" if is_profit else "🔴"
    head_word = "POSITION CLOSED" if is_profit else "POSITION CLOSED"
    side_word = "PROFIT" if is_profit else "LOSS"
    reason_en = {
        ExitReason.SL_HIT: "Stop loss hit",
        ExitReason.TP1_HIT: "TP1 hit",
        ExitReason.TP2_HIT: "TP2 hit",
        ExitReason.TP3_HIT: "TP3 — full target",
        ExitReason.EXPLOSION: "Explosion mode exit",
        ExitReason.TACTICAL: "Tactical exit",
        ExitReason.FORCE_CLOSE: "Force close",
        ExitReason.KILL_SWITCH: "Kill switch",
    }.get(reason, reason.value.replace('_', ' '))

    msg = (
        f"{head_emoji} <b>{head_word}</b> · {side_word}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"<code>{pos.symbol}</code> · {pos.direction}\n\n"
        f"Entry   <code>{pos.entry:.6g}</code>\n"
        f"Exit    <code>{price:.6g}</code>\n"
        f"<b>PnL     {pnl_pct:+.2f}%</b>\n\n"
        f"Reason  {reason_en}\n"
        f"Lev {pos.leverage:.0f}x · Level {pos.pyramid_level}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{'🎊 Successful trade' if is_profit else '📊 Logged for model training'}"
    )

    await notify(pos.user_id, msg)

    # حفظ في DB
    try:
        from db.database import get_session, Signal as DBSignal
        db = get_session()
        # تحديث end_time و highest_hit
        sig = db.query(DBSignal).filter(
            DBSignal.symbol == pos.symbol,
            DBSignal.direction == pos.direction,
        ).order_by(DBSignal.id.desc()).first()

        if sig:
            sig.end_time = int(time.time())
            sig.highest_hit = pos.peak_price
            db.commit()
    except Exception as e:
        log.debug("close DB update: %s", e)

    log.info("Position closed: %s %s | %s | pnl=%.2f%%",
             pos.symbol, pos.direction, reason.value, pnl_pct)


# ═══════════════════════════════════════════════════════════════
# ─── MANUAL OVERRIDES ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def force_close(pos_id: str, user_id: str) -> dict:
    """
    Force Close — المستخدم يكسر حلقة AI ويغلق بسعر السوق
    هذا القرار نهائي — لا AI بعده
    """
    pos = ACTIVE.get(pos_id)
    if not pos:
        return {"error": "Position not found"}
    if pos.user_id != user_id:
        return {"error": "Unauthorized"}

    pos.force_close_lock = True  # ← يمنع AI من التدخل

    price = await get_price(pos.symbol)
    if not price:
        return {"error": "Could not fetch price"}

    pnl_pct = calc_pnl(pos, price)

    await notify(pos.user_id,
        f"🛑 <b>Force Close تم بنجاح</b>\n"
        f"{pos.symbol} {pos.direction}\n"
        f"سعر الخروج: {price:.4f}\n"
        f"PnL: <b>{pnl_pct:+.2f}%</b>\n"
        f"تم إغلاق الصفقة بسعر السوق فوراً ✅")

    await _close_position(pos, price, ExitReason.FORCE_CLOSE, pnl_pct)

    return {
        "status": "force_closed",
        "symbol": pos.symbol,
        "exit_price": price,
        "pnl_pct": round(pnl_pct, 2),
    }


# ═══════════════════════════════════════════════════════════════
# ─── AUTO POSITION OPENER ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def open_from_signal(sig: Signal, user_id: str = "system", amount: float = 100.0):
    """
    يفتح صفقة من إشارة الرادار - فقط Grade A و S
    """
    # ═══ شرط 1: Grade A أو S فقط ═══
    if sig.grade not in ("A", "S"):
        log.debug("Position skip: %s grade=%s (only A/S open positions)", sig.symbol, sig.grade)
        return None
    
    # ═══ شرط 2: Kill Switch ═══
    from .service import is_kill_switch_active
    if is_kill_switch_active():
        log.warning("Kill Switch active — لا صفقات جديدة")
        return None

    # ═══ شرط 3: منع تكرار نفس العملة (يمنع الصفقات الشبحية) ═══
    for existing in ACTIVE.values():
        if existing.status == "open" and existing.symbol == sig.symbol:
            log.info("Position skip: %s مفتوحة بالفعل (%s) — لا تكرار",
                     sig.symbol, existing.direction)
            return None

    # ═══ شرط 4: حد أقصى للصفقات المتزامنة بنفس الاتجاه + نفس الرادار ═══
    #   يمنع رهاناً واحداً مكرّراً (مثل 6 شورت متزامنة على عملات مرتبطة بـ BTC)
    MAX_CONCURRENT = 5  # خُفِض من 50: سقف المخاطرة — يمنع تكدّس الصفقات (كارثة الـ14)
    sig_is_ph = (sig.radar_type == "futures" and getattr(sig, "tier", "") == "PH")
    same = 0
    for _ex in ACTIVE.values():
        if _ex.status != "open" or _ex.direction != sig.direction:
            continue
        ex_is_ph = (_ex.radar_type == "futures" and getattr(_ex, "tier", "") == "PH")
        if ex_is_ph == sig_is_ph:
            same += 1
    if same >= MAX_CONCURRENT:
        log.info("Position skip: %s %s — بلغ الحد %d/%d لنفس الاتجاه/الرادار",
                 sig.symbol, sig.direction, same, MAX_CONCURRENT)
        return None

    pos_id = f"{sig.symbol}_{sig.direction}_{int(time.time())}"
    pos = Position(
        id=pos_id,
        user_id=user_id,
        symbol=sig.symbol,
        direction=sig.direction,
        entry=sig.entry,
        amount=amount,
        leverage=sig.leverage,
        sl=sig.sl,
        tp1=sig.tp1,
        tp2=sig.tp2,
        tp3=sig.tp3,
        tier=sig.tier,
        grade=sig.grade,
        original_leverage=sig.leverage,
        fvg_zone=sig.fvg_zone,
    )

    await add_position(pos)
    return pos


# ═══════════════════════════════════════════════════════════════
# ─── MAIN MONITOR LOOP ──────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def run_position_manager():
    """
    حلقة المراقبة الرئيسية:
    - كل 30 ثانية يفحص كل الصفقات المفتوحة
    - Semaphore يمنع التحميل الزائد
    - كل صفقة في coroutine مستقل
    """
    log.info("Position Manager started")
    # ═══ استعادة الصفقات من DB (تبقى عبر restart) ═══
    try:
        restored = _pos_load_all()
        for _p in restored:
            ACTIVE[_p.id] = _p
        if restored:
            log.info("🔄 Restored %d open position(s) from DB", len(restored))
    except Exception as _e:
        log.error("restore positions error: %s", _e)
    sem = asyncio.Semaphore(10)

    async def monitor_one(pos: Position):
        async with sem:
            try:
                await monitor_position(pos)
            except Exception as e:
                log.error("monitor_position %s: %s", pos.symbol, e)

    while True:
        try:
            positions = [p for p in ACTIVE.values() if p.status == "open"]

            if positions:
                await asyncio.gather(*[monitor_one(p) for p in positions], return_exceptions=True)
            else:
                await asyncio.sleep(10)

        except Exception as e:
            log.error("PM loop error: %s", e)

        await asyncio.sleep(10)  # مراقبة كل 10s (كان 30 — أسرع للصفقات السريعة، SL يُقطع مبكراً)
