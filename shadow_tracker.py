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

def _real_result(symbol, direction, ts):
    """نتيجة المشتركين الحقيقية لهذه الاشارة — أو لا شيء."""
    try:
        import sqlite3 as _s
        c = _s.connect("file:/opt/whalex/db/whalex.db?mode=ro", uri=True)
        c.row_factory = _s.Row
        rows = [dict(r) for r in c.execute(
            "SELECT pnl_pct, exit_price, net_usdt, real_net FROM user_trades "
            "WHERE symbol=? AND direction=? AND market='futures' "
            "AND closed_at IS NOT NULL AND opened_at BETWEEN ? AND ?",
            (symbol, direction, ts - 300, ts + 1800))]
        c.close()
        if not rows:
            return None
        pcts = [float(r["pnl_pct"] or 0) for r in rows]
        xs = [float(r["exit_price"] or 0) for r in rows if r["exit_price"]]
        return {"pnl": round(sum(pcts) / len(pcts), 3),
                "exit": round(sum(xs) / len(xs), 8) if xs else 0.0,
                "n": len(rows)}
    except Exception as e:
        log.debug("real_result %s: %s", symbol, e)
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
        # 🛡️ نُفّذت لمشترك؟ فنتيجتها الحقيقية لا النظرية.
        #    مقيس 16 سبتمبر: POWER سُجّلت shadow_sl -5.00% وربح بها
        #    ثلاثة مشتركين (+1.64$ · +1.88$ · +0.91$)، و龙虾 سُجّلت
        #    shadow_tp1 +7.50% وخسر بها ثلاثة (-1.67$ · -1.70$ · -1.18$).
        #    فالمتتبّع يمشي على الشموع حتى يلمس الوقف النظري ويكتبه،
        #    بينما الحارس أغلق المركز الحقيقي عند -1.7%. والنتيجة:
        #    39 من 40 صفقة اليوم موسومة shadow وهي منفّذة بأموال حقيقية،
        #    فتُستبعد من الشاشة ويتعلّم النموذج من نتائج معكوسة.
        _real = _real_result(sym, direction, int(ts))
        if _real:
            _write(rid, "win" if _real["pnl"] > 0 else "loss",
                   _real["exit"], _real["pnl"], 1 if _real["pnl"] > 0 else 0)
            resolved += 1
            log.info("🎯 %s %s: نتيجة حقيقية %+.2f%% (%d مشترك) — لا ظلّ",
                     sym, direction, _real["pnl"], _real["n"])
            continue
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

def _peak_pct(rid):
    """الذروة الحقيقية من spot_state — كانت تُكتب = pnl فتُفقد."""
    try:
        c = sqlite3.connect(ML_DB)
        r = c.execute("SELECT symbol, direction, entry FROM training_signals "
                      "WHERE id=?", (rid,)).fetchone()
        c.close()
        if not r or not r[2]:
            return None
        w = sqlite3.connect("/opt/whalex/db/whalex.db")
        q = w.execute(
            "SELECT s.peak FROM spot_state s JOIN signals g ON g.id=s.sig_id "
            "WHERE g.symbol=? AND g.radar_type='spot' AND s.peak>0 "
            "ORDER BY s.updated DESC LIMIT 1", (r[0],)).fetchone()
        w.close()
        if not q or not q[0]:
            return None
        e = float(r[2])
        pk = float(q[0])
        if e <= 0 or pk <= 0:
            return None
        return round((pk - e) / e * 100.0, 3)
    except Exception:
        return None


def _write(rid, result, exit_price, pnl, outcome):
    try:
        conn = sqlite3.connect(ML_DB)
        # 📊 نكتب سبب الإغلاق والقمة أيضاً — كانا يبقيان فارغين في 96% من الصفوف
        conn.execute(
            "UPDATE training_signals SET result=?, exit_price=?, pnl_pct=?, closed_at=?, "
            "outcome=?, close_reason=COALESCE(close_reason,?), peak_pnl=COALESCE(peak_pnl,?) "
            "WHERE id=? AND outcome IS NULL",
            (result, exit_price, round(pnl, 3), int(time.time()), outcome,
             result, (_peak_pct(rid) if _peak_pct(rid) is not None
                      else (round(pnl, 3) if pnl > 0 else 0.0)), rid)
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
