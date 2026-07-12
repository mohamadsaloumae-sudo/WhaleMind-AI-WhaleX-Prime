"""
🔬 Backtest — جرّب أي فلتر على صفقاتك التاريخية قبل تطبيقه في الحيّ.
يحوّل ضبط النظام من حدس إلى علم: "لو طبّقنا الشرط X، ماذا كانت النتيجة؟"

أمثلة:
  python -m quant_engine.backtest "tier != 'B'"
  python -m quant_engine.backtest "direction == 'SHORT'"
  python -m quant_engine.backtest "rsi >= 50"
  python -m quant_engine.backtest "hour_utc >= 6 and hour_utc < 12"
  python -m quant_engine.backtest "confidence >= 85 and grade == 'S'"
الشرط = تعبير Python على حقول الصفقة. الصفقات التي يصدق عليها = "نُبقيها"،
والباقي = "نرفضها" — فنرى هل الفلتر يرفع النجاح ويرفض الخاسرات دون التضحية بالرابحات.
"""
import sqlite3, sys, time

DB = "/opt/whalex/ml_training.db"

def _rows():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM training_signals WHERE outcome IS NOT NULL").fetchall()]
    conn.close()
    for r in rows:  # حقول مشتقة
        ts = r.get("timestamp") or 0
        r["hour_utc"] = (int(ts) % 86400) // 3600 if ts else -1
    return rows

def _stat(group):
    n = len(group)
    if not n:
        return (0, 0.0, 0.0)
    w = sum(1 for x in group if x.get("outcome") == 1)
    pnl = sum((x.get("pnl_pct") or 0) for x in group)
    return (n, w / n * 100, pnl / n)

def backtest(condition: str) -> str:
    rows = _rows()
    bn, bwr, bpnl = _stat(rows)
    keep, drop = [], []
    errs = 0
    for r in rows:
        try:
            ok = bool(eval(condition, {"__builtins__": {}}, dict(r)))
        except Exception:
            ok = True; errs += 1
        (keep if ok else drop).append(r)
    kn, kwr, kpnl = _stat(keep)
    dn, dwr, dpnl = _stat(drop)

    L = []
    L.append(f"🔬 Backtest: {condition}")
    L.append("═" * 54)
    L.append(f"الأساس (كل الصفقات): {bn} | نجاح {bwr:.1f}% | متوسط pnl {bpnl:+.2f}%")
    L.append("─" * 54)
    L.append(f"✅ نُبقيها: {kn} صفقة | نجاح {kwr:.1f}% | متوسط pnl {kpnl:+.2f}%")
    L.append(f"❌ نرفضها: {dn} صفقة | نجاح {dwr:.1f}% | متوسط pnl {dpnl:+.2f}%")
    L.append("═" * 54)
    # الحكم
    if kn == 0:
        L.append("⚠️ الشرط رفض كل الصفقات — لا جدوى.")
    else:
        delta = kwr - bwr
        verdict = "✅ يحسّن" if delta > 1 else "➖ لا يغيّر" if abs(delta) <= 1 else "❌ يضرّ"
        L.append(f"الحكم: {verdict} النجاح ({bwr:.1f}% → {kwr:.1f}%، {delta:+.1f} نقطة)")
        if dn:
            lost_winners = sum(1 for x in drop if x.get("outcome") == 1)
            L.append(f"       رفضنا {dn} صفقة — منها {lost_winners} رابحة "
                     f"({lost_winners/dn*100:.0f}% من المرفوض كان سيربح)")
    if errs:
        L.append(f"⚠️ {errs} صفقة تعذّر تقييمها (حقل مفقود) — عُدّت مُبقاة.")
    return "\n".join(L)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(0)
    print(backtest(sys.argv[1]))
