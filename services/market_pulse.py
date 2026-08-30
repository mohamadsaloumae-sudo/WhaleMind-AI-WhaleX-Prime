"""🌡️ نبض السوق — مستشار يُخبر ولا يمنع.

المشكلة المقيسة: حقول حالة السوق ميّتة في السجلّ — regime فارغ في
1,093 من 1,200 صفقة، و btc_trend قيمته NEUTRAL دائماً، و hawk_phase
فارغ كلّياً. فالنظام يتداول أعمى عن حالة السوق ولا نملك بيانات لقياس
أثرها.

ولاحظنا أن الصفقات التي فشل فيها قياس السوق (btc_trend فارغ) كانت
كارثية: 106 صفقة بفوز 18% و -135.2%.

وهذه الوحدة تقيس كل خمس دقائق وتُخزّن الحالة، فتصير لدينا بيانات
حقيقية نقيس عليها لاحقاً. ولا تمنع إشارة ولا تُعدّل قراراً — دورها
أن تُخبر فقط، حتى نتحقّق بالأرقام قبل أن نبني عليها.
"""
import asyncio
import logging
import os
import sqlite3
import time

log = logging.getLogger("market_pulse")
DB = "/opt/whalex/db/market_pulse.db"
EVERY = 300
OFF_FLAG = "/opt/whalex/db/market_pulse.off"

_state = {"ts": 0, "trend": "unknown", "vol": "unknown",
          "mkt_rsi": 50.0,
          "breadth": "unknown", "btc_1h": 0.0, "up_pct": 0,
          "vol_p90": 0.0}


def _init():
    try:
        c = sqlite3.connect(DB)
        c.execute("""CREATE TABLE IF NOT EXISTS pulse(
            ts INTEGER PRIMARY KEY, trend TEXT, vol TEXT, breadth TEXT,
            btc_5m REAL, btc_1h REAL, up_pct INTEGER, vol_med REAL,
            vol_p90 REAL)""")
        c.commit(); c.close()
    except Exception as e:
        log.error("تهيئة: %s", e)


