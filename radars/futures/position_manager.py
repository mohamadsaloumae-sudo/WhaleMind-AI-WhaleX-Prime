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
    # ─ صفقة حقيقية على Binance (المدير ينفّذ قراراته فعلياً) ─
    is_real: bool = False
    binance_user_id: str = ""
    binance_sl_order_id: str = ""
    source_radar: str = ""           # رادار المصدر — المدير يدير كل صفقة بسياسة رادارها
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
            STATS["losses"] += 1
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


# ═══ سياسات الرادارات — المدير يفهم مصدر كل صفقة ويديرها بمنطق رادارها ═══
BTC_GUARD_L1 = 1.2   # % حركة BTC خلال 5 دقائق ضد الاتجاه → وقف للتعادل (إن رابحة)
BTC_GUARD_L2 = 2.2   # % حركة عنيفة → إغلاق تكتيكي فوري

RADAR_POLICY = {
    "PREDATOR": {"btc_guard": True},   # عملات تتبع BTC → الحارس فعّال
    "OB_REV":   {"btc_guard": True},
    "PH_SHORT": {"btc_guard": False},  # المنفجرات خارج جاذبية BTC لحظتها
    "PH_LONG":  {"btc_guard": False},
}

_BTC_PULSE = {"ts": 0.0, "chg": 0.0}
_SL_TOUCH: dict = {}   # pos.id -> وقت أول لمسة للوقف (مضاد الانخداع بالوميض)

async def _btc_pulse() -> float:
    """تغيّر BTC ٪ آخر 5 دقائق — cache مشترك 30ث (استدعاء واحد لكل الصفقات معاً)."""
    now = time.time()
    if now - _BTC_PULSE["ts"] < 30:
        return _BTC_PULSE["chg"]
    try:
        from radars.futures.engine import fapi_get
        k = await fapi_get("https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1m&limit=6", 10)
        if isinstance(k, list) and k:
            a, b = float(k[0][4]), float(k[-1][4])
            _BTC_PULSE["chg"] = (b - a) / a * 100 if a else 0.0
        else:
            _BTC_PULSE["chg"] = 0.0
    except Exception:
        _BTC_PULSE["chg"] = 0.0
    _BTC_PULSE["ts"] = now
    return _BTC_PULSE["chg"]


LIVE_POS: dict = {}   # id -> Position (مراجع الصفقات الحيّة)

def mark_position_real(symbol: str, direction: str, user_id: str,
                       qty: float = 0, lev: float = 0) -> bool:
    """يربط أحدث صفقة ورقية مفتوحة مطابقة بالتنفيذ الحقيقي (سجل واحد).
    qty/lev: الكمية والرافعة الفعليتان من أمر Binance — حتى يُغلق المدير الكمية الصحيحة."""
    try:
        _c = [p for p in LIVE_POS.values() if p.symbol==symbol
              and p.direction==direction and p.status=="open" and not p.is_real]
        if not _c: return False
        p = max(_c, key=lambda x: x.opened_at)
        p.is_real = True; p.binance_user_id = user_id
        if qty and float(qty) > 0: p.amount = float(qty)
        if lev and float(lev) > 0: p.leverage = float(lev)
        _pos_save(p)
        log.info("🔗 ربط حقيقي: %s %s ← id=%s", symbol, direction, p.id)
        return True
    except Exception as e:
        log.error("mark_position_real: %s", e); return False


def _pos_save(pos):
    LIVE_POS[pos.id] = pos
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
        LIVE_POS.pop(pos_id, None)
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
            _rp = Position(**d)
            LIVE_POS[_rp.id] = _rp
            out.append(_rp)
        return out
    except Exception as e:
        log.error("pos_load_all error: %s", e)
        return []


