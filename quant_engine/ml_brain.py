"""
🧠 ML Brain — عقل WhaleX المتعلّم
نموذج log-odds شفاف يتدرّب على training_signals (2372+ صفقة مكتملة):
لكل خاصية/قيمة يتعلّم وزنها من نسب النجاح الفعلية، ويعطي كل إشارة جديدة
احتمال نجاح + أقوى العوامل المؤثرة (قابل للتفسير — لا صندوق أسود).
الوضع الافتراضي: مراقبة فقط (ML_VETO_THRESHOLD=0). التفعيل كفيتو: ارفع العتبة.
"""
import asyncio, json, logging, math, sqlite3, time
from typing import Optional

log = logging.getLogger("ml_brain")
DB_PATH = "/opt/whalex/ml_training.db"
MODEL_PATH = "/opt/whalex/ml_model.json"
MIN_SAMPLES = 15          # قيمة بعينات أقل → وزن صفر (لا ثقة إحصائية)
ML_VETO_THRESHOLD = 0.38  # فيتو مفعّل: يرفض الإشارات دون 38% نجاح متوقّع (+8pts مثبتة)

# ─── تحويل الحقول الخام إلى فئات (bins) ───────────────────────
def _bin(name: str, v) -> Optional[str]:
    try:
        if v is None: return None
        if name in ("direction","grade","tier","regime","btc_trend","hawk_phase"):
            s = str(v).strip()
            return s if s else None
        x = float(v)
        if name == "confidence":
            return "<70" if x < 70 else "70-80" if x < 80 else "80-90" if x < 90 else "90+"
        if name == "score":
            return "<6" if x < 6 else "6-7.5" if x < 7.5 else "7.5-9" if x < 9 else "9+"
        if name == "rsi":
            if x <= 0: return None
            return "<35" if x < 35 else "35-50" if x < 50 else "50-65" if x < 65 else "65+"
        if name == "range_pos":
            return "<0.3" if x < 0.3 else "0.3-0.6" if x < 0.6 else "0.6-0.85" if x < 0.85 else "0.85+"
        if name == "funding":
            return "neg" if x < -0.0001 else "pos" if x > 0.0001 else "zero"
        if name == "oi_change":
            return "down" if x < -1 else "up" if x > 1 else "flat"
        if name == "hawk_modifier":
            return "<0.8" if x < 0.8 else "0.8-1.0" if x < 1.0 else "1.0+"
        if name == "volume_ratio":
            if x <= 0: return None
            return "<1" if x < 1 else "1-1.5" if x < 1.5 else "1.5+"
        if name == "key_strat_count":
            return "0-1" if x < 2 else "2-3" if x < 4 else "4+"
        if name == "hour_utc":
            h = int(x)
            return "00-06" if h < 6 else "06-12" if h < 12 else "12-18" if h < 18 else "18-24"
    except Exception:
        return None
    return None

FEATURES = ["direction","grade","tier","regime","btc_trend","hawk_phase",
            "confidence","score","rsi","range_pos","funding","oi_change",
            "hawk_modifier","volume_ratio","key_strat_count","hour_utc"]

def _extract(row: dict) -> dict:
    f = {}
    for name in FEATURES:
        v = row.get(name)
        if name == "hour_utc":
            ts = row.get("timestamp") or 0
            v = (int(ts) % 86400) / 3600 if ts else None
        b = _bin(name, v)
        if b is not None:
            f[name] = b
    return f

# ─── التدريب ───────────────────────────────────────────────────
def train(db_path: str = DB_PATH, model_path: str = MODEL_PATH) -> dict:
    conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM training_signals WHERE outcome IS NOT NULL").fetchall()]
    conn.close()
    W = sum(1 for r in rows if r["outcome"] == 1)
    L = len(rows) - W
    if W < 30 or L < 30:
        raise RuntimeError(f"عينات غير كافية للتدريب: wins={W} losses={L}")

    counts: dict = {}
    for r in rows:
        ok = r["outcome"] == 1
        for name, val in _extract(r).items():
            d = counts.setdefault(name, {}).setdefault(val, {"w": 0, "l": 0})
            d["w" if ok else "l"] += 1

    weights: dict = {}
    for name, vals in counts.items():
        K = max(len(vals), 2)
        for val, d in vals.items():
            n = d["w"] + d["l"]
            if n < MIN_SAMPLES:
                continue
            w = math.log((d["w"] + 1) / (W + K)) - math.log((d["l"] + 1) / (L + K))
            weights.setdefault(name, {})[val] = {
                "w": round(w, 4), "n": n, "wr": round(d["w"] / n * 100, 1)}

    model = {"trained_at": int(time.time()), "samples": len(rows),
             "wins": W, "losses": L, "base_wr": round(W / len(rows) * 100, 1),
             "prior": round(math.log(W / L), 4), "weights": weights}
    with open(model_path, "w") as fp:
        json.dump(model, fp, ensure_ascii=False)
    log.info("🧠 ML مدرَّب: %d عينة (نجاح أساسي %.1f%%) — %d وزن",
             len(rows), model["base_wr"], sum(len(v) for v in weights.values()))
    return model

