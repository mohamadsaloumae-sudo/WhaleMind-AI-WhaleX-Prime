"""🪙🧠 تدريب دماغ السبوت — يومياً من البيانات الحيّة.

بلا هذه الحلقة يبقى النموذج على 446 صفقة قديمة إلى الأبد،
ولا يتعلّم من أي صفقة جديدة — وهذا ما قتل الدماغ الأوّل.
"""
import asyncio
import json
import logging
import math
import os
import sqlite3
import time

log = logging.getLogger("spot_trainer")
DB = "/opt/whalex/db/whalex.db"
MODEL = "/opt/whalex/spot_model.json"
EVERY = 21600           # كل ست ساعات
MIN_ROWS = 120
OFF_FLAG = "/opt/whalex/db/spot_trainer.off"

BINS = {
 "zscore":   [(-99,-1.0,"<-1.0"),(-1.0,-0.4,"-1..-0.4"),(-0.4,0.4,"-0.4..0.4"),(0.4,99,">0.4")],
 "bb_pos":   [(-99,0.2,"<0.2"),(0.2,0.45,"0.2-0.45"),(0.45,0.7,"0.45-0.7"),(0.7,99,">0.7")],
 "rsi2":     [(0,15,"<15"),(15,50,"15-50"),(50,85,"50-85"),(85,101,">85")],
 "rsi14":    [(0,35,"<35"),(35,48,"35-48"),(48,60,"48-60"),(60,101,">60")],
 "atr_pct":  [(0,1.5,"<1.5"),(1.5,3,"1.5-3"),(3,6,"3-6"),(6,99,">6")],
 "taker":    [(0,0.45,"<0.45"),(0.45,0.55,"0.45-0.55"),(0.55,0.65,"0.55-0.65"),(0.65,9,">0.65")],
 "vol_infl": [(0,1.2,"<1.2"),(1.2,2,"1.2-2"),(2,4,"2-4"),(4,999,">4")],
 "range_pos":[(0,0.15,"<0.15"),(0.15,0.35,"0.15-0.35"),(0.35,0.6,"0.35-0.6"),(0.6,9,">0.6")],
 "hour_utc": [(0,6,"00-06"),(6,12,"06-12"),(12,18,"12-18"),(18,24,"18-24")],
}


def train() -> dict:
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    R = [dict(x) for x in c.execute(
        "SELECT * FROM spot_train_v2 WHERE outcome IS NOT NULL")]
    c.close()
    n = len(R)
    if n < MIN_ROWS:
        return {"ok": False, "n": n}
    base = sum(x["outcome"] for x in R) / n * 100
    pb = max(0.02, min(0.98, base / 100))
    W = {}
    for name, bins in BINS.items():
        g = {}
        for x in R:
            v = x.get(name)
            if v is None: continue
            for lo, hi, lbl in bins:
                if lo <= v < hi:
                    g.setdefault(lbl, []).append(x["outcome"]); break
        ws = {}
        for b, v in g.items():
            if len(v) < 12: continue
            p = max(0.02, min(0.98, sum(v) / len(v)))
            ws[b] = {"w": round(math.log(p/(1-p)) - math.log(pb/(1-pb)), 4),
                     "n": len(v), "wr": round(sum(v)/len(v)*100, 1)}
        if ws: W[name] = ws
    # المسار
    gp = {}
    for x in R:
        p = str(x.get("path") or "")
        if p: gp.setdefault(p, []).append(x["outcome"])
    ws = {}
    for b, v in gp.items():
        if len(v) < 12: continue
        p = max(0.02, min(0.98, sum(v)/len(v)))
        ws[b] = {"w": round(math.log(p/(1-p)) - math.log(pb/(1-pb)), 4),
                 "n": len(v), "wr": round(sum(v)/len(v)*100, 1)}
    if ws: W["path"] = ws
    m = {"trained_at": int(time.time()), "samples": n,
         "base_wr": round(base, 1),
         "prior": round(math.log(pb/(1-pb)), 4), "weights": W}
    json.dump(m, open(MODEL, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return {"ok": True, "n": n, "base": round(base, 1), "feats": len(W)}


async def train_loop():
    await asyncio.sleep(300)
    while True:
        try:
            if not os.path.exists(OFF_FLAG):
                r = await asyncio.to_thread(train)
                if r.get("ok"):
                    log.info("🪙🧠 تدرّب الدماغ: %d صفقة | فوز أساسيّ %.1f%% "
                             "| %d حقل", r["n"], r["base"], r["feats"])
                else:
                    log.info("🪙🧠 بيانات قليلة: %d (نحتاج %d)",
                             r.get("n", 0), MIN_ROWS)
        except Exception as e:
            log.error("تدريب السبوت: %s", e)
        await asyncio.sleep(EVERY)
