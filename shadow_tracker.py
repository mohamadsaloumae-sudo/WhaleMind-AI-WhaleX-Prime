"""
Shadow Tracker — يتابع كل إشارة (مفتوحة أو لا) بأثر رجعي وحيّ.
يحسب نتيجتها الوهمية (هل ضربت TP1 أم SL أولاً) من klines التاريخية،
ويكتب outcome في training_signals — لتدريب النموذج على كل القرارات.
آمن تماماً: لا يفتح صفقات، يقرأ أسعار ويكتب نتيجة فقط.
"""
import asyncio, time, logging, sqlite3
import httpx

log = logging.getLogger("shadow_tracker")
ML_DB = "/opt/whalex/ml_training.db"
TIMEOUT_HOURS = 24          # إشارة لم تُحسم خلال 24س → محايدة
CHECK_INTERVAL = 300        # كل 5 دقائق
KLINE_INTERVAL = "5m"

async def _fetch_klines_since(symbol: str, start_ms: int) -> list:
    """شموع 5m من لحظة الإشارة حتى الآن (يدعم startTime)."""
    url = (f"https://fapi.binance.com/fapi/v1/klines"
           f"?symbol={symbol}&interval={KLINE_INTERVAL}&startTime={start_ms}&limit=1000")
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(url)
            if r.status_code != 200:
                return []
            return r.json()
    except Exception as e:
        log.debug("shadow klines %s: %s", symbol, e)
        return []

def _resolve(direction: str, entry: float, sl: float, tp1: float, klines: list):
    """
    يمشي على الشموع بالترتيب، يحدّد أيّهما لُمس أولاً: TP1 أم SL.
    يرجع (result, exit_price) أو None إن لم يُحسم بعد.
    SHORT: ربح إن low<=tp1، خسارة إن high>=sl.
    LONG:  ربح إن high>=tp1، خسارة إن low<=sl.
    """
    for k in klines:
        high = float(k[2]); low = float(k[3])
        if direction == "SHORT":
            hit_tp = low <= tp1
            hit_sl = high >= sl
        else:
            hit_tp = high >= tp1
            hit_sl = low <= sl
        # لو الشمعة لمست الاثنين: نفترض الأسوأ (SL أولاً) — تحفّظ
        if hit_sl:
            return ("shadow_sl", sl)
        if hit_tp:
            return ("shadow_tp1", tp1)
    return None

def _pnl(direction: str, entry: float, exit_price: float) -> float:
    if entry <= 0:
        return 0.0
    if direction == "SHORT":
        return (entry - exit_price) / entry * 100
    return (exit_price - entry) / entry * 100


POSITIONS_DB = "/opt/whalex/positions.db"

def _real_open_positions() -> set:
    """يُرجِع مجموعة (symbol, direction) للصفقات الحقيقية المفتوحة.
    Shadow يتخطّاها حتى لا يبتلع صفّ الصفقة الحقيقية قبل تسجيل نتيجتها."""
    held = set()
    try:
        import json as _json
        conn = sqlite3.connect(POSITIONS_DB)
        for (data,) in conn.execute("SELECT data FROM active_positions WHERE status='open'"):
            try:
                d = _json.loads(data)
                sym = d.get("symbol"); dirn = d.get("direction")
                if sym and dirn:
                    held.add((sym, dirn))
            except Exception:
                continue
        conn.close()
    except Exception as e:
        log.debug("real_open_positions error: %s", e)
    return held


async def _process_pending():
    conn = sqlite3.connect(ML_DB)
    rows = conn.execute(
        "SELECT id, symbol, direction, entry, sl, tp1, timestamp "
        "FROM training_signals WHERE outcome IS NULL AND timestamp < ?",
        (int(time.time()) - 7200,)   # تأخير ساعتين: ندع المدير يحسم الصفقات الفعلية أولاً
    ).fetchall()
    conn.close()

    if not rows:
        return
    resolved = 0
    now = int(time.time())
    held = _real_open_positions()  # صفقات حقيقية مفتوحة — لا يلمسها shadow
    skipped = 0
    for rid, sym, direction, entry, sl, tp1, ts in rows:
        if not (entry and sl and tp1 and ts):
            continue
        if (sym, direction) in held:
            skipped += 1
            continue  # صفقة حقيقية مفتوحة — نتركها لـ update_result_by_match
        klines = await _fetch_klines_since(sym, int(ts) * 1000)
        if not klines:
            continue
        outcome = _resolve(direction, entry, sl, tp1, klines)
        if outcome:
            result, exit_price = outcome
            pnl = _pnl(direction, entry, exit_price)
            _write(rid, result, exit_price, pnl, 1 if pnl > 0 else 0)
            resolved += 1
        elif now - int(ts) > TIMEOUT_HOURS * 3600:
            # لم تضرب TP/SL خلال 24س → محايدة (outcome=2، لا تلوّث ربح/خسارة)
            _write(rid, "shadow_timeout", entry, 0.0, 2)
            resolved += 1
        await asyncio.sleep(0.15)  # احترام rate limit
    if resolved or skipped:
        log.info("🌓 Shadow: حُسمت %d | تخطّى %d (صفقات حقيقية مفتوحة)", resolved, skipped)

def _write(rid, result, exit_price, pnl, outcome):
    try:
        conn = sqlite3.connect(ML_DB)
        conn.execute(
            "UPDATE training_signals SET result=?, exit_price=?, pnl_pct=?, closed_at=?, outcome=? "
            "WHERE id=? AND outcome IS NULL",
            (result, exit_price, round(pnl, 3), int(time.time()), outcome, rid)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.debug("shadow write %d: %s", rid, e)

async def shadow_loop():
    log.info("🌓 Shadow Tracker بدأ — يتابع كل إشارة (أثر رجعي + حيّ)")
    while True:
        try:
            await _process_pending()
        except Exception as e:
            log.error("shadow loop: %s", e)
        await asyncio.sleep(CHECK_INTERVAL)
