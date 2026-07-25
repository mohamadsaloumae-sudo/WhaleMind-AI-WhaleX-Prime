#!/usr/bin/env python3
"""🧠 مدرّب النموذج — مستقل تماماً، لا سلطة على القرار.

يقرأ النتائج المكتملة، يدرّب، ويقيس على بيانات لم يرها.
التقسيم زمنيّ لا عشوائيّ: نتدرّب على الماضي ونختبر على ما بعده،
كما يحدث في الواقع — التقسيم العشوائي يسرّب المستقبل ويعطي دقّة كاذبة.
"""
import sqlite3
import json
import math
import os
import sys

DB = "/opt/whalex/ml_training.db"
OUT = "/opt/whalex/models/futures_model.json"

NUM_FEATS = ["score", "confidence", "range_pos", "rsi", "stoch_k", "stoch_d",
             "macd_hist", "funding", "oi_change", "hawk_modifier",
             "volume_ratio", "key_strat_count"]
CAT_FEATS = ["direction", "grade", "tier", "regime", "btc_trend", "hawk_phase"]


def load():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(
        "SELECT * FROM training_signals WHERE result IN ('win','loss') "
        "AND pnl_pct IS NOT NULL ORDER BY timestamp ASC")]
    con.close()
    return rows


def encode(rows):
    """يبني مصفوفة الميزات + قاموس التشفير."""
    cats = {f: sorted({str(r.get(f) or "?") for r in rows}) for f in CAT_FEATS}
    X, y, meta = [], [], []
    for r in rows:
        v = []
        for f in NUM_FEATS:
            try:
                v.append(float(r.get(f) or 0))
            except Exception:
                v.append(0.0)
        for f in CAT_FEATS:
            val = str(r.get(f) or "?")
            for opt in cats[f]:
                v.append(1.0 if val == opt else 0.0)
        X.append(v)
        y.append(1 if r["result"] == "win" else 0)
        meta.append({"symbol": r["symbol"], "pnl": r["pnl_pct"], "ts": r["timestamp"]})
    names = list(NUM_FEATS) + [f"{f}={o}" for f in CAT_FEATS for o in cats[f]]
    return X, y, meta, names, cats


def standardize(X, mu=None, sd=None):
    n = len(X[0])
    if mu is None:
        mu = [sum(r[i] for r in X) / len(X) for i in range(n)]
        sd = []
        for i in range(n):
            var = sum((r[i] - mu[i]) ** 2 for r in X) / max(1, len(X) - 1)
            sd.append(math.sqrt(var) or 1.0)
    Z = [[(r[i] - mu[i]) / sd[i] for i in range(n)] for r in X]
    return Z, mu, sd


def logistic_fit(X, y, epochs=400, lr=0.08, l2=0.01):
    n = len(X[0])
    w = [0.0] * n
    b = 0.0
    m = len(X)
    for _ in range(epochs):
        gw = [0.0] * n
        gb = 0.0
        for xi, yi in zip(X, y):
            z = b + sum(w[j] * xi[j] for j in range(n))
            p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            e = p - yi
            gb += e
            for j in range(n):
                gw[j] += e * xi[j]
        b -= lr * gb / m
        for j in range(n):
            w[j] -= lr * (gw[j] / m + l2 * w[j])
    return w, b


def predict(w, b, x):
    z = b + sum(w[j] * x[j] for j in range(len(w)))
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def report(y_true, probs, meta, thr=0.5):
    tp = sum(1 for t, p in zip(y_true, probs) if t == 1 and p >= thr)
    fp = sum(1 for t, p in zip(y_true, probs) if t == 0 and p >= thr)
    tn = sum(1 for t, p in zip(y_true, probs) if t == 0 and p < thr)
    fn = sum(1 for t, p in zip(y_true, probs) if t == 1 and p < thr)
    total = len(y_true) or 1
    acc = (tp + tn) / total * 100
    prec = tp / (tp + fp) * 100 if (tp + fp) else 0
    rec = tp / (tp + fn) * 100 if (tp + fn) else 0
    base = sum(y_true) / total * 100
    # أثر النموذج على الربح: نأخذ فقط ما يقبله
    taken = [m["pnl"] for m, p in zip(meta, probs) if p >= thr]
    all_pnl = [m["pnl"] for m in meta]
    return {
        "عتبة": thr, "دقة": round(acc, 1), "الأساس (نسبة الفوز الطبيعية)": round(base, 1),
        "دقة القبول": round(prec, 1), "التغطية": round(rec, 1),
        "قَبِل": len(taken), "من": total,
        "صافي بلا نموذج": round(sum(all_pnl), 1),
        "صافي بالنموذج": round(sum(taken), 1),
        "مصفوفة": {"صح_رابح": tp, "خطأ_قَبِل_خاسر": fp, "صح_رفض_خاسر": tn, "خطأ_رفض_رابح": fn},
    }


def main():
    rows = load()
    print(f"═ البيانات: {len(rows)} نتيجة مكتملة")
    if len(rows) < 200:
        print("  غير كافية للتدريب"); return
    X, y, meta, names, cats = encode(rows)
    cut = int(len(X) * 0.8)
    Xtr, ytr = X[:cut], y[:cut]
    Xte, yte, mte = X[cut:], y[cut:], meta[cut:]
    print(f"  تدريب {len(Xtr)} | اختبار {len(Xte)} (تقسيم زمنيّ)")
    print(f"  نسبة الفوز في التدريب: {sum(ytr)/len(ytr)*100:.1f}% | في الاختبار: {sum(yte)/len(yte)*100:.1f}%")
    print()

    Ztr, mu, sd = standardize(Xtr)
    Zte, _, _ = standardize(Xte, mu, sd)

    used = "logistic (بلا تبعيات)"
    probs = None
    try:
        from sklearn.ensemble import GradientBoostingClassifier
        clf = GradientBoostingClassifier(n_estimators=120, max_depth=3,
                                         learning_rate=0.06, random_state=42)
        clf.fit(Xtr, ytr)
        probs = [p[1] for p in clf.predict_proba(Xte)]
        used = "GradientBoosting (sklearn)"
        imp = sorted(zip(names, clf.feature_importances_), key=lambda x: -x[1])[:10]
    except Exception:
        w, b = logistic_fit(Ztr, ytr)
        probs = [predict(w, b, x) for x in Zte]
        imp = sorted(zip(names, [abs(v) for v in w]), key=lambda x: -x[1])[:10]

    print(f"═ النموذج: {used}")
    print()
    print("═ الأداء على بيانات لم يرها:")
    for thr in (0.45, 0.5, 0.55, 0.6):
        r = report(yte, probs, mte, thr)
        print(f"  عتبة {thr}: دقة {r['دقة']}% | دقة القبول {r['دقة القبول']}% "
              f"(الأساس {r['الأساس (نسبة الفوز الطبيعية)']}%) | قَبِل {r['قَبِل']}/{r['من']} | "
              f"صافي {r['صافي بالنموذج']:+.1f}% مقابل {r['صافي بلا نموذج']:+.1f}% بلا نموذج")
    print()
    print("═ أهم الميزات:")
    for n_, v in imp:
        print(f"  {n_:24} {v:.4f}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"model": used, "features": names, "cats": cats,
                   "mu": mu, "sd": sd, "trained_on": len(Xtr)}, f, ensure_ascii=False)
    print()
    print(f"✅ التقرير أُنجز. النموذج بلا سلطة — لم يُربط بأي قرار.")


if __name__ == "__main__":
    main()