def _measure() -> dict:
    import ccxt
    from services.ccxt_pool import get as _pool
    ex = _pool("binance", "swap", 20000)
    out = {}
    kl5 = ex.fetch_ohlcv("BTCUSDT", "5m", limit=12)
    kl1 = ex.fetch_ohlcv("BTCUSDT", "1h", limit=2)
    out["btc_5m"] = (float(kl5[-1][4]) - float(kl5[0][1])) / float(kl5[0][1]) * 100
    out["btc_1h"] = (float(kl1[-1][4]) - float(kl1[-1][1])) / float(kl1[-1][1]) * 100
    # 📉 إشباع السوق: متوسط RSI لأنشط العملات.
    #    مقيس على 3,704 صفقة: اللونج حين متوسط RSI للسوق دون 45
    #    أعطى 1,236 صفقة بفوز 48% و -289.4% — أكبر خسارة في النظام.
    #    والشورت في نفس الحالة ربح +169.6%. فالخطر أن نشتري القاع
    #    في سوق ما زال يهبط.
    try:
        out["mkt_rsi"] = _market_rsi(ex)
    except Exception as _re:
        log.debug("RSI السوق: %s", _re)
        out["mkt_rsi"] = 50.0

    tk = ex.fetch_tickers()
    ch = [float(v.get("percentage") or 0) for k, v in tk.items()
          if k.endswith("USDT:USDT") and v.get("percentage") is not None]
    ch.sort()
    n = len(ch) or 1
    out["up_pct"] = len([x for x in ch if x > 0]) * 100 // n
    out["vol_med"] = abs(ch[n // 2])
    out["vol_p90"] = abs(ch[int(n * 0.9)])
    h = out["btc_1h"]
    out["trend"] = ("down_hard" if h < -1.5 else "down" if h < -0.4 else
                    "up_hard" if h > 1.5 else "up" if h > 0.4 else "flat")
    out["vol"] = ("violent" if out["vol_p90"] > 12 else
                  "choppy" if out["vol_p90"] > 7 else "calm")
    out["breadth"] = ("buy" if out["up_pct"] > 60 else
                      "sell" if out["up_pct"] < 40 else "even")
    return out


def advice() -> dict:
    """توجيه الرادار حسب حالة السوق — أوزان لا أوامر.

    الرادار يقرأ هذا ويُعدّل ميزانه: يُخفّض عتبة الاتّجاه الموافق
    ويرفعها للمخالف. ولا يُمنَع شيء — الإشارة القوية تمرّ دائماً.

    مقيس: BTC هابط + إشارة لونج = 48 صفقة بفوز 45% و -39.8%،
    بينما العرضيّ + شورت = 383 صفقة بفوز 65% و +83.6%.
    """
    t = _state.get("trend", "unknown")
    v = _state.get("vol", "unknown")
    b = _state.get("breadth", "unknown")
    out = {"long_bias": 0.0, "short_bias": 0.0, "size_mult": 1.0,
           "note": "", "trend": t, "vol": v, "breadth": b}

    if t == "down_hard":
        out["long_bias"], out["short_bias"] = +1.0, -0.5
        out["note"] = "السوق يهبط بقوّة — ركّز على الشورت واحذر اللونج"
    elif t == "down":
        out["long_bias"], out["short_bias"] = +0.5, -0.25
        out["note"] = "السوق مائل للهبوط — الشورت أولى"
    elif t == "up_hard":
        out["long_bias"], out["short_bias"] = -0.5, +1.0
        out["note"] = "السوق يصعد بقوّة — ركّز على اللونج واحذر الشورت"
    elif t == "up":
        out["long_bias"], out["short_bias"] = -0.25, +0.5
        out["note"] = "السوق مائل للصعود — اللونج أولى"
    else:
        out["note"] = "السوق عرضيّ — تأنَّ ولا ترجيح لاتّجاه"

    # 📉 السوق مُشبَع بيعاً — اللونج خطر (السكّين الهابطة)
    _mr = float(_state.get("mkt_rsi") or 50)
    if _mr < 42:
        out["long_bias"] = 99.0        # منع فعليّ
        out["note"] = (f"السوق مُشبَع بيعاً (RSI {_mr:.0f}) — "
                       f"اللونج ممنوع، الشورت أولى")
    elif _mr < 46:
        out["long_bias"] += 0.5
        out["note"] += f" · ضعف عامّ (RSI {_mr:.0f}) — اللونج أشدّ"

    if v == "violent":
        out["size_mult"] = 0.6
        out["long_bias"] += 0.4
        out["short_bias"] += 0.4
        out["note"] += " · تقلّب عنيف: مبلغ أصغر وشروط أشدّ"
    elif v == "choppy":
        out["size_mult"] = 0.8
        out["note"] += " · تقلّب مرتفع"

    if b == "sell" and t in ("down", "down_hard"):
        out["short_bias"] -= 0.25
        out["note"] += " · اتّساع بيع يؤكّد الهبوط"
    elif b == "buy" and t in ("up", "up_hard"):
        out["long_bias"] -= 0.25
        out["note"] += " · اتّساع شراء يؤكّد الصعود"
    # حدّ أقصى ±1.0 — لا نُشدّد أكثر من نقطة كاملة
    if out["long_bias"] < 90:
        out["long_bias"] = max(-1.0, min(1.0, out["long_bias"]))
    out["short_bias"] = max(-1.0, min(1.0, out["short_bias"]))
    return out


def score_adjust(direction: str) -> float:
    """كم نُضيف لعتبة النقاط لهذا الاتّجاه؟ موجب = أشدّ."""
    try:
        a = advice()
        return float(a["long_bias"] if str(direction).upper() == "LONG"
                     else a["short_bias"])
    except Exception:
        return 0.0


def _market_rsi(ex, n: int = 30) -> float:
    """متوسط RSI لأنشط العملات — مقياس إشباع السوق."""
    import sqlite3 as _sq
    syms = []
    try:
        cn = _sq.connect("/opt/whalex/multi_universe.db")
        syms = [r[0] for r in cn.execute(
            "SELECT symbol FROM multi_universe WHERE exchange='binance' "
            "LIMIT ?", (n,))]
        cn.close()
    except Exception:
        pass
    if not syms:
        syms = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
    vals = []
    for sym in syms[:n]:
        try:
            kl = ex.fetch_ohlcv(sym, "15m", limit=30)
            cl = [float(k[4]) for k in kl]
            if len(cl) < 15:
                continue
            g = l = 0.0
            for i in range(-14, 0):
                d = cl[i] - cl[i - 1]
                if d > 0: g += d
                else: l -= d
            rs = (g / 14) / ((l / 14) or 1e-9)
            vals.append(100 - 100 / (1 + rs))
        except Exception:
            continue
    return round(sum(vals) / len(vals), 1) if vals else 50.0


def get_state() -> dict:
    """الحالة الحالية — للقراءة من أي رادار. لا تمنع شيئاً."""
    return dict(_state)


async def pulse_loop():
    _init()
    await asyncio.sleep(20)
    while True:
        try:
            if not os.path.exists(OFF_FLAG):
                m = await asyncio.to_thread(_measure)
                m["ts"] = int(time.time())
                _state.update(m)
                try:
                    c = sqlite3.connect(DB)
                    c.execute(
                        "INSERT OR REPLACE INTO pulse VALUES(?,?,?,?,?,?,?,?,?)",
                        (m["ts"], m["trend"], m["vol"], m["breadth"],
                         round(m["btc_5m"], 3), round(m["btc_1h"], 3),
                         m["up_pct"], round(m["vol_med"], 3),
                         round(m["vol_p90"], 3)))
                    c.commit(); c.close()
                except Exception as e:
                    log.debug("حفظ النبض: %s", e)
                _a = advice()
                log.info("🌡️ %s | لونج %+.2f · شورت %+.2f · حجم ×%.1f",
                         _a["note"], _a["long_bias"], _a["short_bias"],
                         _a["size_mult"])
        except Exception as e:
            log.error("نبض السوق: %s", e)
        await asyncio.sleep(EVERY)
