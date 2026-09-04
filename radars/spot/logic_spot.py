"""🪙🧠 منطق السبوت — مساران مستقلّان لا يمنع أحدهما الآخر.

القديم كان يطلب معاً: ترنداً صاعداً + سعراً في أدنى ربع النطاق — وهما متناقضان.
الجديد يقرأ حالة كل عملة ثم يُطلق مسارها:
  ① القاع    — للمتذبذب والهابط المستقرّ
  ② الارتداد — للصاعد: شراء التصحيح نحو الدعم
  ③ الاختراق — كسر قمّة بحجم مؤكَّد
"""
import logging
log = logging.getLogger("spot_logic")
MIN_SCORE = 7.0
GRADE_A = 8.5

def sma(xs, n):
    if len(xs) < n: return sum(xs)/len(xs) if xs else 0.0
    return sum(xs[-n:])/n

def rsi(closes, period=14):
    if len(closes) < period+1: return 50.0
    g = l = 0.0
    for i in range(-period, 0):
        d = closes[i]-closes[i-1]
        if d >= 0: g += d
        else: l -= d
    if l == 0: return 100.0
    rs = (g/period)/(l/period)
    return 100-(100/(1+rs))

def atr_pct(highs, lows, closes, n=14):
    if len(closes) < n+1: return 3.0
    trs = []
    for i in range(-n, 0):
        trs.append(max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])))
    a = sum(trs)/len(trs); px = closes[-1] or 1
    return max(0.5, min(15.0, a/px*100))

def regime(closes, highs, lows) -> tuple:
    if len(closes) < 50: return "range", "بيانات قليلة"
    px = closes[-1]; m20, m50 = sma(closes,20), sma(closes,50)
    l1,l2,l3 = min(lows[-30:-20]), min(lows[-20:-10]), min(lows[-10:])
    h1,h2,h3 = max(highs[-30:-20]), max(highs[-20:-10]), max(highs[-10:])
    higher_lows = l3 >= l2*0.995 and l2 >= l1*0.995
    higher_highs = h3 >= h2*0.995
    if px > m20 and m20 >= m50 and (higher_lows or higher_highs):
        return "up", "صاعد"
    if l3 < l2 < l1 and h3 < h2 and px < m20 < m50:
        return "down", "هابط"
    return "range", "متذبذب"

def path_dip(closes, highs, lows, vols, tbuys, book):
    px = closes[-1]; pk, lo = max(highs), min(lows); rng = pk-lo
    if rng <= 0: return 0.0, [], {}
    pos = (px-lo)/rng
    if pos > 0.40: return 0.0, [], {}
    if min(lows[-6:]) < lo*0.982: return 0.0, [], {}
    r = rsi(closes)
    v8, t8 = sum(vols[-8:]), sum(tbuys[-8:])
    taker = (t8/v8) if v8 > 0 else 0.0
    v_avg = sum(vols[-48:-8])/40 if len(vols) >= 48 else max(1e-9, sum(vols[:-8])/max(1,len(vols)-8))
    v_infl = (v8/8)/v_avg if v_avg > 0 else 0.0
    pts, why = 0.0, []
    if pos <= 0.20: pts += 2.0; why.append(f"قاع {pos*100:.0f}%")
    elif pos <= 0.32: pts += 1.4; why.append(f"قاع {pos*100:.0f}%")
    else: pts += 0.7
    if 30 <= r <= 55: pts += 2.2; why.append(f"RSI {r:.0f}")
    elif 25 <= r < 30: pts += 1.6; why.append(f"مُشبع {r:.0f}")
    elif 55 < r <= 65: pts += 1.0; why.append(f"RSI {r:.0f}")
    if taker >= 0.58: pts += 2.2; why.append(f"ضغط شراء {taker*100:.0f}%")
    elif taker >= 0.50: pts += 1.3; why.append(f"شراء {taker*100:.0f}%")
    if v_infl >= 2.0: pts += 1.8; why.append(f"حجم ×{v_infl:.1f}")
    elif v_infl >= 1.3: pts += 1.1; why.append(f"حجم ×{v_infl:.1f}")
    if px > sum(closes[-6:-1])/5: pts += 1.0; why.append("شرارة ارتداد")
    if book.get("wall"): pts += 1.0; why.append("جدار شراء")
    if book.get("imb",0) >= 0.10: pts += 0.8; why.append(f"كتاب داعم {book['imb']*100:+.0f}%")
    elif book.get("imb",0) <= -0.30: pts -= 1.5; why.append("بائعون في الكتاب")
    return pts, why, {"rsi":r,"taker":taker,"v_infl":v_infl,"range_pos":pos,"low":lo,"peak":pk}

