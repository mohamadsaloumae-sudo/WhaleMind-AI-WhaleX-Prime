"""🌐 قياس بوابة الأنظمة الظلّية — هل قراراتها صحيحة؟

يقرأ قرارات الظلّ من السجلّ، يطابقها بالنتائج الفعلية،
ويُظهر كم كنّا سنوفّر (أو نخسر) لو فعّلناها.
"""
import re
import subprocess
import sqlite3
from datetime import datetime, timezone

RX = re.compile(r"^(\w+)\s+(\d+)\s+(\d{2}:\d{2}:\d{2}).*?"
                r"🌐👁️ ظل — كنّا سنمنع\s+(\S+)\s+(\S+):\s*(.*)$")
MON = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
       "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
DB = "/opt/whalex/ml_training.db"

out = subprocess.run(
    ["journalctl","-u","whalex","--since","7 days ago","--no-pager"],
    capture_output=True, text=True).stdout.splitlines()

recs = []
for ln in out:
    m = RX.match(ln.strip())
    if not m:
        continue
    mon, day, hms, sym, d, why = m.groups()
    if mon not in MON:
        continue
    h, mi, s = hms.split(":")
    ts = int(datetime(2026, MON[mon], int(day), int(h), int(mi), int(s),
                      tzinfo=timezone.utc).timestamp())
    recs.append({"ts": ts, "symbol": sym, "direction": d.strip(),
                 "why": why.strip()})

print("قرارات الظلّ في السجلّ: %d\n" % len(recs))
if not recs:
    raise SystemExit("لا قرارات — البوابة لم تمنع شيئاً أو السجلّ دُوِّر.")

con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
hit = []
for r in recs:
    row = con.execute(
        "SELECT tier, pnl_pct, leverage FROM training_signals "
        "WHERE symbol=? AND direction=? AND ABS(timestamp-?)<=180 "
        "AND close_reason IN ('tactical_exit','sl_hit') "
        "ORDER BY ABS(timestamp-?) LIMIT 1",
        (r["symbol"], r["direction"], r["ts"], r["ts"])).fetchone()
    if row and row["pnl_pct"] is not None:
        d = dict(row); d["why"] = r["why"]; hit.append(d)
con.close()

print("طُوبقت بنتائج فعلية: %d\n" % len(hit))
if not hit:
    raise SystemExit("لا مطابقات.")

net = [x["pnl_pct"] - 0.10 * (x["leverage"] or 5) for x in hit]
w = sum(1 for v in net if v > 0)
print("=== لو فعّلنا البوابة ===\n")
print("  الصفقات الممنوعة : %d" % len(hit))
print("  منها رابحة       : %d (%.0f%%)" % (w, w/len(hit)*100))
print("  متوسّطها         : %+.2f%%" % (sum(net)/len(net)))
print("  مجموعها          : %+.0f نقطة" % sum(net))
print()
if sum(net) < 0:
    print("  ✅ التفعيل يوفّر %.0f نقطة" % abs(sum(net)))
else:
    print("  ❌ التفعيل يخسر %.0f نقطة — لا نفعّلها" % sum(net))

by = {}
for x, v in zip(hit, net):
    by.setdefault(x["tier"] or "?", []).append(v)
print("\n=== حسب الرادار ===\n")
for t, v in sorted(by.items(), key=lambda z: sum(z[1])):
    print("  %-5s %3d صفقة · متوسّط %+6.2f%% · مجموع %+7.0f" %
          (t, len(v), sum(v)/len(v), sum(v)))
