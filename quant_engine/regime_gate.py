"""🌐 بوابة النظام — كل رادار يعمل في الانظمة التي يربح فيها فقط.

مقيس 10 سبتمبر على 6047 صفقة و1000 ساعة من 12 عملة:
  PH  في BULL|CALM  +3.04%  وفي BEAR|WILD  -0.74%
  MX  في BULL|CALM  +0.67%  وفي BEAR|CALM  -1.16%  (22% فوز · -232 نقطة)
  SP  خاسر في 6 من 7 انظمة
والفرق بين افضل نظام واسوأه 4 نقاط مئوية لنفس الرادار.

المنهج: نقيس اتساع السوق (كم عملة صاعدة) وتقلبه من 12 عملة — لا من
البتكوين وحده لان الالتكوين لا تتبعه دائما. والعتبات من توزيع
البيانات (اثلاث) فتتكيف تلقائيا حين يتغير السوق نفسه.

القاعدة: يُمنع الرادار في نظام اذا متوسطه سالب وعينته >= 50.
مختبر: يمنع الخاسر ويمرر الرابح ولا يمنع بعينة صغيرة.
الاطفاء: touch /opt/whalex/db/regime_gate.off
"""
import os
import json
import math
import time
import logging
import sqlite3

log = logging.getLogger("regime_gate")

SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT",
        "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT", "DOTUSDT", "NEARUSDT"]
W = 24
MIN_N = 50
ML_DB = "/opt/whalex/ml_training.db"
OUT = "/opt/whalex/models/regime_map.json"
STATE = "/opt/whalex/models/regime_now.json"
OFF = "/opt/whalex/db/regime_gate.off"
REFRESH = 900


def _klines(sym, limit=1000):
    import urllib.request
    u = ("https://fapi.binance.com/fapi/v1/klines?symbol=%s&interval=1h&limit=%d"
         % (sym, limit))
    try:
        return json.load(urllib.request.urlopen(u, timeout=25))
    except Exception:
        return []


def _series(limit=1000):
    data = {}
    for s in SYMS:
        k = _klines(s, limit)
        if k:
            data[s] = {r[0] // 1000: float(r[4]) for r in k}
        time.sleep(0.2)
    return data


def _features(data):
    if len(data) < 4:
        return []
    times = sorted(set.intersection(*[set(v) for v in data.values()]))
    out = []
    for i in range(W + 1, len(times)):
        rets, vols = [], []
        for px in data.values():
            a, b = px.get(times[i - W]), px.get(times[i])
            if a and b:
                rets.append((b - a) / a * 100)
            rr = []
            for j in range(i - W + 1, i + 1):
                p0, p1 = px.get(times[j - 1]), px.get(times[j])
                if p0 and p1:
                    rr.append((p1 - p0) / p0 * 100)
            if rr:
                m = sum(rr) / len(rr)
                vols.append(math.sqrt(sum((x - m) ** 2 for x in rr) / len(rr)))
        if rets:
            out.append((times[i],
                        {"b": sum(1 for x in rets if x > 0) / len(rets),
                         "v": sum(vols) / max(1, len(vols))}))
    return out


def _fit(feats):
    br = sorted(f["b"] for _, f in feats)
    vl = sorted(f["v"] for _, f in feats)
    n = len(br)
    if n < 9:
        return None
    return {"b1": br[n // 3], "b2": br[2 * n // 3],
            "v1": vl[n // 3], "v2": vl[2 * n // 3]}


def _label(f, th):
    d = ("BEAR" if f["b"] <= th["b1"] else
         "BULL" if f["b"] >= th["b2"] else "MIXED")
    s = ("CALM" if f["v"] <= th["v1"] else
         "WILD" if f["v"] >= th["v2"] else "NORM")
    return "%s|%s" % (d, s)


def build_map() -> dict:
    import collections
    data = _series(1000)
    feats = _features(data)
    th = _fit(feats)
    if not th or not feats:
        return {"ok": False, "why": "بيانات سوق غير كافية"}

    def at(t):
        if t < feats[0][0]:
            return None
        lo, hi = 0, len(feats) - 1
        while lo < hi:
            m = (lo + hi + 1) // 2
            if feats[m][0] <= t:
                lo = m
            else:
                hi = m - 1
        return _label(feats[lo][1], th)

    c = sqlite3.connect("file:%s?mode=ro" % ML_DB, uri=True)
    c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute(
        "SELECT tier, pnl_pct, timestamp FROM training_signals "
        "WHERE pnl_pct IS NOT NULL AND timestamp >= ?", (feats[0][0],))]
    c.close()

    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        g = at(r["timestamp"])
        if g:
            by[str(r["tier"])][g].append(r["pnl_pct"])

    block, stats = {}, {}
    for t, gs in by.items():
        stats[t] = {}
        for g, v in gs.items():
            avg = sum(v) / len(v)
            stats[t][g] = {"n": len(v), "avg": round(avg, 3),
                           "sum": round(sum(v), 1),
                           "wr": round(sum(1 for x in v if x > 0) * 100 / len(v), 1)}
            if len(v) >= MIN_N and avg < 0:
                block.setdefault(t, []).append(g)

    m = {"ok": True, "built_at": int(time.time()), "thr": th,
         "block": block, "stats": stats, "n_rows": len(rows)}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fp:
        json.dump(m, fp, ensure_ascii=False, indent=1)
    log.info("🌐 خريطة الأنظمة: %d رادار · %d منع · %d صفقة",
             len(stats), sum(len(v) for v in block.values()), len(rows))
    return m


_NOW, _NOW_TS = None, 0.0


def current() -> str:
    global _NOW, _NOW_TS
    if _NOW and time.time() - _NOW_TS < REFRESH:
        return _NOW
    try:
        mp = json.load(open(OUT))
        th = mp["thr"]
        feats = _features(_series(60))
        if feats:
            _NOW = _label(feats[-1][1], th)
            _NOW_TS = time.time()
            try:
                with open(STATE, "w") as fp:
                    json.dump({"regime": _NOW, "ts": int(time.time()),
                               "b": round(feats[-1][1]["b"], 3),
                               "v": round(feats[-1][1]["v"], 4)}, fp)
            except Exception:
                pass
    except Exception as e:
        log.debug("current regime: %s", e)
    return _NOW or "UNKNOWN"


def allow(tier: str) -> tuple:
    """(نسمح؟، السبب). من لا بيانات له يمر."""
    if os.path.exists(OFF):
        return True, ""
    try:
        mp = json.load(open(OUT))
        g = current()
        if g in ("UNKNOWN", None):
            return True, ""
        bad = mp.get("block", {}).get(str(tier), [])
        if g in bad:
            st = mp.get("stats", {}).get(str(tier), {}).get(g, {})
            return False, "نظام %s: %s خاسر فيه (%s%% فوز · %s%%)" % (
                g, tier, st.get("wr"), st.get("avg"))
        return True, g
    except Exception as e:
        log.debug("regime allow: %s", e)
    return True, ""