def path_pullback(closes, highs, lows, vols, tbuys, book):
    if len(closes) < 30: return 0.0, [], {}
    px = closes[-1]; m20 = sma(closes,20)
    if m20 <= 0: return 0.0, [], {}
    recent_peak = max(highs[-14:])
    dd = (recent_peak-px)/recent_peak*100 if recent_peak > 0 else 0
    dist_ma = (px-m20)/m20*100
    if dd < 0.8 or dd > 16.0: return 0.0, [], {}
    if dist_ma < -6.0: return 0.0, [], {}
    r = rsi(closes)
    v8, t8 = sum(vols[-8:]), sum(tbuys[-8:])
    taker = (t8/v8) if v8 > 0 else 0.0
    v_avg = sum(vols[-48:-8])/40 if len(vols) >= 48 else max(1e-9, sum(vols[:-8])/max(1,len(vols)-8))
    v_infl = (v8/8)/v_avg if v_avg > 0 else 0.0
    pts, why = 0.0, []
    if 3.0 <= dd <= 10.0: pts += 2.2; why.append(f"تصحيح {dd:.1f}%")
    elif dd < 3.0: pts += 1.6; why.append(f"استراحة {dd:.1f}%")
    else: pts += 1.2; why.append(f"تصحيح {dd:.1f}%")
    if -3.0 <= dist_ma <= 3.0: pts += 2.0; why.append("عند متوسط 20")
    elif dist_ma > 3.0: pts += 0.8; why.append("فوق المتوسط")
    else: pts += 1.2; why.append("لمس المتوسط")
    if 40 <= r <= 62: pts += 2.0; why.append(f"RSI مُبرَّد {r:.0f}")
    elif 62 < r <= 70: pts += 1.0; why.append(f"RSI {r:.0f}")
    elif r < 40: pts += 1.4; why.append(f"RSI {r:.0f}")
    if taker >= 0.55: pts += 1.8; why.append(f"عودة المشترين {taker*100:.0f}%")
    elif taker >= 0.48: pts += 1.0; why.append(f"شراء {taker*100:.0f}%")
    if px > closes[-2] and closes[-2] <= closes[-3]: pts += 1.3; why.append("انعكاس مؤكَّد")
    elif px > closes[-2]: pts += 0.7; why.append("شمعة خضراء")
    if v_infl >= 1.2: pts += 0.9; why.append(f"حجم ×{v_infl:.1f}")
    if book.get("imb",0) >= 0.05: pts += 0.8; why.append("كتاب داعم")
    elif book.get("imb",0) <= -0.30: pts -= 1.5; why.append("بائعون في الكتاب")
    return pts, why, {"rsi":r,"taker":taker,"v_infl":v_infl,"drawdown":dd,"ma20":m20,"peak":recent_peak}

def path_breakout(closes, highs, lows, vols, tbuys, book):
    if len(closes) < 30: return 0.0, [], {}
    px = closes[-1]
    prior_high = max(closes[-21:-1])
    if px < prior_high: return 0.0, [], {}
    ext = (px-prior_high)/prior_high*100
    if ext > 6.0: return 0.0, [], {}
    v8, t8 = sum(vols[-8:]), sum(tbuys[-8:])
    taker = (t8/v8) if v8 > 0 else 0.0
    v_avg = sum(vols[-48:-8])/40 if len(vols) >= 48 else max(1e-9, sum(vols[:-8])/max(1,len(vols)-8))
    v_infl = (v8/8)/v_avg if v_avg > 0 else 0.0
    r = rsi(closes)
    if v_infl < 1.4: return 0.0, [], {}
    pts, why = 0.0, []
    pts += 2.4; why.append(f"كسر قمّة +{ext:.1f}%")
    if v_infl >= 2.5: pts += 2.2; why.append(f"حجم ×{v_infl:.1f}")
    else: pts += 1.4; why.append(f"حجم ×{v_infl:.1f}")
    if taker >= 0.58: pts += 1.8; why.append(f"ضغط شراء {taker*100:.0f}%")
    elif taker >= 0.50: pts += 1.0; why.append(f"شراء {taker*100:.0f}%")
    if r <= 72: pts += 1.2; why.append(f"RSI {r:.0f}")
    else: pts -= 0.8; why.append(f"RSI مرتفع {r:.0f}")
    if book.get("imb",0) >= 0.05: pts += 0.8; why.append("كتاب داعم")
    return pts, why, {"rsi":r,"taker":taker,"v_infl":v_infl,"breakout_ext":ext,"prior_high":prior_high}