async def add_position(pos: Position):
    pos.peak_price = pos.entry
    ACTIVE[pos.id] = pos
    _pos_save(pos)
    log.info("Position opened: %s %s @%.6f lev=%.0fx", pos.symbol, pos.direction, pos.entry, pos.leverage)
    try:
        asyncio.create_task(monitor_position(pos))  # ⚡ قراءة أولى فورية — تغلق فجوة الثواني الأولى
    except Exception:
        pass
    src = "Peak Hunter" if pos.radar_type == "futures" and getattr(pos, "tier", "") == "PH" else "Radar"
    msg = (
        f"🟢 <b>فتح صفقة</b> · {pos.direction} · {pos.leverage:.0f}x\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"<code>{pos.symbol}</code>\n\n"
        f"الدخول   <code>{pos.entry:.6g}</code>\n"
        f"الوقف    <code>{pos.sl:.6g}</code>\n"
        f"الهدف 1  <code>{pos.tp1:.6g}</code>\n"
        f"الهدف 2  <code>{pos.tp2:.6g}</code>\n"
        f"الهدف 3  <code>{pos.tp3:.6g}</code>\n\n"
        f"الدرجة <b>{pos.grade}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📡 المراقبة جارية · إدارة تلقائية"
    )
    msg_en = (
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
            await notify(pos.user_id, msg, msg_en=msg_en)
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
    # 🌊 أولاً من WebSocket اللحظي (بلا REST، فوري) — fallback لـREST عند غياب البثّ
    try:
        from quant_engine.ob_stream import get_price as _ws_price
        _wp = _ws_price(symbol)
        if _wp and _wp > 0:
            return _wp
    except Exception:
        pass
    try:
        import httpx
        sym = symbol.replace("/", "").replace("-", "")
        if not sym.endswith("USDT"):
            sym += "USDT"
        from radars.futures.price_stream import get_price as _ws_price
        _wp = _ws_price(sym)
        if _wp:
            return float(_wp)
        from radars.futures.engine import fapi_get
        _pj = await fapi_get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={sym}", 2, max_stale=20)
        if isinstance(_pj, dict) and "price" in _pj:
            return float(_pj["price"])
        # بديل حيّ أثناء حظر fapi: تغذية WebSocket للسبوت (صفر REST، لا يتأثر بالحظر)
        try:
            from radars.spot.scout_spot import _prices as _ws_prices
            _v = _ws_prices.get(sym)
            if _v and float(_v) > 0:
                return float(_v)
        except Exception:
            pass
        return None
    except:
        return None

_OB_CACHE: dict = {}
async def get_order_book(symbol: str) -> dict:
    try:
        import httpx, time as _t
        sym = symbol.replace("/", "").replace("-", "")
        if not sym.endswith("USDT"):
            sym += "USDT"
        # 🌊 الستريم أولاً: صفر REST للعملات المبثوثة (كل الصفقات المفتوحة مبثوثة)
        try:
            from quant_engine.ob_stream import _books
            bk = _books.get(sym.lower())
            if bk:
                s = bk[-1]
                bids = sum(q for _, q in s.bids[:10]); asks = sum(q for _, q in s.asks[:10])
                if bids + asks > 0:
                    return {"bids": bids, "asks": asks,
                            "imbalance": (bids - asks) / (bids + asks),
                            "spread": s.asks[0][0] - s.bids[0][0]}
        except Exception:
            pass
        _cc = _OB_CACHE.get(sym)
        if _cc and _t.time() - _cc[0] < 3.0:
            return _cc[1]
        from radars.futures.engine import fapi_get
        d = await fapi_get(f"https://fapi.binance.com/fapi/v1/depth?symbol={sym}&limit=20", 5)
        if isinstance(d, dict) and d.get("bids"):
            bids = sum(float(b[1]) for b in d.get("bids", [])[:10])
            asks = sum(float(a[1]) for a in d.get("asks", [])[:10])
            _res = {
                "bids": bids,
                "asks": asks,
                "imbalance": (bids - asks) / (bids + asks) if (bids + asks) > 0 else 0,
                "spread": float(d["asks"][0][0]) - float(d["bids"][0][0]) if d.get("asks") and d.get("bids") else 0,
            }
            _OB_CACHE[sym] = (_t.time(), _res)
            return _res
        return {}
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

    ⚠️ مُعطّل للشفافية: رفع الرافعة الورقي لا يمكن تطبيقه في Binance
    (تغيير رافعة صفقة مفتوحة = تلاعب). الرافعة تبقى ثابتة من الفتح للإغلاق.
    """
    return False  # ← إيقاف رفع الرافعة (شفافية)

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
                f"📈 <b>تعزيز هرمي · المستوى 2</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"<code>{pos.symbol}</code> · {pos.direction}\n\n"
                f"الهدف 1 محقّق ✅\n"
                f"الرافعة رُفعت → <b>{pos.leverage:.0f}x</b>\n"
                f"اختلال الدفتر {imbalance:+.2f} · زخم إيجابي",
                msg_en=(
                    f"📈 <b>PYRAMIDING · Level 2</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"<code>{pos.symbol}</code> · {pos.direction}\n\n"
                    f"TP1 secured ✅\n"
                    f"Leverage raised → <b>{pos.leverage:.0f}x</b>\n"
                    f"OBI {imbalance:+.2f} · momentum positive"
                ))
            log.info("Pyramid L2: %s lev=%.0fx", pos.symbol, pos.leverage)
            _pos_save(pos)
            return True

    # شرط الانتقال للمستوى 3 (5x → 10x)
    if pos.pyramid_level == 2 and pos.tp2_hit and pos.explosion_mode:
        new_lev = pos.original_leverage * 5.0
        pos.leverage = min(new_lev, 50.0)
        pos.pyramid_level = 3
        await notify(pos.user_id,
            f"💥 <b>تعزيز هرمي · المستوى 3 — وضع الانفجار</b>\n"
            f"{pos.symbol} | الرافعة → <b>{pos.leverage:.0f}x</b>\n"
            f"⚡ الانفجار مؤكد — الكل مع الحوت!",
            msg_en=(
                f"💥 <b>Pyramiding · Level 3 — EXPLOSION MODE</b>\n"
                f"{pos.symbol} | Leverage → <b>{pos.leverage:.0f}x</b>\n"
                f"⚡ Explosion confirmed — all in with the whale!"
            ))
        log.info("Pyramid L3: %s lev=%.0fx", pos.symbol, pos.leverage)
        _pos_save(pos)
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

_IRR_CACHE: dict = {}   # (symbol,is_long) -> (ts, verdict, reason) — يمنع إغراق REST مع دورة 3s
async def is_real_reversal(symbol: str, is_long: bool, opened_at: float = 0) -> tuple[bool, str]:
    _k = (symbol, is_long)
    _cc = _IRR_CACHE.get(_k)
    if _cc and time.time() - _cc[0] < 12:
        return _cc[1], _cc[2]
    _v, _r = await _is_real_reversal_raw(symbol, is_long, opened_at)
    _IRR_CACHE[_k] = (time.time(), _v, _r)
    return _v, _r

async def _is_real_reversal_raw(symbol: str, is_long: bool, opened_at: float = 0) -> tuple[bool, str]:
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
            _pdir = getattr(_a, "pressure_direction", "NEUTRAL")
            _spf = getattr(_a, "spoofing_side", "")
            # ─ تلاعب معاكس للصفقة (بالاتجاه الصحيح) → انقلاب فوري ─
            #   SHORT: جدار شراء وهمي (spoof=bid) = تلاعب لرفعنا → اخرج
            #   جدار وهمي (spoof) = خداع حوت لإخراجنا — لا نخرج على الوهمي، بل ننتظر
            #   تأكيد القراءتين + حركة السعر الحقيقية أدناه (السعر لا يكذب، الأوردر بوك يُزيَّف).
            #   [أُزيلت 4 بوابات خروج فوري كانت تخرج على لقطة واحدة — درس IOTA]

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
                    _thr = 0.28
                elif _range_pos > 0.30:
                    _thr = 0.22
                else:
                    _thr = 0.15

            # تأكيد الاستمرارية: لا نغلق على لقطة واحدة (تذبذب/امتصاص لحظي).
            #   الانقلاب يجب أن يصمد عبر قراءتين متتاليتين (~10s) ليُعتبر حقيقياً.
            _against = (is_long and _ps < -_thr) or ((not is_long) and _ps > _thr)
            _wkey = f"{symbol}_{'L' if is_long else 'S'}"
            if _against:
                if _reversal_warn.get(_wkey):
                    # ✅ صمد قراءتين — الآن التحقّق الأصدق: هل السعر تحرّك ضدنا فعلاً؟
                    #   (رؤية Mohamad: الحوت يزيّف الأوردر بوك، لا يزيّف السعر المتحقّق)
                    _price_confirms = True
                    try:
                        _kk = await _fk_eye(symbol, "1m", 4)
                        if _kk and len(_kk) >= 4:
                            _p_now, _p_ago = _kk[-1].close, _kk[-4].close
                            _moved = (_p_now - _p_ago) / _p_ago * 100 if _p_ago else 0
                            # LONG يخرج فقط إن هبط السعر فعلاً؛ SHORT إن صعد فعلاً (≥0.15%)
                            _price_confirms = (_moved <= -0.15) if is_long else (_moved >= 0.15)
                            if not _price_confirms:
                                log.info("🐋 %s: أوردر بوك ينقلب لكن السعر لم يتحرك ضدنا (%+.2f%%/3د) — تلاعب حوت، نبقى",
                                         symbol, _moved)
                    except Exception:
                        pass
                    if _price_confirms:
                        _reversal_warn.pop(_wkey, None)
                        _side_txt = "بائعون مسيطرون" if is_long else "مشترون مسيطرون"
                        return True, f"انقلاب مؤكّد ({_side_txt} {_ps:+.2f} @ موقع {_range_pos:.0%}, صمد قراءتين + السعر)"
                else:
                    _reversal_warn[_wkey] = True
                    log.debug("إنذار انقلاب %s: ضغط %+.2f @ موقع %.0f%% — بانتظار القراءة التالية",
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
        from radars.futures.engine import fapi_get
        d = await fapi_get(f"https://fapi.binance.com/fapi/v1/depth?symbol={sym}&limit=100", 8)
        if not isinstance(d, dict):
            return False, ""
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

async def notify(user_id: str, msg: str, event_type: str = "alert", data: dict = None, to_channel: bool = True, msg_en: str = None):
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
        import sqlite3, time as _t
        _classified = event_type
        if event_type == "alert":
            if "🎯" in msg:
                _classified = "tp1_hit"
            elif "🚀" in msg:
                _classified = "tp2_hit"
            elif "🏆" in msg or "🔴" in msg:
                _classified = "position_closed"
            elif "📈" in msg or "💥" in msg:
                _classified = "pyramiding"
            elif "⚠️" in msg:
                _classified = "sl_warning"
            elif "🔒" in msg:
                _classified = "trailing_active"
            elif "🤖" in msg:
                _classified = "ai_alert"
        import re as _re
        _clean_msg = _re.sub(r"<[^>]+>", "", msg).strip()
        _clean_msg_en = _re.sub(r"<[^>]+>", "", msg_en).strip() if msg_en else None
        _c = sqlite3.connect("/opt/whalex/db/whalex.db")
        _c.execute(
            "INSERT INTO notifications (event, message, message_en, created_at) VALUES (?,?,?,?)",
            (_classified, _clean_msg, _clean_msg_en, int(_t.time()))
        )
        _c.commit()
        _c.close()
    except Exception as _e:
        log.debug("notify db save error: %s", _e)
    try:
        from routers.ws import registry
        await registry.broadcast({"event": event_type, "user_id": user_id, "message": msg, "message_en": msg_en, "data": data or {}})
    except Exception as e:
        log.debug("notify ws error: %s", e)
    try:
        from routers.push import send_push_to_all
        await send_push_to_all("WhaleX Prime", msg)
    except Exception as _pe:
        log.debug("push notify error: %s", _pe)

# ═══════════════════════════════════════════════════════════
#  العيون عند الإغلاق: نغلق أم نتنفّس؟ (يخدم بوّابتَي SL و HARD_STOP)
#  أرضية pnl صلبة لا تُخترق. فوقها نستشير is_real_reversal:
#    انقلاب مؤكد→نغلق | فخ مكشوف→نتنفّس | صمت→نغلق (احترام الوقف).
#  القرار يُخزَّن 60 ثانية لكل صفقة (يمنع إغراق Binance وتضارب البوّابتين).
# ═══════════════════════════════════════════════════════════
PNL_HARD_FLOOR = -8.0   # أرضية الخسارة المطلقة (pnl مُرفّع) — كانت -15: انقلاب مؤكّد يُغلق مبكراً، والفجوات العنيفة تُقطع هنا
_REV_CACHE: dict = {}    # pos.id -> (ts, breathe, reason)
_LADDER_TS: dict = {}    # pos.id -> آخر فحص سلّم دوري
_LOSS_CD: dict = {}      # symbol -> وقت آخر إغلاق خاسر (تهدئة 30 دقيقة)
TUNE = {"strict": 1.0, "harvest": 1.0}   # 🧭 strict=عمق الدفاع · harvest=سرعة قفل الأرباح (أقل = أبكر)

async def _ladder_verdict(pos: "Position", pnl_pct: float):
    """⚖️ سلّم عبء الإثبات — يعيد سبب الإغلاق (str) أو None للبقاء.
    -4..-8%: شاهدان (عمق+تدفق ضدنا) = إغلاق. أعمق من -8%: البقاء يحتاج دليلاً إيجابياً.
    العتبات تُضرب بعامل الصرامة الذاتي TUNE["strict"]."""
    _t4 = -4.0; _t8 = -6.0 * TUNE["strict"]   # العمق يبدأ -6: الخسارة النموذجية أصغر من الربح المقفول
    if pnl_pct > _t4:
        if getattr(pos, "_deep_grace_ts", 0.0):
            pos._deep_grace_ts = 0.0  # تعافى — تُمنح مهلة جديدة مستقبلاً فقط بعد تعافٍ حقيقي
        return None
    try:
        from quant_engine.order_book_analyzer import analyze_order_book as _aob
        from quant_engine.delta_engine import calculate_cvd as _cvd_l
        from radars.futures.engine import fetch_klines_async as _fk_l
        _lng = pos.direction == "LONG"
        _a = await _aob(pos.symbol, check_spoofing=True)
        _ps = getattr(_a, "pressure_score", 0.0) if _a else 0.0
        _spf = getattr(_a, "spoofing_side", "") if _a else ""
        _depth_against = (_ps <= -0.15) if _lng else (_ps >= 0.15)
        _kl5 = await _fk_l(pos.symbol, "5m", 30)
        _flow_against = False; _flow_for = False
        if _kl5 and len(_kl5) >= 20:
            _raw5 = [[int(k.time)*1000, k.open, k.high, k.low, k.close,
                      k.volume, 0, k.volume, 0, k.buy_volume, k.buy_volume] for k in _kl5]
            _, _cum5 = _cvd_l(_raw5)
            if len(_cum5) >= 6:
                _dslope = _cum5[-1] - _cum5[-6]
                _flow_against = (_dslope < 0) if _lng else (_dslope > 0)
                _flow_for = (_dslope > 0) if _lng else (_dslope < 0)
        if pnl_pct <= -10.0:
            return f"⚖️ حد صلب {pnl_pct:.1f}% ≤ -10%: إغلاق غير مشروط — لا دليل يعلو عليه"
        if pnl_pct <= _t8:
            _spoof_trap = (_spf == "ask") if _lng else (_spf == "bid")
            if _spoof_trap:
                return None  # خداع صريح لإخراجنا — البقاء مبرَّر
            if _flow_for:
                # ⏳ مهلة تعافٍ واحدة فقط (60s) — لا تتجدد مع كل تصحيح صغير
                _g = getattr(pos, "_deep_grace_ts", 0.0)
                if not _g:
                    pos._deep_grace_ts = time.time()
                    return None
                if time.time() - _g < 60:
                    return None
                return f"⚖️ سلّم عميق {pnl_pct:.1f}%: انتهت مهلة التعافي (60s) والتدفق لم ينقذ — إغلاق"
            return f"⚖️ سلّم عميق {pnl_pct:.1f}%: لا دليل بقاء (ضغط {_ps:+.2f}, تدفق ضدنا) — إغلاق"
        else:
            if _depth_against and _flow_against:
                return f"⚖️ سلّم {pnl_pct:.1f}%: عمق OB ضدنا ({_ps:+.2f}) + CVD ضدنا — شاهدان → إغلاق"
    except Exception as _lad_e:
        log.warning("⚖️ سلّم %s: تعذّر جمع الأدلة (%s) عند pnl=%.1f%%", pos.symbol, _lad_e, pnl_pct)
        if pnl_pct <= _t8:
            return f"⚖️ سلّم عميق {pnl_pct:.1f}%: تعذّر التحقق من دليل بقاء — إغلاق احترازي"
    return None

async def _should_breathe(pos: "Position", price: float, pnl_pct: float) -> tuple:
    """True = تنفّس (لا تغلق هذه الدورة). False = أغلق. السبب للّوج."""
    if pnl_pct <= PNL_HARD_FLOOR:
        return False, f"أرضية صلبة {pnl_pct:.1f}% <= {PNL_HARD_FLOOR:.0f}%"
    # ⚖️ سلّم عبء الإثبات: كلما تعمّقت الخسارة قلّ احتمال الخداع → تقلّ الأدلة المطلوبة للإغلاق.
    #   0→-4%: تنفس كامل (المنطق أدناه كما هو). -4→-8%: يكفي شاهدان (عمق OB ضدنا + CVD ضدنا).
    #   أعمق من -8%: ينقلب العبء — نغلق ما لم يوجد دليل إيجابي للبقاء (spoofing ضدنا أو CVD معنا).
    _lv = await _ladder_verdict(pos, pnl_pct)
    if _lv:
        return False, _lv
    # 📉 رقيب الاتجاه: هبوط تدريجي حقيقي ضدنا عبر 10 شموع (5m) = اتجاه صامت → أغلق
    #   (يكمّل الخروج التكتيكي: ذاك للانقلاب الحاد، هذا للتآكل البطيء الذي لا يصرخ)
    try:
        from radars.futures.engine import fetch_klines_async as _fkt
        _is_long = pos.direction == "LONG"
        _kl = await _fkt(pos.symbol, "5m", 10)
        if _kl and len(_kl) >= 10:
            _closes = [k.close for k in _kl]
            _drift = (_closes[-1] - _closes[0]) / _closes[0] * 100 if _closes[0] else 0
            _against = (_drift <= -1.5) if _is_long else (_drift >= 1.5)
            # اتّساق: أغلب الشموع في اتجاه الضرر (ميل حقيقي لا شمعة واحدة)
            _steps = sum(1 for i in range(1, len(_closes))
                         if (_closes[i] < _closes[i-1]) == _is_long)
            if _against and _steps >= 6:
                return False, f"📉 رقيب الاتجاه: تآكل تدريجي {_drift:+.1f}%/50د ({_steps}/9 ضدنا)"
    except Exception:
        pass
    # 🎯 مخرج تنبّؤي: إن رابحة والزخم يُستنزف (exhaustion) → جنِ الربح قبل الانقلاب لا بعده
    if pnl_pct > 0.6:
        try:
            from radars.futures.engine import fetch_klines_async as _fkp
            from quant_engine.delta_engine import calculate_cvd as _cvd, detect_exhaustion as _exh
            _kl = await _fkp(pos.symbol, "5m", 30)
            if _kl and len(_kl) >= 20:
                _raw = [[int(k.time)*1000, k.open, k.high, k.low, k.close,
                         k.volume, 0, k.volume, 0, k.buy_volume, k.buy_volume] for k in _kl]
                _, _cum = _cvd(_raw)
                _ex, _kind = _exh(_raw, _cum)
                _lng = pos.direction == "LONG"
                # LONG+bullish (شراء يضعف بالقمة) أو SHORT+bearish (بيع يضعف بالقاع) = انقلاب وشيك
                if _ex and ((_lng and _kind == "bullish") or (not _lng and _kind == "bearish")):
                    return False, f"🎯 مخرج تنبّؤي: استنزاف الزخم ({_kind}) والصفقة رابحة {pnl_pct:+.1f}% — جني قبل الانقلاب"
        except Exception:
            pass
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
    if getattr(pos, "status", "") != "open":
        return
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
                f"<i>نُغلق فوراً عند تأكّد انقلاب حقيقيّ.</i>",
                msg_en=(
                    f"⚠️ <b>{pos.symbol} {pos.direction} — Price approaching stop</b>\n"
                    f"The bot is watching live. If it detects a temporary wobble (not a reversal), it stays in the trade.\n"
                    f"📌 <b>Get ready: raise your stop-loss or cancel it if you want to follow the bot.</b>\n"
                    f"<i>We close immediately once a real reversal is confirmed.</i>"
                ))

    # ─ ₿🛡️ حارس BTC — لصفقات الرادارات التابعة لBTC فقط (سياسة المصدر) ─
    if RADAR_POLICY.get(pos.source_radar or "PREDATOR", {}).get("btc_guard"):
        try:
            _m = await _btc_pulse()
            _against = (_m <= -BTC_GUARD_L1) if is_long else (_m >= BTC_GUARD_L1)
            if _against:
                if abs(_m) >= BTC_GUARD_L2:
                    log.warning("₿🛡️ %s: BTC انقلب بعنف (%+.2f%%/5د) ضد %s — إغلاق فوري",
                                pos.symbol, _m, pos.direction)
                    await _close_position(pos, price, ExitReason.TACTICAL, pnl_pct)
                    return
                _be = pos.entry * (1.001 if is_long else 0.999)
                if pnl_pct > 0 and ((is_long and pos.sl < _be) or (not is_long and pos.sl > _be)):
                    pos.sl = _be; pos.trailing_sl = _be
                    await _binance_update_sl(pos, pos.sl)
                    log.info("₿🛡️ %s: BTC ضدنا (%+.2f%%/5د) — الوقف للتعادل حمايةً",
                             pos.symbol, _m)
        except Exception as _bg:
            log.debug("btc_guard: %s", _bg)

    # ─ شبكة أمان مطلقة: أرضية pnl صلبة (كل دورة، قبل أي منطق وقف) ─
    if pnl_pct <= PNL_HARD_FLOOR:
        log.warning("PNL FLOOR %s %s pnl=%.1f%% — إغلاق فوري",
                    pos.symbol, pos.direction, pnl_pct)
        await _close_position(pos, price, ExitReason.SL_HIT, pnl_pct)
        return

    # ⚖️ بوابة السلّم الدورية — تعمل في نطاقها كل دورة (كانت ميتة خلف بوابتي SL/HARD_STOP)
    # 🧱 الحد الصلب المطلق -10% — لا يحجبه عمر ولا كاش ولا دليل (سُدّ ثقب مهلة الولادة)
    if pnl_pct <= -10.0:
        log.warning("🧱 حد صلب %s %s pnl=%.1f%% — إغلاق غير مشروط", pos.symbol, pos.direction, pnl_pct)
        await _close_position(pos, price, ExitReason.SL_HIT, pnl_pct)
        return

    if pnl_pct <= -4.0 and (time.time() - getattr(pos, "opened_at", 0)) >= 180:
        _lts = _LADDER_TS.get(pos.id, 0.0)
        if time.time() - _lts >= 15:
            _LADDER_TS[pos.id] = time.time()
            _lv = await _ladder_verdict(pos, pnl_pct)
            if _lv:
                log.warning("%s | %s %s", _lv, pos.symbol, pos.direction)
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

    # ─ الوقف المتحرك اللاحق: يلاحق السعر مع الربح (يُرفع تلقائياً) ─
    #   بعد TP1، الوقف يتبع أفضل سعر بمسافة TRAIL_GAP، فيحمي الربح المتراكم.
    #   SHORT: يتبع القاع لأسفل. LONG: يتبع القمة لأعلى. لا ينزل/يصعد عكسياً أبداً.
    if pos.tp1_hit:
        TRAIL_GAP = 0.03  # 3% مسافة الملاحقة من أفضل سعر
        if is_long:
            _new_trail = pos.peak_price * (1 - TRAIL_GAP)
            if _new_trail > pos.sl:
                pos.sl = _new_trail
                pos.trailing_sl = _new_trail
                await _binance_update_sl(pos, pos.sl)
        else:
            _new_trail = pos.peak_price * (1 + TRAIL_GAP)
            if _new_trail < pos.sl or pos.sl == 0:
                pos.sl = _new_trail
                pos.trailing_sl = _new_trail
                await _binance_update_sl(pos, pos.sl)

    # ─ SL / Trailing Stop ─
    sl_hit = (is_long and price <= pos.sl) or (not is_long and price >= pos.sl)
    # 🛡️ مضاد السبايك: وميض لحظي واحد لا يُغلق — يلزم بقاء السعر خلف الوقف
    #   لقراءتين متتاليتين (≥8 ثوانٍ). درس EVAA: wick لمس الوقف ثوانيَ فأغلق صفقة رابحة.
    if sl_hit:
        _t0 = _SL_TOUCH.get(pos.id, 0.0)
        _nowt = time.time()
        if _t0 == 0.0:
            _SL_TOUCH[pos.id] = _nowt
            log.info("⚡ %s لمس الوقف (%.6g) — انتظار تأكيد، لا انخداع بالوميض",
                     pos.symbol, price)
            sl_hit = False
        elif _nowt - _t0 < 8:
            sl_hit = False
    else:
        _SL_TOUCH.pop(pos.id, None)
    if sl_hit:
        # Trailing رابح (جني فوري) أم SL خسارة (استشر العيون)؟
        if pos.tp1_hit and pnl_pct > 0:
            # Trailing Stop بعد TP1 = إغلاق رابح، يُؤخذ فوراً بلا تنفّس
            await notify(pos.user_id,
                f"🔒 <b>الوقف المتحرك — ربح محمي</b>\n"
                f"{pos.symbol} {pos.direction}\n"
                f"💰 الربح المُحقق: <b>+{pnl_pct:.2f}%</b>\n"
                f"✅ تم تأمين الأرباح بعد الهدف 1\n"
                f"<i>الوقف المتحرك يحمي مكاسبك</i>",
                msg_en=(
                    f"🔒 <b>Trailing Stop — Profit Protected</b>\n"
                    f"{pos.symbol} {pos.direction}\n"
                    f"💰 Realized profit: <b>+{pnl_pct:.2f}%</b>\n"
                    f"✅ Profits secured after TP1\n"
                    f"<i>Trailing Stop protects your gains</i>"
                ))
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


    # تامين ربح Predator المبكر (قبل TP1)
    is_predator = (pos.radar_type == "futures" and getattr(pos, "tier", "") != "PH")
    # 🔒 قفل نصف الذروة: ربح لامس +8% لا يرتد خسارة — الوقف يتبع نصف القمة
    _pkp = pos.peak_price or pos.entry
    _pk_pnl = ((_pkp - pos.entry) / pos.entry if is_long else (pos.entry - _pkp) / pos.entry) * 100 * pos.leverage
    if _pk_pnl >= 8.0 * TUNE["harvest"]:
        _lock = _pk_pnl / 2.0
        _ls = pos.entry * (1 + _lock / (100 * pos.leverage)) if is_long else pos.entry * (1 - _lock / (100 * pos.leverage))
        _new = max(pos.sl, _ls) if is_long else min(pos.sl, _ls)
        if _new != pos.sl:
            pos.sl = _new
            await _binance_update_sl(pos, pos.sl)
    _be_th = (2.0 if is_predator else 5.0) * TUNE["harvest"]   # ⚖️ تأمين مبكر — يتبع حالة النظام
    if not pos.trailing_active and pnl_pct >= _be_th:
        pos.trailing_active = True
        pos.sl = pos.entry * (1.001 if is_long else 0.999)
        pos.trailing_sl = pos.sl
        await _binance_update_sl(pos, pos.sl)
        await notify(pos.user_id,
            f"🛡 <b>ربح مؤمن — Predator</b>\n"
            f"{pos.symbol} {pos.direction}\n"
            f"الربح الحالي: <b>+{pnl_pct:.2f}%</b>\n"
            f"الوقف على نقطة التعادل — لا خسارة بعد الان",
            msg_en=(
                f"🛡 <b>Profit Secured — Predator</b>\n"
                f"{pos.symbol} {pos.direction}\n"
                f"Current profit: <b>+{pnl_pct:.2f}%</b>\n"
                f"Stop at breakeven — no loss from here"
            ))
        log.info("Predator breakeven %s pnl=%.2f", pos.symbol, pnl_pct)
    # ─ TP1 ─
    tp1_hit = (is_long and price >= pos.tp1) or (not is_long and price <= pos.tp1)
    if tp1_hit and not pos.tp1_hit:
        pos.tp1_hit = True
        pos.trailing_active = True
        # قفل ربح +2% سعري (لا مجرد تعادل) — TP1 بلغ فالربح يُحفظ لا يُعاد
        pos.sl = max(pos.sl, pos.entry * 1.02) if is_long else min(pos.sl, pos.entry * 0.98)
        pos.trailing_sl = pos.sl
        await _binance_update_sl(pos, pos.sl)

        profit = abs((price - pos.tp1) / pos.entry * 100)
        await notify(pos.user_id,
            f"🎯 <b>الهدف 1 محقّق</b> · +{profit:.2f}%\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<code>{pos.symbol}</code> · {pos.direction}\n\n"
            f"ربح مؤمّن  <b>+{profit:.2f}%</b>\n"
            f"الوقف نُقل إلى  نقطة التعادل 🛡️\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"▶ نستمر نحو الهدف 2 · رأس المال محمي",
            msg_en=(
                f"🎯 <b>TARGET 1 HIT</b> · +{profit:.2f}%\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"<code>{pos.symbol}</code> · {pos.direction}\n\n"
                f"Profit secured  <b>+{profit:.2f}%</b>\n"
                f"Stop moved to   breakeven 🛡️\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"▶ Holding for TP2 · capital protected"
            ))

        # Pyramiding check
        await check_pyramiding(pos, price)
        _pos_save(pos)

    # ─ TP2 ─
    tp2_hit = (is_long and price >= pos.tp2) or (not is_long and price <= pos.tp2)
    if tp2_hit and not pos.tp2_hit and pos.tp1_hit:
        pos.tp2_hit = True
        pos.explosion_mode = True
        # رفع الوقف إلى الهدف 1 (حماية ربح الهدف 1)
        pos.sl = pos.tp1
        pos.trailing_sl = pos.tp1
        await _binance_update_sl(pos, pos.sl)

        await notify(pos.user_id,
            f"🚀 <b>الهدف 2 محقّق</b> · وضع الانفجار\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<code>{pos.symbol}</code> · {pos.direction}\n\n"
            f"💥 الاختراق مؤكّد\n"
            f"⬆️ الهدف التالي: الهدف 3",
            msg_en=(
                f"🚀 <b>TARGET 2 HIT</b> · Explosion Mode\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"<code>{pos.symbol}</code> · {pos.direction}\n\n"
                f"💥 Breakout confirmed\n"
                f"⬆️ Next target: TP3"
            ))

        await check_pyramiding(pos, price)
        _pos_save(pos)

    # ─ TP3 ─
    tp3_hit = (is_long and price >= pos.tp3) or (not is_long and price <= pos.tp3)
    if tp3_hit and pos.tp2_hit:
        profit = abs(pnl_pct)
        await notify(pos.user_id,
            f"🏆 <b>الهدف 3 محقّق</b> — {pos.symbol}\n"
            f"💰 الربح الكامل: <b>+{profit:.2f}%</b>\n"
            f"✅ تم إغلاق الصفقة بالكامل\n"
            f"🎊 <i>إشارة WhaleMind Prime ناجحة!</i>",
            msg_en=(
                f"🏆 <b>TP3 HIT</b> — {pos.symbol}\n"
                f"💰 Full profit: <b>+{profit:.2f}%</b>\n"
                f"✅ Position fully closed\n"
                f"🎊 <i>Successful WhaleMind Prime signal!</i>"
            ))
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
                await _binance_update_sl(pos, pos.sl)
        else:
            new_sl = price + (pos.entry - pos.tp1) * TRAIL_MULT
            if new_sl < pos.trailing_sl or pos.trailing_sl == 0:
                pos.trailing_sl = new_sl
                pos.sl = new_sl
                await _binance_update_sl(pos, pos.sl)
        _pos_save(pos)

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
                f"🤖 <b>تحليل طارئ من Claude AI</b> — {pos.symbol}\n"
                f"{'📈' if is_long else '📉'} {pos.direction} | الربح/الخسارة: {pnl_pct:+.2f}%\n"
                f"⚠️ {alert_reason}\n"
                f"{'─' * 20}\n"
                f"<i>{ai_reply}</i>",
                msg_en=(
                    f"🤖 <b>Claude AI Emergency Analysis</b> — {pos.symbol}\n"
                    f"{'📈' if is_long else '📉'} {pos.direction} | PnL: {pnl_pct:+.2f}%\n"
                    f"⚠️ {alert_reason}\n"
                    f"{'─' * 20}\n"
                    f"<i>{ai_reply}</i>"
                ))

            # إذا قرر Claude B (هروب) → تنفيذ تكتيكي
            if ai_reply.upper().startswith("B") and pnl_pct > -1.0:
                await _close_position(pos, price, ExitReason.TACTICAL, pnl_pct)
                return

    # ─ Tactical Exit Check ─
    # مراقبة ديناميكية: شديدة بعد TP1 (حماية الربح)، يقظة قبله (خروج وقائي).
    #   الحلقة الضائعة كانت 300ث (نوم 5 دقائق) — الانقلاب يضرب الستوب قبل الفحص.
    _tac_interval = 20 if pos.tp1_hit else 45
    if now - pos.last_warned > _tac_interval:
        pos.last_warned = now  # ⏱️ خنق حقيقي: يُحدَّث عند كل فحص لا عند النجاح فقط
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

async def _binance_update_sl(pos: "Position", new_sl: float):
    """يحدّث أمر SL الحقيقي على Binance (يلغي القديم، يضع الجديد)."""
    if not pos.is_real:
        return
    _last = getattr(pos, "_last_sl_sent", 0.0)
    if _last and abs(new_sl - _last) / _last * 100 < 0.15:
        return  # 🔇 تغيير أدق من 0.15% — لا نغرق Binance بأوامر إلغاء/إنشاء
    try:
        from services.binance_trader import get_client, _fmt_price
        client = get_client(pos.binance_user_id)
        if not client:
            log.warning("real SL: client None لـ %s", pos.symbol)
            return
        # إلغاء أوامر STOP القديمة للعملة
        try:
            for o in client.futures_get_open_orders(symbol=pos.symbol):
                if o.get("type") == "STOP_MARKET":
                    client.futures_cancel_order(symbol=pos.symbol, orderId=o["orderId"])
        except Exception as _ce:
            log.debug("cancel old SL %s: %s", pos.symbol, _ce)
        # وضع SL الجديد
        sl_side = "SELL" if pos.direction == "LONG" else "BUY"
        o = client.futures_create_order(
            symbol=pos.symbol, side=sl_side, type="STOP_MARKET",
            stopPrice=_fmt_price(client, pos.symbol, new_sl),
            closePosition=True,
        )
        pos.binance_sl_order_id = str(o.get("orderId", ""))
        pos._last_sl_sent = new_sl
        log.info("🔧 SL حقيقي حُدّث: %s → %.6g (order %s)", pos.symbol, new_sl, pos.binance_sl_order_id)
    except Exception as e:
        log.error("binance_update_sl %s: %s", pos.symbol, e)


async def _binance_close_position(pos: "Position") -> float:
    """يغلق المركز الحقيقي على Binance ويعيد سعر التنفيذ الفعلي (0 إن ورقي/فشل)."""
    if not pos.is_real:
        return 0.0
    try:
        from services.binance_trader import get_client, _fmt_qty
        client = get_client(pos.binance_user_id)
        if not client:
            log.warning("real close: client None لـ %s", pos.symbol)
            return 0.0
        close_side = "SELL" if pos.direction == "LONG" else "BUY"
        _o = client.futures_create_order(
            symbol=pos.symbol, side=close_side, type="MARKET",
            quantity=_fmt_qty(client, pos.symbol, pos.amount),
            reduceOnly=True,
        )
        try:
            client.futures_cancel_all_open_orders(symbol=pos.symbol)
        except Exception:
            pass
        _avg = 0.0
        try:
            _od = client.futures_get_order(symbol=pos.symbol, orderId=_o["orderId"])
            _avg = float(_od.get("avgPrice") or 0)
        except Exception:
            pass
        log.info("🔒 مركز حقيقي أُغلق على Binance: %s %s qty=%s @%.6g",
                 pos.symbol, pos.direction, pos.amount, _avg)
        return _avg
    except Exception as e:
        log.error("binance_close %s: %s", pos.symbol, e)
    return 0.0


async def _close_position(pos: Position, price: float, reason: ExitReason, pnl_pct: float):
    """إغلاق الصفقة وإرسال الإشعار"""
    if getattr(pos, "status", "") != "open":
        return  # 🔒 حارس ذري: مسار آخر أغلقها/يغلقها الآن — لا إغلاق مزدوج
    pos.status = "closing"
    if pnl_pct < 0:
        _LOSS_CD[pos.symbol] = time.time()   # 🧊 تهدئة إعادة الفتح بعد خسارة
    # ─ الصفقة الحقيقية: الإغلاق على Binance أولاً + اعتماد سعر التنفيذ الفعلي ─
    #   (درس EVAA: التقرير حُسب من سعر لحظي مخادع فأعلن -18% بينما Binance ربحت)
    _real_exit = await _binance_close_position(pos)
    if _real_exit and _real_exit > 0:
        _dirmul = 1 if pos.direction == "LONG" else -1
        pnl_pct = (_real_exit - pos.entry) / pos.entry * 100 * _dirmul * pos.leverage
        price = _real_exit
        log.info("💹 %s: سعر الخروج الحقيقي %.6g → pnl فعلي %+.2f%%",
                 pos.symbol, _real_exit, pnl_pct)
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
    head_word = "POSITION CLOSED"
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
    head_word_ar = "أُغلقت الصفقة"
    side_word_ar = "ربح" if is_profit else "خسارة"
    reason_ar = {
        ExitReason.SL_HIT: "ضرب وقف الخسارة",
        ExitReason.TP1_HIT: "تحقيق الهدف 1",
        ExitReason.TP2_HIT: "تحقيق الهدف 2",
        ExitReason.TP3_HIT: "الهدف 3 — الهدف الكامل",
        ExitReason.EXPLOSION: "خروج وضع الانفجار",
        ExitReason.TACTICAL: "خروج تكتيكي",
        ExitReason.FORCE_CLOSE: "إغلاق قسري",
        ExitReason.KILL_SWITCH: "مفتاح الإيقاف",
    }.get(reason, reason.value.replace('_', ' '))

    msg = (
        f"{head_emoji} <b>{head_word_ar}</b> · {side_word_ar}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"<code>{pos.symbol}</code> · {pos.direction}\n\n"
        f"الدخول   <code>{pos.entry:.6g}</code>\n"
        f"الخروج   <code>{price:.6g}</code>\n"
        f"<b>الربح/الخسارة  {pnl_pct:+.2f}%</b>\n\n"
        f"السبب  {reason_ar}\n"
        f"رافعة {pos.leverage:.0f}x · مستوى {pos.pyramid_level}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{'🎊 صفقة ناجحة' if is_profit else '📊 سُجّلت لتدريب النموذج'}"
    )
    msg_en = (
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

    await notify(pos.user_id, msg, msg_en=msg_en)

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
        f"🛑 <b>إغلاق قسري تم بنجاح</b>\n"
        f"{pos.symbol} {pos.direction}\n"
        f"سعر الخروج: {price:.4f}\n"
        f"الربح/الخسارة: <b>{pnl_pct:+.2f}%</b>\n"
        f"تم إغلاق الصفقة بسعر السوق فوراً ✅",
        msg_en=(
            f"🛑 <b>Force Close Successful</b>\n"
            f"{pos.symbol} {pos.direction}\n"
            f"Exit price: {price:.4f}\n"
            f"PnL: <b>{pnl_pct:+.2f}%</b>\n"
            f"Position closed at market immediately ✅"
        ))

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
    # منع الازدواج: صفقة واحدة لكل عملة (من أي رادار وأي اتجاه)
    _cd = _LOSS_CD.get(sig.symbol, 0.0)
    if _cd and time.time() - _cd < 1800:
        log.info("🧊 تهدئة %s: أُغلق خاسراً قبل %.0f دقيقة — لا إعادة فتح", sig.symbol, (time.time()-_cd)/60)
        return None
    _dup = [p for p in LIVE_POS.values() if p.symbol == sig.symbol and p.status == "open"]
    if _dup:
        log.info("🚫 %s %s — صفقة مفتوحة مسبقاً على العملة (id=%s) — لا ازدواج",
                 sig.symbol, sig.direction, _dup[0].id)
        return None
    # ═══ شرط 1: Grade A أو S فقط ═══
    if sig.grade not in ("A", "S"):
        log.debug("Position skip: %s grade=%s (only A/S open positions)", sig.symbol, sig.grade)
        return None
    
    # 🛡 صمام الانحراف: إشارة دخولها بعيد عن السعر الحي = بيانات فاسدة → رفض
    try:
        _live = await get_price(sig.symbol)
        if _live and _live > 0 and sig.entry > 0:
            _drift = abs(sig.entry - _live) / _live * 100
            if _drift > 2.0:
                log.warning("🛡 رفض %s %s: دخول %.6g ينحرف %.1f%% عن الحي %.6g — بيانات قديمة",
                            sig.symbol, sig.direction, sig.entry, _drift, _live)
                return None
    except Exception:
        pass
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
        source_radar=getattr(sig, "source_radar", "PREDATOR"),
        symbol=sig.symbol,
        direction=sig.direction,
        entry=sig.entry,
        amount=amount,
        leverage=float(max(1, round(float(sig.leverage or 3)))),
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
# ─── 🧭 DAILY SELF-REVIEW — يقيس نتائجه ويكيّف صرامته ─────────────
# ═══════════════════════════════════════════════════════════════
_REVIEW_F = "/opt/whalex/.pm_review"

async def _self_review_loop():
    """🧭 وعي ذاتي: كل ساعة يقرأ نافذة 24h ويضبط موازينه بفلسفة محمد —
    رابح = حذر يقفل مكاسبه أبكر · خاسر = انتقاء أصرم (فيتو أعلى) + حصاد أسرع + عمق أشد.
    لا رفع مخاطرة أبداً. تقرير يومي للخاص يفصّل كل اتجاه (يكشف الجانب النازف بالأرقام)."""
    while True:
        try:
            import sqlite3 as _sq
            _now = time.time()
            _tot = _win = 0; _net = 0.0; _dir = {"LONG": 0.0, "SHORT": 0.0}
            try:
                cx = _sq.connect("/opt/whalex/ml_training.db")
                _cols = {r[1] for r in cx.execute("PRAGMA table_info(training_signals)")}
                _pc = "pnl_pct" if "pnl_pct" in _cols else ("result_pnl" if "result_pnl" in _cols else None)
                if _pc:
                    for d, n, w, s in cx.execute(
                        f"SELECT direction, COUNT(*), SUM(CASE WHEN outcome=1 THEN 1 ELSE 0 END), COALESCE(SUM({_pc}),0) "
                        "FROM training_signals WHERE outcome IS NOT NULL AND timestamp >= ? GROUP BY direction",
                        (_now - 86400,)):
                        _tot += int(n or 0); _win += int(w or 0); _net += float(s or 0.0)
                        if d in _dir: _dir[d] = float(s or 0.0)
                cx.close()
            except Exception as _qe:
                log.debug("self_review query: %s", _qe)

            if _tot >= 3:
                try:
                    from quant_engine import ml_brain as _mlb
                    if _net < 0:
                        TUNE["strict"] = 0.8; TUNE["harvest"] = 0.8; _mlb.ML_VETO_THRESHOLD = 0.46
                        _mode = "🛡️ خاسر → تكثيف: انتقاء أصرم (فيتو 44%) + حصاد أبكر + عمق أشد"
                    else:
                        TUNE["strict"] = 1.0; TUNE["harvest"] = 0.9; _mlb.ML_VETO_THRESHOLD = 0.42
                        _mode = "✅ رابح → حذر: قفل مبكر للمكاسب، عتبات قياسية"
                except Exception as _te:
                    log.debug("tune set: %s", _te)

            # تقرير يومي (ختم ملف) — يفصّل الاتجاهين
            _last = 0.0
            try:
                _last = float(open(_REVIEW_F).read().strip() or 0)
            except Exception:
                pass
            if _now - _last >= 86400 and _tot >= 3:
                try:
                    from services.telegram import send_message
                    from core.config import get_settings
                    _adm = get_settings().telegram_admin_chat_id
                    if _adm:
                        await send_message(_adm,
                            f"🧭 <b>مراجعة المدير الذاتية · 24 ساعة</b>\n"
                            f"صفقات: <b>{_tot}</b> · رابحة: <b>{_win}</b> · خاسرة: <b>{_tot-_win}</b>\n"
                            f"الصافي: <b>{_net:+.1f}%</b>\n"
                            f"📈 LONG: <b>{_dir['LONG']:+.1f}%</b> · 📉 SHORT: <b>{_dir['SHORT']:+.1f}%</b>\n"
                            f"الموازين: صرامة {TUNE['strict']:.2f} · حصاد {TUNE['harvest']:.2f}\n{_mode}")
                except Exception:
                    pass
                try:
                    open(_REVIEW_F, "w").write(str(_now))
                except Exception:
                    pass
                log.info("🧭 مراجعة: %d صفقة، صافي %+.1f%% (L %+.1f / S %+.1f)", _tot, _net, _dir["LONG"], _dir["SHORT"])
        except Exception as _e:
            log.debug("self_review: %s", _e)
        await asyncio.sleep(3600)


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
            for _p in restored:
                try:
                    asyncio.create_task(monitor_position(_p))  # ⚡ فحص فوري بعد الاستعادة — لا فجوة عمياء بعد restart
                except Exception:
                    pass
    except Exception as _e:
        log.error("restore positions error: %s", _e)
    try:
        asyncio.create_task(_self_review_loop())  # 🧭 المراجعة اليومية الذاتية
    except Exception:
        pass
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
                # ⏱️ إيقاع متكيّف: يقظة 3s لو صفقة حقيقية أو قرب خطر (SL/انقلاب)؛ وإلا 10s
                try:
                    from quant_engine.watchdog import beat as _wb; _wb("manager")
                except Exception: pass
                await asyncio.sleep(3)  # ⚡ دورة موحّدة ورقي+حقيقي (العمق من الستريم = صفر REST)
                continue
            else:
                await asyncio.sleep(10)

        except Exception as e:
            log.error("PM loop error: %s", e)

        await asyncio.sleep(10)
