"""🦅 عين الصقر التفاعلية — فحص أي عملة بنفس عيون الرادار."""
import time, logging
from types import SimpleNamespace
from fastapi import APIRouter, Query

log = logging.getLogger("scanner")
router = APIRouter()


@router.get("/api/scanner/scan")
async def scan(symbol: str = Query(...)):
    sym = symbol.upper().replace("/", "").replace("-", "").strip()
    if not sym.endswith("USDT"):
        sym += "USDT"
    out = {"symbol": sym, "ok": False}
    try:
        from radars.futures.engine import fetch_klines_async, rsi as _rsi
        from quant_engine.ml_brain import live_context, predict_signal, smart_leverage
        from quant_engine.ob_stream import get_price as _wsp

        k = await fetch_klines_async(sym, "4h", 50)
        if not k or len(k) < 25:
            # 🌍 fapi محظور على السيرفر (النظام يعيش على WS) — سبوت يفحص أي عملة
            try:
                import httpx
                from types import SimpleNamespace as _NS
                async with httpx.AsyncClient(timeout=8) as _c:
                    _r = await _c.get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=4h&limit=60")
                    _rows = _r.json()
                if isinstance(_rows, list):
                    k = [_NS(time=int(x[0]) // 1000, open=float(x[1]), high=float(x[2]),
                             low=float(x[3]), close=float(x[4]), volume=float(x[5]),
                             buy_volume=float(x[9])) for x in _rows]
            except Exception as _fe:
                log.debug("spot fallback %s: %s", sym, _fe)
        if not k or len(k) < 25:
            out["error"] = "no_data"
            return out
        closes = [c.close for c in k]
        price = _wsp(sym) or closes[-1]
        rsi_v = _rsi(closes)
        highs = [c.high for c in k]; lows = [c.low for c in k]
        pk, lo = max(highs), min(lows)
        rng = pk - lo
        range_pos = (price - lo) / rng if rng > 0 else 0.5
        ch24 = (price - closes[-7]) / closes[-7] * 100 if len(closes) >= 7 and closes[-7] > 0 else 0.0

        lc = live_context(sym)
        obp = lc.get("ob_pressure"); flow = lc.get("cvd_flow")

        def _mk(direction):
            atr = (pk - lo) / max(1, len(k)) or price * 0.01
            sl = price - atr * 1.5 if direction == "LONG" else price + atr * 1.5
            return SimpleNamespace(symbol=sym, direction=direction, grade="A",
                                   confidence=80.0, score=3.0, entry=price, sl=sl,
                                   tp1=0, tp2=0, tp3=0, leverage=5, tier="PH",
                                   regime="", btc_trend="", hawk_phase="",
                                   rsi=rsi_v, range_pos=range_pos, funding=0,
                                   oi_change=0, hawk_modifier=0, volume_ratio=1,
                                   key_strat_count=1, strategies="scan")
        try:
            p_long, _ = predict_signal(_mk("LONG"))
        except Exception:
            p_long = 0.5
        try:
            p_short, _ = predict_signal(_mk("SHORT"))
        except Exception:
            p_short = 0.5

        # الحكم المركّب الشفاف
        verdict, reason_ar, reason_en = "WAIT", "", ""
        if obp is not None and obp >= 0.15 and flow == "up" and rsi_v < 68 and p_long >= 0.45:
            verdict = "LONG"
            reason_ar = "مشترون مسيطرون + تدفق شراء منفَّذ + RSI غير متشبع"
            reason_en = "Buyers dominate + executed buy flow + RSI not overbought"
        elif obp is not None and obp <= -0.15 and flow == "down" and rsi_v > 32 and p_short >= 0.45:
            verdict = "SHORT"
            reason_ar = "بائعون مسيطرون + تدفق بيع منفَّذ + RSI غير مُشبَع بيعاً"
            reason_en = "Sellers dominate + executed sell flow + RSI not oversold"
        else:
            _miss_ar, _miss_en = [], []
            if obp is None:
                _miss_ar.append("لا بثّ عمق حي"); _miss_en.append("no live depth")
            elif -0.15 < obp < 0.15:
                _miss_ar.append("العمق متوازن"); _miss_en.append("balanced depth")
            if flow == "flat" or flow is None:
                _miss_ar.append("التدفق محايد"); _miss_en.append("neutral flow")
            if max(p_long, p_short) < 0.45:
                _miss_ar.append(f"ثقة النموذج منخفضة ({max(p_long,p_short)*100:.0f}%)")
                _miss_en.append(f"low model confidence ({max(p_long,p_short)*100:.0f}%)")
            if not _miss_ar:
                _miss_ar = ["إشارات متضاربة"]; _miss_en = ["mixed signals"]
            reason_ar = " · ".join(_miss_ar); reason_en = " · ".join(_miss_en)

        lev = 5
        try:
            lev = smart_leverage(_mk(verdict if verdict != "WAIT" else ("LONG" if p_long >= p_short else "SHORT")))
        except Exception:
            pass

        _st_ar = "منفجرة صعوداً" if ch24 > 15 else ("هابطة بحدة" if ch24 < -15 else "مستقرة نسبياً")
        _pos_ar = "قرب القمة" if range_pos > 0.75 else ("قرب القاع" if range_pos < 0.25 else "وسط النطاق")
        _dom_ar = "المشترون" if (obp or 0) > 0.15 else ("البائعون" if (obp or 0) < -0.15 else "لا أحد")
        brief_ar = (f"{sym.replace('USDT','')} {_st_ar} ({ch24:+.1f}% خلال 24س)، تقف {_pos_ar} "
                    f"(RSI {rsi_v:.0f}). المسيطر الآن: {_dom_ar}، والتدفق المنفَّذ "
                    f"{'شراء' if flow=='up' else 'بيع' if flow=='down' else 'محايد'}. "
                    f"توقّع النموذج: لونغ {p_long*100:.0f}% · شورت {p_short*100:.0f}%.")
        _st_en = "exploding up" if ch24 > 15 else ("falling hard" if ch24 < -15 else "relatively stable")
        _pos_en = "near the top" if range_pos > 0.75 else ("near the bottom" if range_pos < 0.25 else "mid-range")
        _dom_en = "Buyers" if (obp or 0) > 0.15 else ("Sellers" if (obp or 0) < -0.15 else "Nobody")
        brief_en = (f"{sym.replace('USDT','')} is {_st_en} ({ch24:+.1f}% 24h), sitting {_pos_en} "
                    f"(RSI {rsi_v:.0f}). In control: {_dom_en}; executed flow is "
                    f"{'buying' if flow=='up' else 'selling' if flow=='down' else 'neutral'}. "
                    f"Model: LONG {p_long*100:.0f}% · SHORT {p_short*100:.0f}%.")

        out.update(ok=True, price=price, change24h=round(ch24, 2), rsi=round(rsi_v, 1),
                   range_pos=round(range_pos, 2), ob_pressure=None if obp is None else round(obp, 2),
                   cvd_flow=flow, p_long=round(p_long * 100), p_short=round(p_short * 100),
                   verdict=verdict, reason=reason_ar, reason_en=reason_en,
                   lev=int(lev), brief=brief_ar, brief_en=brief_en)
    except Exception as e:
        log.error("scan %s: %s", sym, e)
        out["error"] = str(e)
    return out
