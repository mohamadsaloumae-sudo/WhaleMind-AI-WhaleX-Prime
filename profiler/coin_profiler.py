"""
WhaleMind Coin Behavior Profiler V2 — معايير صارمة احترافية
═══════════════════════════════════════════════════════════════════
التحديثات:
- ❌ حظر العملات < $20M حجم يومي
- ❌ حظر manipulation_score > 0.15
- ❌ حظر false_breakout_rate > 0.45
- ✅ تصنيف Tier (1-4) لكل عملة
- ✅ تعديل threshold + leverage حسب السيولة
"""

import asyncio
import httpx
import logging
import time
import math
import statistics
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

log = logging.getLogger("coin_profiler")

BINANCE_FAPI = "https://fapi.binance.com/fapi/v1"

# ═══════════════════════════════════════════════════════════════
# ─── معايير احترافية صارمة ─────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

# عتبات السيولة (USDT)
MIN_DAILY_VOLUME = 20_000_000      # < $20M = حظر مطلق
TIER1_VOLUME = 100_000_000          # > $100M = عملات قوية
TIER2_VOLUME = 50_000_000           # $50M-$100M = متوسط
TIER3_VOLUME = 20_000_000           # $20M-$50M = حذر

# عتبات التلاعب
MAX_MANIPULATION_SCORE = 0.15       # > 15% = حظر
MAX_FALSE_BREAKOUT_RATE = 0.45      # > 45% = حظر

# عتبات spike (قفزات شاذة)
MAX_SPIKES_PER_30_DAYS = 12         # أكثر من 12 قفزة = مشكوكة


PROFILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS coin_profiles (
    symbol               TEXT    PRIMARY KEY,
    tier                 INTEGER, -- 1=قوية, 2=متوسط, 3=حذر, 4=محظورة
    avg_atr_pct          REAL,
    volatility_class     TEXT,
    active_hours         TEXT,
    behavior_pattern     TEXT,
    btc_correlation      REAL,
    manipulation_score   REAL,
    false_breakout_rate  REAL,
    avg_daily_volume     REAL,
    avg_candle_range_pct REAL,
    biggest_pump_pct     REAL,
    biggest_dump_pct     REAL,
    spike_count          INTEGER,
    quiet_hours          TEXT,
    btc_decoupling_pct   REAL,
    sample_days          INTEGER,
    safe_to_trade        INTEGER DEFAULT 0,
    confidence_threshold REAL,
    recommended_leverage INTEGER,
    last_updated         TIMESTAMP,
    notes                TEXT,
    rejection_reason     TEXT
);
CREATE INDEX IF NOT EXISTS idx_safe_to_trade ON coin_profiles(safe_to_trade);
CREATE INDEX IF NOT EXISTS idx_tier ON coin_profiles(tier);
"""


# ═══════════════════════════════════════════════════════════════
# ─── DATA FETCHING ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def fetch_klines(symbol: str, interval: str = "1h", limit: int = 720) -> List[list]:
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                f"{BINANCE_FAPI}/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit}
            )
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        log.warning("fetch_klines %s: %s", symbol, e)
    return []


async def fetch_btc_baseline(interval: str = "1h", limit: int = 720) -> List[float]:
    klines = await fetch_klines("BTCUSDT", interval, limit)
    return [float(k[4]) for k in klines]


# ═══════════════════════════════════════════════════════════════
# ─── ANALYSIS FUNCTIONS ────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def calculate_atr_pct(klines: List[list]) -> float:
    if len(klines) < 14:
        return 0.0
    trs = []
    for i in range(1, len(klines)):
        high, low, prev_close = float(klines[i][2]), float(klines[i][3]), float(klines[i-1][4])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        avg_price = (high + low) / 2
        if avg_price > 0:
            trs.append((tr / avg_price) * 100)
    return round(statistics.mean(trs), 3) if trs else 0.0


def classify_volatility(atr_pct: float) -> str:
    if atr_pct < 0.5: return "low"
    if atr_pct < 1.5: return "medium"
    if atr_pct < 3.0: return "high"
    return "extreme"


def detect_active_hours(klines: List[list]) -> tuple[List[int], List[int]]:
    if len(klines) < 24:
        return list(range(24)), []
    hour_volumes: Dict[int, List[float]] = {h: [] for h in range(24)}
    for k in klines:
        ts = int(k[0]) // 1000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        hour_volumes[dt.hour].append(float(k[5]) * float(k[4]))
    avg_hour_vol = {h: statistics.mean(v) if v else 0 for h, v in hour_volumes.items()}
    sorted_h = sorted(avg_hour_vol.items(), key=lambda x: x[1], reverse=True)
    return sorted([h for h, _ in sorted_h[:6]]), sorted([h for h, _ in sorted_h[-6:]])


def detect_behavior_pattern(klines: List[list]) -> str:
    if len(klines) < 50:
        return "unknown"
    closes = [float(k[4]) for k in klines]
    volumes = [float(k[5]) * float(k[4]) for k in klines]
    avg_vol = statistics.mean(volumes)
    if avg_vol < 100_000:
        return "dead"
    n = len(closes)
    x_vals = list(range(n))
    x_mean, y_mean = sum(x_vals) / n, sum(closes) / n
    num = sum((x_vals[i] - x_mean) * (closes[i] - y_mean) for i in range(n))
    den_x = sum((x - x_mean) ** 2 for x in x_vals)
    den_y = sum((y - y_mean) ** 2 for y in closes)
    if den_x * den_y == 0:
        return "ranging"
    correlation = num / math.sqrt(den_x * den_y)
    r_squared = correlation ** 2
    pct_changes = [abs((closes[i] - closes[i-1]) / closes[i-1]) * 100 for i in range(1, n)]
    avg_change = statistics.mean(pct_changes)
    if r_squared > 0.6:
        return "trending"
    if avg_change > 1.5:
        return "wild"
    return "ranging"


def detect_false_breakouts(klines: List[list]) -> float:
    if len(klines) < 40:
        return 0.0
    closes = [float(k[4]) for k in klines]
    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    total, false_bk = 0, 0
    for i in range(20, len(klines) - 3):
        prev_high = max(highs[i-20:i])
        prev_low = min(lows[i-20:i])
        if highs[i] > prev_high * 1.005:
            total += 1
            if min(closes[i+1:i+4]) < prev_high:
                false_bk += 1
        if lows[i] < prev_low * 0.995:
            total += 1
            if max(closes[i+1:i+4]) > prev_low:
                false_bk += 1
    return round(false_bk / total, 3) if total else 0.0


def calculate_btc_correlation(coin_klines: List[list], btc_closes: List[float]) -> float:
    if len(coin_klines) < 50 or len(btc_closes) < 50:
        return 0.0
    coin_closes = [float(k[4]) for k in coin_klines]
    min_len = min(len(coin_closes), len(btc_closes))
    coin_closes = coin_closes[-min_len:]
    btc_closes = btc_closes[-min_len:]
    coin_rets = [(coin_closes[i] - coin_closes[i-1]) / coin_closes[i-1] for i in range(1, min_len)]
    btc_rets = [(btc_closes[i] - btc_closes[i-1]) / btc_closes[i-1] for i in range(1, min_len)]
    n = len(coin_rets)
    if n == 0:
        return 0.0
    mc, mb = sum(coin_rets) / n, sum(btc_rets) / n
    num = sum((coin_rets[i] - mc) * (btc_rets[i] - mb) for i in range(n))
    dc = math.sqrt(sum((r - mc) ** 2 for r in coin_rets))
    db = math.sqrt(sum((r - mb) ** 2 for r in btc_rets))
    if dc * db == 0:
        return 0.0
    return round(num / (dc * db), 3)


def calculate_manipulation_score(klines: List[list]) -> float:
    if len(klines) < 30:
        return 0.0
    suspicious, total = 0, 0
    for i in range(1, len(klines)):
        op, hi, lo, cl, vol = float(klines[i][1]), float(klines[i][2]), float(klines[i][3]), float(klines[i][4]), float(klines[i][5])
        body = abs(cl - op)
        full_range = hi - lo
        if full_range == 0 or op == 0:
            continue
        total += 1
        if body / full_range < 0.2 and full_range / op > 0.02:
            suspicious += 1; continue
        if i >= 10:
            avg_vol = statistics.mean([float(klines[j][5]) for j in range(i-10, i)])
            if avg_vol > 0 and vol > avg_vol * 5:
                suspicious += 1; continue
        change = abs(cl - op) / op * 100
        if change > 5:
            suspicious += 1
    return round(suspicious / total, 3) if total else 0.0


def count_spikes(klines: List[list]) -> int:
    count = 0
    for k in klines:
        op, cl = float(k[1]), float(k[4])
        if op > 0 and abs(cl - op) / op * 100 > 5:
            count += 1
    return count


def find_biggest_moves(klines: List[list]) -> tuple[float, float]:
    pump = dump = 0.0
    for k in klines:
        op, hi, lo = float(k[1]), float(k[2]), float(k[3])
        if op == 0: continue
        p = (hi - op) / op * 100
        d = (lo - op) / op * 100
        if p > pump: pump = p
        if d < dump: dump = d
    return round(pump, 2), round(dump, 2)


def calculate_decoupling(coin_klines: List[list], btc_closes: List[float]) -> float:
    if len(coin_klines) < 30 or len(btc_closes) < 30:
        return 0.0
    coin_closes = [float(k[4]) for k in coin_klines]
    min_len = min(len(coin_closes), len(btc_closes))
    coin_closes, btc_closes = coin_closes[-min_len:], btc_closes[-min_len:]
    opposite, total = 0, 0
    for i in range(1, min_len):
        cc = coin_closes[i] - coin_closes[i-1]
        bc = btc_closes[i] - btc_closes[i-1]
        if abs(cc / coin_closes[i-1]) < 0.001 or abs(bc / btc_closes[i-1]) < 0.001:
            continue
        total += 1
        if (cc > 0 and bc < 0) or (cc < 0 and bc > 0):
            opposite += 1
    return round(opposite / total, 3) if total else 0.0


# ═══════════════════════════════════════════════════════════════
# ─── DECISION ENGINE — معايير صارمة احترافية ───────────────────
# ═══════════════════════════════════════════════════════════════

def decide_trade_safety(profile: dict) -> tuple[bool, int, float, int, str, str]:
    """
    يحدد:
    - safe_to_trade (bool)
    - tier (1-4)
    - confidence_threshold
    - recommended_leverage
    - notes
    - rejection_reason (إن وجد)
    """
    daily_vol = profile.get("avg_daily_volume", 0)
    manip = profile.get("manipulation_score", 0)
    false_bk = profile.get("false_breakout_rate", 0)
    pattern = profile.get("behavior_pattern", "")
    vol_class = profile.get("volatility_class", "")
    spikes = profile.get("spike_count", 0)
    decoupling = profile.get("btc_decoupling_pct", 0)
    
    # ════ شروط الرفض المطلق ════
    
    if pattern == "dead":
        return False, 4, 0, 0, "❌ Dead coin", "حجم منخفض جداً"
    
    if daily_vol < MIN_DAILY_VOLUME:
        vol_m = daily_vol / 1_000_000
        return False, 4, 0, 0, f"❌ سيولة ضعيفة (${vol_m:.1f}M)", f"الحجم اليومي < $20M (${vol_m:.1f}M)"
    
    if manip > MAX_MANIPULATION_SCORE:
        return False, 4, 0, 0, f"❌ تلاعب عالٍ ({manip*100:.0f}%)", f"manipulation_score > 15%"
    
    if false_bk > MAX_FALSE_BREAKOUT_RATE:
        return False, 4, 0, 0, f"❌ فخاخ كثيرة ({false_bk*100:.0f}%)", f"false_breakouts > 45%"
    
    if spikes > MAX_SPIKES_PER_30_DAYS:
        return False, 4, 0, 0, f"❌ قفزات شاذة ({spikes})", "spike_count > 12 in 30 days"
    
    # ════ تصنيف Tier ════
    
    if daily_vol >= TIER1_VOLUME:
        tier = 1
        threshold = 65.0
        leverage = 5
        notes_list = ["✅ Tier 1 — سيولة ممتازة"]
    elif daily_vol >= TIER2_VOLUME:
        tier = 2
        threshold = 72.0
        leverage = 4
        notes_list = ["⭐ Tier 2 — سيولة متوسطة"]
    else:  # TIER3_VOLUME <= vol < TIER2_VOLUME
        tier = 3
        threshold = 80.0
        leverage = 3
        notes_list = ["⚠️ Tier 3 — سيولة محدودة"]
    
    # ════ تعديلات حسب التقلب ════
    
    if vol_class == "extreme":
        threshold += 10
        leverage = max(1, leverage - 4)
        notes_list.append("⚠️ تقلبات عنيفة")
    elif vol_class == "high":
        threshold += 5
        leverage = max(2, leverage - 2)
        notes_list.append("تقلبات مرتفعة")
    elif vol_class == "low":
        threshold = max(60, threshold - 3)
        leverage = min(6, leverage + 2)
        notes_list.append("✅ تقلبات منخفضة")
    
    # ════ تعديلات حسب النمط ════
    
    if pattern == "wild":
        threshold += 8
        leverage = max(1, leverage - 2)
        notes_list.append("⚠️ نمط عشوائي")
    elif pattern == "trending":
        threshold = max(60, threshold - 3)
        notes_list.append("✅ ترندي")
    
    # ════ تعديلات حسب التلاعب ════
    
    if manip > 0.08:
        threshold += 3
        notes_list.append("تلاعب ملحوظ")
    
    if false_bk > 0.35:
        threshold += 3
        notes_list.append("فخاخ متوسطة")
    
    # ════ حدود نهائية ════
    
    threshold = max(60, min(95, threshold))
    leverage = max(1, min(20, leverage))
    
    return True, tier, round(threshold, 1), leverage, " | ".join(notes_list), ""


# ═══════════════════════════════════════════════════════════════
# ─── MAIN PROFILER ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def build_profile(symbol: str, btc_closes: List[float] = None) -> Optional[dict]:
    klines = await fetch_klines(symbol, "1h", 720)
    if len(klines) < 100:
        log.warning("%s: insufficient data (%d candles)", symbol, len(klines))
        return None
    
    avg_atr = calculate_atr_pct(klines)
    vol_class = classify_volatility(avg_atr)
    active_hrs, quiet_hrs = detect_active_hours(klines)
    pattern = detect_behavior_pattern(klines)
    false_bk = detect_false_breakouts(klines)
    
    daily_volumes, current = [], 0
    for i, k in enumerate(klines):
        current += float(k[5]) * float(k[4])
        if (i + 1) % 24 == 0:
            daily_volumes.append(current)
            current = 0
    avg_daily_vol = round(statistics.mean(daily_volumes)) if daily_volumes else 0
    
    candle_ranges = []
    for k in klines:
        hi, lo, op = float(k[2]), float(k[3]), float(k[1])
        if op > 0:
            candle_ranges.append((hi - lo) / op * 100)
    avg_range = round(statistics.mean(candle_ranges), 3) if candle_ranges else 0
    
    manip_score = calculate_manipulation_score(klines)
    spikes = count_spikes(klines)
    pump, dump = find_biggest_moves(klines)
    
    if btc_closes is None:
        btc_closes = await fetch_btc_baseline()
    btc_corr = calculate_btc_correlation(klines, btc_closes)
    decoupling = calculate_decoupling(klines, btc_closes)
    
    profile = {
        "symbol": symbol,
        "avg_atr_pct": avg_atr,
        "volatility_class": vol_class,
        "active_hours": active_hrs,
        "quiet_hours": quiet_hrs,
        "behavior_pattern": pattern,
        "btc_correlation": btc_corr,
        "btc_decoupling_pct": decoupling,
        "manipulation_score": manip_score,
        "false_breakout_rate": false_bk,
        "avg_daily_volume": avg_daily_vol,
        "avg_candle_range_pct": avg_range,
        "biggest_pump_pct": pump,
        "biggest_dump_pct": dump,
        "spike_count": spikes,
        "sample_days": len(klines) // 24,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    
    safe, tier, threshold, leverage, notes, rejection = decide_trade_safety(profile)
    profile["safe_to_trade"] = 1 if safe else 0
    profile["tier"] = tier
    profile["confidence_threshold"] = threshold
    profile["recommended_leverage"] = leverage
    profile["notes"] = notes
    profile["rejection_reason"] = rejection
    
    return profile


def save_profile_sqlite(db_path: str, profile: dict):
    import sqlite3, json
    conn = sqlite3.connect(db_path)
    conn.executescript(PROFILE_SCHEMA)
    p = profile.copy()
    p["active_hours"] = json.dumps(p["active_hours"])
    p["quiet_hours"] = json.dumps(p["quiet_hours"])
    cols = list(p.keys())
    placeholders = ",".join(["?"] * len(cols))
    cols_str = ",".join(cols)
    conn.execute(
        f"INSERT OR REPLACE INTO coin_profiles ({cols_str}) VALUES ({placeholders})",
        [p[c] for c in cols]
    )
    conn.commit()
    conn.close()


def load_profile_sqlite(db_path: str, symbol: str) -> Optional[dict]:
    import sqlite3, json
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM coin_profiles WHERE symbol = ?", (symbol,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        p = dict(row)
        p["active_hours"] = json.loads(p["active_hours"]) if p["active_hours"] else []
        p["quiet_hours"] = json.loads(p["quiet_hours"]) if p["quiet_hours"] else []
        return p
    except Exception as e:
        log.warning("load_profile error: %s", e)
        return None


async def build_all_profiles(symbols: List[str], db_path: str, concurrency: int = 5):
    log.info("🚀 Building profiles for %d coins with STRICT criteria", len(symbols))
    btc_closes = await fetch_btc_baseline()
    log.info("✅ BTC baseline loaded (%d candles)", len(btc_closes))
    
    sem = asyncio.Semaphore(concurrency)
    completed = failed = 0
    
    async def process(sym):
        nonlocal completed, failed
        async with sem:
            try:
                profile = await build_profile(sym, btc_closes)
                if profile:
                    save_profile_sqlite(db_path, profile)
                    completed += 1
                    flag = "✅" if profile["safe_to_trade"] else "❌"
                    log.info("%s %s: Tier%d | %s/%s | %s",
                             flag, sym, profile["tier"],
                             profile["volatility_class"], profile["behavior_pattern"],
                             profile["notes"][:50])
                else:
                    failed += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                failed += 1
                log.warning("❌ %s: %s", sym, e)
    
    await asyncio.gather(*[process(s) for s in symbols])
    log.info("✅ Done. Completed: %d | Failed: %d", completed, failed)
    return completed, failed


def should_emit_signal(profile: Optional[dict], signal_confidence: float) -> tuple[bool, str]:
    """فلتر للرادار"""
    if profile is None:
        return False, "لا توجد بيانات سلوكية"
    if profile.get("safe_to_trade") != 1:
        return False, profile.get("rejection_reason", "غير آمنة")
    threshold = profile.get("confidence_threshold", 70)
    if signal_confidence < threshold:
        return False, f"الثقة {signal_confidence:.0f}% < المطلوب {threshold:.0f}%"
    now_hour = datetime.now(timezone.utc).hour
    quiet_hours = profile.get("quiet_hours", [])
    if now_hour in quiet_hours:
        return False, f"الساعة {now_hour} UTC ضمن السكون"
    return True, f"✅ Tier {profile.get('tier', '?')}"


def get_safe_leverage(profile: Optional[dict], base_leverage: int) -> int:
    if profile is None:
        return min(base_leverage, 2)
    return min(base_leverage, profile.get("recommended_leverage", 5))


async def cli_main():
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    db_path = "/opt/whalex/coin_profiles.db"
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        symbol = sys.argv[2] if len(sys.argv) > 2 else "BTCUSDT"
        profile = await build_profile(symbol)
        if profile:
            import json
            print(json.dumps(profile, indent=2, ensure_ascii=False))
        return
    
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{BINANCE_FAPI}/exchangeInfo")
        info = r.json()
        symbols = [
            s["symbol"] for s in info["symbols"]
            if s["status"] == "TRADING" and s["symbol"].endswith("USDT")
            and s.get("contractType") == "PERPETUAL"
        ]
    log.info("📊 Found %d USDT perpetual pairs", len(symbols))
    completed, failed = await build_all_profiles(symbols, db_path)
    print(f"\n✅ Completed: {completed} | Failed: {failed}")


if __name__ == "__main__":
    asyncio.run(cli_main())