def evaluate(closes, highs, lows, vols, tbuys, book=None) -> dict:
    book = book or {}
    if len(closes) < 50: return {"ok": False, "reason": "بيانات قليلة"}
    # 📐 مرشّح المعايير العالمية — معكوساً كما قاسه سجلّنا.
    #   الكتاب يقول اشترِ المُشبَع بيعاً، وسجلّنا يقول إنه يستمرّ
    #   في الموت: z<-1.5 فوز 26% · بولنجر تحت السفليّ 25% ·
    #   RSI-2<10 فوز 25% · RSI-14<30 فوز 23%.
    #   والأثر المقيس على 199 إشارة: -31.3% → +7.1% وفوز 43% → 51%
    #   وموجب في النصفين (+14 و +25).
    try:
        from radars.spot.std_filter import check as _std
        _ok, _sw = _std(closes)
        if not _ok:
            return {"ok": False, "reason": _sw}
    except Exception as _se:
        log.debug("مرشّح المعايير: %s", _se)

    reg, reg_why = regime(closes, highs, lows)
    px = closes[-1]; atr = atr_pct(highs, lows, closes)
    cands = []
    # 🚫 صيد القاع في سوق هابط أو متذبذب = مصيدة. مقيس على 300 صفقة:
    #      dip / down   15 صفقة | فوز 33% | -35.2%
    #      dip / range  35 صفقة | فوز 31% | -16.0%
    #      dip / up      4 صفقة | فوز 50% |  +2.9%
    #      pullback/up 219 صفقة | فوز 29% | +12.7%
    #    واستبعاد dip من الحالتين يوفّر 48.3 نقطة. فالقاع لا يُشترى
    #    إلا في اتجاه صاعد مؤكَّد، حيث الهبوط تصحيح لا انهيار.
    if reg in ("range", "down"):
        pass
    if reg == "up":
        p,w,m = path_pullback(closes,highs,lows,vols,tbuys,book)
        if p > 0: cands.append(("pullback",p,w,m))
        p,w,m = path_breakout(closes,highs,lows,vols,tbuys,book)
        if p > 0: cands.append(("breakout",p,w,m))
        p,w,m = path_dip(closes,highs,lows,vols,tbuys,book)
        if p > 0: cands.append(("dip",p,w,m))
    if reg == "range":
        p,w,m = path_breakout(closes,highs,lows,vols,tbuys,book)
        if p > 0: cands.append(("breakout",p,w,m))
    if not cands:
        return {"ok": False, "regime": reg, "reason": f"{reg_why} — لا مسار منطبق"}
    _r_now = rsi(closes)
    if _r_now >= 85:
        return {"ok": False, "regime": reg, "reason": f"محموم جداً RSI {_r_now:.0f}"}
    if _r_now >= 76:
        cands = [x for x in cands if x[0] != "breakout"]
        if not cands:
            return {"ok": False, "regime": reg, "reason": f"اختراق محموم RSI {_r_now:.0f}"}
    cands.sort(key=lambda x: -x[1])
    path, pts, why, meta = cands[0]
    if pts < MIN_SCORE:
        return {"ok": False, "regime": reg, "path": path, "score": round(pts,2),
                "reason": f"نقاط {pts:.1f} < {MIN_SCORE}"}
    if path == "dip":
        sl_pct = max(2.0, min(6.0, atr*1.3)); tps = (atr*2.0, atr*3.6, atr*6.0)
        sl = max(meta.get("low", px*0.97)*0.985, px*(1-sl_pct/100))
    elif path == "pullback":
        sl_pct = max(1.8, min(5.0, atr*1.1)); tps = (atr*1.5, atr*2.8, atr*4.5)
        sl = max(meta.get("ma20", px*0.98)*0.975, px*(1-sl_pct/100))
    else:
        sl_pct = max(2.0, min(5.5, atr*1.2)); tps = (atr*1.8, atr*3.2, atr*5.2)
        sl = max(meta.get("prior_high", px*0.98)*0.985, px*(1-sl_pct/100))
    tp1 = px*(1+max(1.5, min(9.0, tps[0]))/100)
    tp2 = px*(1+max(3.0, min(18.0, tps[1]))/100)
    tp3 = px*(1+max(5.0, min(30.0, tps[2]))/100)
    label = {"dip":"🪙 صيد القاع","pullback":"📈 ارتداد في اتجاه صاعد","breakout":"🚀 اختراق مؤكَّد"}[path]
    conf = min(94, 58+(pts-MIN_SCORE)*7)
    return {"ok": True, "path": path, "label": label, "regime": reg,
            "score": round(pts,2), "grade": "A" if pts >= GRADE_A else "B",
            "confidence": round(conf,1), "why": why, "meta": meta,
            "entry": px, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
            "atr_pct": round(atr,2)}
