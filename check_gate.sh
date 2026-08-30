#!/bin/bash
cd /opt/whalex && python3 -c "
import sqlite3, time
c=sqlite3.connect('/opt/whalex/db/whalex.db'); c.row_factory=sqlite3.Row
T=1787966000
r=[x for x in c.execute(f'SELECT * FROM spot_results WHERE ts>{T}')]
print(f'═══ بعد بوّابة الجودة: {len(r)} صفقة ═══')
if len(r)>=10:
    w=len([x for x in r if x['pnl_pct']>0])
    net=sum(x['pnl_pct'] for x in r)
    print(f'  فوز {w*100//len(r)}% | صافي {net:+.1f}% | متوسط {net/len(r):+.2f}%')
    print()
    print('  المقارنة قبلها: 325 صفقة | فوز 29% | -90.0% | متوسط -0.28%')
    print()
    from collections import Counter
    print('  الأسباب:', dict(Counter(x['reason'] or '?' for x in r)))
    fast=[x for x in r if x['opened_ts'] and (x['ts']-x['opened_ts'])/3600<2]
    if fast:
        fw=len([x for x in fast if x['pnl_pct']>0])
        print(f'  السريعة (<2س): {len(fast)} | فوز {fw*100//len(fast)}% | صافي {sum(x[\"pnl_pct\"] for x in fast):+.1f}%')
        print('  (كانت: 189 صفقة | فوز 21% | -92.9%)')
else:
    print(f'  العيّنة صغيرة — ننتظر 10 صفقات على الأقلّ')
n=c.execute(\"SELECT COUNT(*) FROM signals WHERE radar_type='spot' AND is_active=1\").fetchone()[0]
print()
print(f'  المفتوحة الآن: {n}')
"
