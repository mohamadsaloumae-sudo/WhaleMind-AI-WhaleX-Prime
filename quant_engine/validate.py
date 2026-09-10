"""🔬 تحقق منقى بحظر — لوبيز دي برادو (فصلا 7 و12).

المشكلة: التحقق العادي يفترض استقلال الصفوف. والتسميات المالية تُبنى
على نوافذ زمنية متداخلة، فالشفل العادي يسرب جواب الغد الى التدريب
ويضخم الدقة بهدوء. مقيس 10 سبتمبر: نموذجنا يتدرب على كل شيء بلا
اي اختبار خارجي — فالرقم الذي نراه حفظ لا تعلم.

  purge  : نحذف من التدريب كل صف تتداخل نافذته مع نافذة الاختبار
  embargo: نحذف صفوفا بعد الاختبار مباشرة (الارتباط التسلسلي)

مختبر: تسريب صفر · بيانات فيها اشارة AUC 0.674 · ضجيج محض 0.4995
"""
import math


def purged_folds(rows, n_splits=5, embargo_pct=0.02):
    n = len(rows)
    if n < n_splits * 10:
        return []
    idx = list(range(n))
    fold_sz = n // n_splits
    emb = max(1, int(n * embargo_pct))
    out = []
    for k in range(n_splits):
        lo = k * fold_sz
        hi = n if k == n_splits - 1 else (k + 1) * fold_sz
        test = idx[lo:hi]
        if not test:
            continue
        t_start = min(rows[i]["t0"] for i in test)
        t_end = max(rows[i]["t1"] for i in test)
        train = []
        for i in idx:
            if lo <= i < hi:
                continue
            r = rows[i]
            if r["t1"] >= t_start and r["t0"] <= t_end:
                continue
            if hi <= i < hi + emb:
                continue
            train.append(i)
        if len(train) >= 30 and len(test) >= 10:
            out.append((train, test))
    return out


def fit_weights(rows, extract, min_samples=8):
    W = sum(1 for r in rows if r["outcome"] == 1)
    L = len(rows) - W
    if W < 5 or L < 5:
        return None
    counts = {}
    for r in rows:
        ok = r["outcome"] == 1
        for name, val in extract(r).items():
            d = counts.setdefault(name, {}).setdefault(val, {"w": 0, "l": 0})
            d["w" if ok else "l"] += 1
    weights = {}
    for name, vals in counts.items():
        K = max(len(vals), 2)
        for val, d in vals.items():
            nn = d["w"] + d["l"]
            if nn < min_samples:
                continue
            w = math.log((d["w"] + 1) / (W + K)) - math.log((d["l"] + 1) / (L + K))
            weights.setdefault(name, {})[val] = {"w": round(w, 4), "n": nn}
    return {"prior": math.log(W / max(1, L)), "weights": weights}


def predict(model, row, extract):
    z = model["prior"]
    for name, val in extract(row).items():
        info = model["weights"].get(name, {}).get(val)
        if info:
            z += info["w"]
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def auc(pairs):
    pos = [p for p, y in pairs if y == 1]
    neg = [p for p, y in pairs if y == 0]
    if not pos or not neg:
        return 0.5
    win = ties = 0
    for a in pos:
        for b in neg:
            if a > b:
                win += 1
            elif a == b:
                ties += 1
    return (win + 0.5 * ties) / (len(pos) * len(neg))


def evaluate(rows, extract, n_splits=5, embargo_pct=0.02, thr=0.55):
    folds = purged_folds(rows, n_splits, embargo_pct)
    if not folds:
        return {"ok": False, "why": "عينات غير كافية"}
    all_pairs, accs, taken = [], [], []
    for tr, te in folds:
        m = fit_weights([rows[i] for i in tr], extract)
        if not m:
            continue
        pairs = [(predict(m, rows[i], extract), rows[i]["outcome"]) for i in te]
        all_pairs += pairs
        accs.append(sum(1 for p, y in pairs if (p >= 0.5) == (y == 1)) / len(pairs))
        sel = [(p, y) for p, y in pairs if p >= thr]
        if sel:
            taken.append(sum(1 for _, y in sel if y == 1) / len(sel))
    if not all_pairs:
        return {"ok": False, "why": "لا طيّات صالحة"}
    base = sum(1 for _, y in all_pairs if y == 1) / len(all_pairs)
    return {"ok": True, "folds": len(accs), "n_test": len(all_pairs),
            "auc": round(auc(all_pairs), 4),
            "acc": round(sum(accs) / len(accs), 4),
            "base_wr": round(base, 4),
            "wr_at_thr": round(sum(taken) / len(taken), 4) if taken else None,
            "lift": round((sum(taken) / len(taken) - base), 4) if taken else None}