_MODEL: dict = {}
def _load() -> dict:
    global _MODEL
    if not _MODEL:
        try:
            _MODEL = json.load(open(MODEL_PATH))
        except Exception:
            _MODEL = {}
    return _MODEL

# ─── التوقّع ───────────────────────────────────────────────────
def predict_signal(sig) -> tuple[float, str]:
    """احتمال نجاح الإشارة + أقوى 3 عوامل (نص عربي جاهز للوج)."""
    m = _load()
    if not m:
        return 0.5, "لا نموذج بعد"
    _get = (sig.get if isinstance(sig, dict)
            else lambda k, d=None: getattr(sig, k, d))
    row = {name: _get(name) for name in FEATURES}
    row["timestamp"] = _get("timestamp", int(time.time()))
    feats = _extract(row)
    z = m["prior"]; contribs = []
    for name, val in feats.items():
        info = m["weights"].get(name, {}).get(val)
        if info:
            z += info["w"]
            contribs.append((abs(info["w"]), f"{name}={val}({info['wr']:.0f}%)", info["w"]))
    prob = 1 / (1 + math.exp(-z))
    contribs.sort(reverse=True)
    top = " | ".join(("+" if c[2] > 0 else "−") + c[1] for c in contribs[:3]) or "-"
    return prob, top

async def retrain_loop(interval_h: int = 24):
    """إعادة تدريب يومية تلقائية — النموذج يكبر مع كل صفقة جديدة."""
    global _MODEL
    while True:
        try:
            train(); _MODEL = {}
        except Exception as e:
            log.warning("ml retrain: %s", e)
        await asyncio.sleep(interval_h * 3600)

# ─── تقرير المحلّل الإحصائي ─────────────────────────────────────
def report() -> str:
    m = _load() or train()
    lines = [f"🧠 نموذج WhaleX — {m['samples']} صفقة | نجاح أساسي {m['base_wr']}% "
             f"({m['wins']}✅/{m['losses']}❌)", "═" * 52]
    for name in ("tier","grade","direction","regime","hawk_phase","confidence","rsi"):
        vals = m["weights"].get(name)
        if not vals: continue
        lines.append(f"▸ {name}:")
        for val, i in sorted(vals.items(), key=lambda x: -x[1]["wr"]):
            lines.append(f"    {val:<12} نجاح {i['wr']:5.1f}%  (n={i['n']})")
    flat = [(i["w"], f"{n}={v}", i) for n, vs in m["weights"].items() for v, i in vs.items()]
    flat.sort(reverse=True)
    lines.append("═" * 52)
    lines.append("🏆 أقوى 6 عوامل نجاح:")
    for w, k, i in flat[:6]:
        lines.append(f"    {k:<26} {i['wr']:5.1f}%  (n={i['n']})")
    lines.append("☠️ أسوأ 6 عوامل:")
    for w, k, i in flat[-6:]:
        lines.append(f"    {k:<26} {i['wr']:5.1f}%  (n={i['n']})")
    return "\n".join(lines)

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "train"
    if cmd == "train":
        train(); print(report())
    elif cmd == "report":
        print(report())


def smart_leverage(sig, cap: int = 10) -> int:
    """رافعة ذكية موحّدة تُحسب عند ولادة الإشارة (تظهر بالرسالة والبطاقة).
    المعادلة = معادلة التنفيذ نفسها: ميزانية مخاطرة 20% ÷ مسافة الوقف × جودة التوقّع."""
    try:
        entry = float(getattr(sig, "entry", 0) or 0)
        sl = float(getattr(sig, "sl", 0) or 0)
        fallback = int(float(getattr(sig, "leverage", 3) or 3))
        if entry <= 0 or sl <= 0:
            return fallback
        sl_dist = abs(entry - sl) / entry * 100
        if sl_dist < 0.3:
            return fallback
        try:
            p_win, _ = predict_signal(sig)
        except Exception:
            p_win = 0.5
        q = 0.75 if p_win < 0.45 else (1.0 if p_win < 0.55 else (1.25 if p_win < 0.65 else 1.5))
        lev = int(20.0 * q / sl_dist + 0.5)
        return max(1, min(cap, lev))
    except Exception:
        return 3
