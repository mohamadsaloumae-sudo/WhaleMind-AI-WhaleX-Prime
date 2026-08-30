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
                log.info("🌡️ السوق: %s · %s · اتّساع %s (%d%% صاعدة) "
                         "| BTC ساعة %+.2f%%",
                         m["trend"], m["vol"], m["breadth"],
                         m["up_pct"], m["btc_1h"])
        except Exception as e:
            log.error("نبض السوق: %s", e)
        await asyncio.sleep(EVERY)
