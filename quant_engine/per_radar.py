"""🎯 نموذج لكل رادار بعتبته — بدل نموذج واحد لسبعة.

مقيس 10 سبتمبر بتحقق منقى بحظر على 8542 صفقة:
  النموذج العام  AUC 0.501 · رفع -2.4%   ← عشوائي وضار
  DIP وحده       AUC 0.891 · رفع +36.2%  عند عتبة 0.75 (فوز 86.8%)
  SP  وحده       AUC 0.633 · رفع +13.8%  عند 0.75
  PH  وحده       AUC 0.542 · رفع +8.0%   عند 0.70
  MX  وحده       AUC 0.464 · رفع +0.2%   ← يجر الجميع للعشوائية

فخلط الرادارات يلغي اشارة كل منها. والحل: نموذج مستقل لكل رادار،
وعتبة مشتقة من تحققه هو، وبوابة لا يحصل عليها الا من يثبت تمييزا.

شروط البوابة (كلها معا): AUC >= 0.55 · رفع موجب · عينة >= 200
ومن لا نموذج له يمر — لا نمنع بلا دليل.

مختبر: يمنح المستحق ويحرم العشوائي والصغير، ويمنع الضعيفة ويمرر القوية.
الاطفاء: touch /opt/whalex/db/per_radar.off
"""
import os
import json
import time
import math
import logging
import sqlite3

log = logging.getLogger("per_radar")
DB = "/opt/whalex/ml_training.db"
OUT = "/opt/whalex/models"
OFF = "/opt/whalex/db/per_radar.off"

MIN_N = 200
MIN_AUC = 0.55
THRS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80)


def _rows():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    out = []
    for r in c.execute("SELECT * FROM training_signals WHERE outcome IS NOT NULL ORDER BY timestamp"):
        d = dict(r)
        t0 = int(d.get("timestamp") or 0)
        t1 = int(d.get("closed_at") or 0) or (t0 + 3600)
        if t0 <= 0 or d.get("outcome") not in (0, 1):
            continue
        d["t0"], d["t1"] = t0, max(t1, t0 + 60)
        out.append(d)
    c.close()
    return out


def train_all() -> dict:
    from quant_engine.ml_brain import _extract
    from quant_engine.validate import evaluate, fit_weights
    os.makedirs(OUT, exist_ok=True)
    tiers = {}
    for r in _rows():
        tiers.setdefault(str(r.get("tier") or "?"), []).append(r)
    report = {"trained_at": int(time.time()), "radars": {}}
    for t, rows in sorted(tiers.items()):
        if len(rows) < MIN_N:
            report["radars"][t] = {"gate": False, "why": f"عينة {len(rows)} < {MIN_N}"}
            continue
        base = evaluate(rows, _extract)
        if not base.get("ok"):
            report["radars"][t] = {"gate": False, "why": base.get("why")}
            continue
        best = None
        for thr in THRS:
            r = evaluate(rows, _extract, thr=thr)
            lf = r.get("lift")
            if lf is None:
                continue
            if best is None or lf > best["lift"]:
                best = {"thr": thr, "lift": lf, "wr": r.get("wr_at_thr")}
        gate = (base["auc"] >= MIN_AUC and best is not None and best["lift"] > 0)
        info = {"gate": gate, "n": len(rows), "auc": base["auc"],
                "base_wr": base["base_wr"], "thr": best["thr"] if best else None,
                "lift": best["lift"] if best else None,
                "wr_at_thr": best["wr"] if best else None}
        if gate:
            m = fit_weights(rows, _extract)
            if m:
                m.update({"tier": t, "trained_at": int(time.time()), "n": len(rows),
                          "auc": base["auc"], "thr": best["thr"], "lift": best["lift"]})
                with open(f"{OUT}/model_{t}.json", "w") as fp:
                    json.dump(m, fp, ensure_ascii=False)
            else:
                info["gate"] = False
                info["why"] = "تعذر التدريب"
        else:
            info["why"] = ("AUC %.3f < %.2f" % (base["auc"], MIN_AUC)
                           if base["auc"] < MIN_AUC else "رفع غير موجب")
            try:
                os.remove(f"{OUT}/model_{t}.json")
            except Exception:
                pass
        report["radars"][t] = info
    with open(f"{OUT}/report.json", "w") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=1)
    log.info("🎯 نماذج الرادارات: %d بوابة من %d",
             sum(1 for v in report["radars"].values() if v.get("gate")),
             len(report["radars"]))
    return report


_CACHE, _CACHE_TS = {}, 0.0


def _load(tier):
    global _CACHE, _CACHE_TS
    if time.time() - _CACHE_TS > 300:
        _CACHE, _CACHE_TS = {}, time.time()
    if tier not in _CACHE:
        try:
            _CACHE[tier] = json.load(open(f"{OUT}/model_{tier}.json"))
        except Exception:
            _CACHE[tier] = None
    return _CACHE[tier]


def allow(sig) -> tuple:
    """(نفتح؟، السبب، الاحتمال). من لا نموذج له يمر."""
    if os.path.exists(OFF):
        return True, "", 0.0
    try:
        g = (sig.get if isinstance(sig, dict)
             else lambda k, d=None: getattr(sig, k, d))
        t = str(g("tier", "") or "")
        m = _load(t)
        if not m:
            return True, "", 0.0
        from quant_engine.ml_brain import _extract
        row = {}
        for f in ("direction", "grade", "rsi", "range_pos", "volume_ratio",
                  "score", "confidence", "btc_trend", "regime", "leverage",
                  "funding", "oi_change", "ob_pressure", "cvd_flow",
                  "timestamp", "symbol", "strategy_count", "accuracy",
                  "rr_tp1", "rr_tp2", "rr_tp3", "macd_hist", "stoch_k"):
            row[f] = g(f, None)
        row["funding"] = g("funding_rate", row.get("funding"))
        row["oi_change"] = g("open_interest_change", row.get("oi_change"))
        z = m["prior"]
        for name, val in _extract(row).items():
            info = m["weights"].get(name, {}).get(val)
            if info:
                z += info["w"]
        p = 1 / (1 + math.exp(-max(-30, min(30, z))))
        thr = float(m.get("thr") or 0.55)
        if p < thr:
            return False, "نموذج %s: %.2f < %.2f" % (t, p, thr), p
        return True, "نموذج %s: %.2f" % (t, p), p
    except Exception as e:
        log.debug("allow: %s", e)
        return True, "", 0.0
