"""🦅 عين الصقر التفاعلية — فحص أي عملة بنفس عيون الرادار."""
import time, logging
from types import SimpleNamespace
from fastapi import APIRouter, Query

log = logging.getLogger("scanner")
router = APIRouter()


@router.get("/api/scanner/symbols")
def scanner_symbols(q: str = "", limit: int = 40):
    """🔍 قائمة العملات للبحث الفوريّ — من ملفّات العملات والكون
    المتعدّد. تُصفّى بأوّل حرف فلا يحتاج المستخدم كتابة الاسم كاملاً."""
    import sqlite3 as _sq
    out, seen = [], set()
    qq = (q or "").strip().upper()
    for db, tbl, col in (("/opt/whalex/coin_profiles.db", "coin_profiles", "symbol"),
                         ("/opt/whalex/multi_universe.db", "universe", "symbol")):
        try:
            c = _sq.connect(f"file:{db}?mode=ro", uri=True)
            sql = f"SELECT {col} FROM {tbl}"
            args = ()
            if qq:
                sql += f" WHERE UPPER({col}) LIKE ?"
                args = (qq + "%",)
            sql += f" LIMIT {int(limit) * 3}"
            for (sy,) in c.execute(sql, args):
                base = str(sy or "").upper().replace("USDT", "")
                if base and base not in seen:
                    seen.add(base)
                    out.append(base)
            c.close()
        except Exception:
            pass
    out.sort(key=lambda x: (len(x), x))
    return {"symbols": out[:limit]}


@router.get("/api/scanner/market")
async def scanner_market(symbol: str = Query(...)):
    """🌐 بطاقة العملة الشاملة: أين تُتداوَل · سبوت أم فيوتشر ·
    القيمة السوقية والترتيب والحجم — كلّها حيّة لا ثابتة."""
    import asyncio as _a
    import httpx as _h
    base = symbol.upper().replace("USDT", "").strip()
    pair = base + "USDT"
    out = {"symbol": base, "pair": pair, "venues": [],
           "spot": False, "futures": False, "market": {}}

    async def _binance(c):
        v = {"id": "binance", "name": "Binance", "spot": False, "futures": False}
        try:
            r = await c.get("https://api.binance.com/api/v3/ticker/24hr",
                            params={"symbol": pair}, timeout=8)
            if r.status_code == 200:
                v["spot"] = True
                d = r.json()
                out["market"]["price"] = float(d.get("lastPrice") or 0)
                out["market"]["change24h"] = float(d.get("priceChangePercent") or 0)
                out["market"]["vol24h"] = float(d.get("quoteVolume") or 0)
        except Exception:
            pass
        try:
            r = await c.get("https://fapi.binance.com/fapi/v1/ticker/24hr",
                            params={"symbol": pair}, timeout=8)
            if r.status_code == 200:
                v["futures"] = True
        except Exception:
            pass
        return v

    async def _simple(c, vid, name, url, key=None):
        v = {"id": vid, "name": name, "spot": False, "futures": False}
        try:
            r = await c.get(url, timeout=8)
            if r.status_code == 200:
                t = r.text
                if base in t.upper() and "error" not in t.lower()[:200]:
                    v["spot"] = True
        except Exception:
            pass
        return v

    # 🌐 follow_redirects إلزاميّ — CoinPaprika يُعيد 301 بدونه
    async with _h.AsyncClient(follow_redirects=True,
                              headers={"User-Agent": "Mozilla/5.0"}) as c:
        tasks = [
            _binance(c),
            _simple(c, "bybit", "Bybit",
                    f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={pair}"),
            _simple(c, "mexc", "MEXC",
                    f"https://api.mexc.com/api/v3/ticker/24hr?symbol={pair}"),
            _simple(c, "gate", "Gate.io",
                    f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={base}_USDT"),
            _simple(c, "okx", "OKX",
                    f"https://www.okx.com/api/v5/market/ticker?instId={base}-USDT"),
            _simple(c, "bitget", "Bitget",
                    f"https://api.bitget.com/api/v2/spot/market/tickers?symbol={pair}"),
        ]
        res = await _a.gather(*tasks, return_exceptions=True)
        for v in res:
            if isinstance(v, dict) and (v["spot"] or v["futures"]):
                out["venues"].append(v)
                out["spot"] = out["spot"] or v["spot"]
                out["futures"] = out["futures"] or v["futures"]

        # 📊 القيمة السوقية والترتيب — حيّان من CoinPaprika
        try:
            r = await c.get("https://api.coinpaprika.com/v1/search",
                            params={"q": base, "c": "currencies", "limit": 1},
                            timeout=10)
            cur = (r.json().get("currencies") or [])
            if cur:
                cid = cur[0]["id"]
                r2 = await c.get(
                    f"https://api.coinpaprika.com/v1/tickers/{cid}", timeout=10)
                d2 = r2.json()
                q = (d2.get("quotes") or {}).get("USD") or {}
                out["market"].update({
                    "name": d2.get("name"),
                    "rank": d2.get("rank"),
                    "market_cap": q.get("market_cap"),
                    "vol24h_global": q.get("volume_24h"),
                    "change_7d": q.get("percent_change_7d"),
                    "change_30d": q.get("percent_change_30d"),
                    "ath_price": q.get("ath_price"),
                    "from_ath": q.get("percent_from_price_ath"),
                    "supply": d2.get("circulating_supply"),
                })
                # 🌐 نبذة المشروع وروابطه — من صفحة العملة نفسها
                try:
                    r3 = await c.get(
                        f"https://api.coinpaprika.com/v1/coins/{cid}",
                        timeout=12)
                    d3 = r3.json()
                    desc = (d3.get("description") or "").strip()
                    links = {}
                    for k, v in (d3.get("links") or {}).items():
                        if isinstance(v, list) and v:
                            links[k] = v[0]
                    desc_ar = None
                    if desc:
                        try:
                            from routers.ticker import _translate
                            desc_ar = await _translate(desc[:480])
                        except Exception as _te:
                            log.debug("translate desc: %s", _te)
                    out["project"] = {
                        "desc": desc[:700] if desc else None,
                        "desc_ar": desc_ar,
                        "tags": [t.get("name") for t in
                                 (d3.get("tags") or [])][:5],
                        "started": d3.get("started_at"),
                        "links": links,
                    }
                except Exception as e3:
                    log.debug("project %s: %s", base, e3)
        except Exception as e:
            log.debug("paprika %s: %s", base, e)
    return out


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
        # 📊 تغيّر 24 ساعة — من باينانس مباشرة. الحساب من الشموع بديل احتياطيّ فقط.
        ch24 = None
        try:
            import httpx as _hx
            async with _hx.AsyncClient(timeout=6) as _tc:
                _tr = await _tc.get("https://api.binance.com/api/v3/ticker/24hr",
                                    params={"symbol": sym})
                if _tr.status_code == 200:
                    ch24 = float(_tr.json().get("priceChangePercent") or 0)
        except Exception as _ce:
            log.debug("ch24 %s: %s", sym, _ce)
        if ch24 is None:
            ch24 = (price - closes[-6]) / closes[-6] * 100 if len(closes) >= 6 and closes[-6] > 0 else 0.0

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
            elif flow == "up" and (obp or 0) < 0.15:
                _miss_ar.append("تدفّق شراء لكن دفتر الأوامر لا يدعمه بعد")
                _miss_en.append("buy flow but order book not backing it yet")
            elif flow == "down" and (obp or 0) > -0.15:
                _miss_ar.append("تدفّق بيع لكن دفتر الأوامر لا يدعمه بعد")
                _miss_en.append("sell flow but order book not backing it yet")
            if max(p_long, p_short) < 0.45:
                _miss_ar.append(f"ثقة النموذج منخفضة ({max(p_long,p_short)*100:.0f}%)")
                _miss_en.append(f"low model confidence ({max(p_long,p_short)*100:.0f}%)")
            if not _miss_ar:
                _miss_ar = ["إشارات متضاربة"]; _miss_en = ["mixed signals"]
            reason_ar = " · ".join(_miss_ar); reason_en = " · ".join(_miss_en)

        # 🪙 حكم السبوت — مقياسه الاتّجاه لا الضغط اللحظيّ. لا شورت فيه.
        _ma20 = sum(closes[-20:]) / len(closes[-20:]) if len(closes) >= 20 else price
        _above = price > _ma20
        _slope = (_ma20 - (sum(closes[-40:-20]) / 20)) if len(closes) >= 40 else 0.0
        spot_verdict, spot_ar, spot_en = "WAIT", "", ""
        if ch24 < -15:
            spot_verdict = "SHORT"
            spot_ar = "هبوط حادّ مستمرّ — لا تُمسك سكّيناً هابطة"
            spot_en = "Sharp ongoing drop — don't catch a falling knife"
        elif rsi_v > 72 or range_pos > 0.88:
            spot_verdict = "SHORT"
            spot_ar = "قرب القمّة ومتشبّعة شرائياً — الدخول هنا مكلف"
            spot_en = "Near the top and overbought — poor entry"
        elif _above and _slope > 0 and rsi_v < 68 and range_pos < 0.8:
            spot_verdict = "LONG"
            spot_ar = "فوق متوسّط 20 والمتوسّط صاعد — اتّجاه شراء سليم"
            spot_en = "Above rising 20-MA — healthy uptrend"
        elif range_pos < 0.3 and rsi_v < 45 and ch24 > -8:
            spot_verdict = "LONG"
            spot_ar = "قرب القاع بلا انهيار — تجميع بسعر منخفض"
            spot_en = "Near the bottom without collapse — accumulation zone"
        else:
            spot_ar = "الاتّجاه غير محسوم — الانتظار أوفر"
            spot_en = "Trend undecided — waiting is cheaper"

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

        # 📐 بنود التحليل الفنّيّ — كلّ بند مستقلّ ليُعرَض في صفّ خاصّ
        _flow_ar = "شراء" if flow == "up" else ("بيع" if flow == "down" else "محايد")
        _flow_en = "Buying" if flow == "up" else ("Selling" if flow == "down" else "Neutral")
        _rsi_ar = "متشبّعة شرائياً" if rsi_v > 70 else ("متشبّعة بيعاً" if rsi_v < 30 else "متوازن")
        _rsi_en = "Overbought" if rsi_v > 70 else ("Oversold" if rsi_v < 30 else "Balanced")
        # الرقمان سؤالان منفصلان لا يجمعان 100% — لا تجوز مقارنتهما
        _pv = p_long if verdict == "LONG" else (p_short if verdict == "SHORT" else max(p_long, p_short))
        if verdict == "WAIT":
            _mdl_ar, _mdl_en = "بلا اتّجاه", "No direction"
        else:
            _mdl_ar = ("ثقة عالية" if _pv >= 0.65 else "ثقة كافية" if _pv >= 0.45 else "ثقة ضعيفة")
            _mdl_en = ("High confidence" if _pv >= 0.65 else "Adequate" if _pv >= 0.45 else "Low confidence")
        _mdl_d_ar = (f"احتمال نجاح اللونغ {p_long*100:.0f}%" if verdict == "LONG"
                     else f"احتمال نجاح الشورت {p_short*100:.0f}%" if verdict == "SHORT"
                     else f"لونغ {p_long*100:.0f}% · شورت {p_short*100:.0f}% — تقديران منفصلان")
        _mdl_d_en = (f"LONG success probability {p_long*100:.0f}%" if verdict == "LONG"
                     else f"SHORT success probability {p_short*100:.0f}%" if verdict == "SHORT"
                     else f"LONG {p_long*100:.0f}% · SHORT {p_short*100:.0f}% — separate estimates")
        facts = [
            {"k": "الحالة العامّة", "k_en": "Overall state", "v": _st_ar, "v_en": _st_en,
             "d": f"{ch24:+.1f}% خلال 24 ساعة", "d_en": f"{ch24:+.1f}% over 24h"},
            {"k": "موقع السعر", "k_en": "Price position", "v": _pos_ar, "v_en": _pos_en,
             "d": f"{range_pos*100:.0f}% من نطاق 8 أيام", "d_en": f"{range_pos*100:.0f}% of the 8-day range"},
            {"k": "الزخم", "k_en": "Momentum", "v": _rsi_ar, "v_en": _rsi_en,
             "d": f"RSI عند {rsi_v:.0f}", "d_en": f"RSI at {rsi_v:.0f}"},
            {"k": "دفتر الأوامر", "k_en": "Order book", "v": _dom_ar, "v_en": _dom_en,
             "d": ("لا بثّ عمق حيّ" if obp is None else f"ضغط {obp:+.2f}"),
             "d_en": ("no live depth" if obp is None else f"pressure {obp:+.2f}")},
            {"k": "التدفّق المنفَّذ", "k_en": "Executed flow", "v": _flow_ar, "v_en": _flow_en,
             "d": "اتّجاه الصفقات المنفَّذة فعلياً", "d_en": "Direction of actually executed trades"},
            {"k": "توقّع النموذج", "k_en": "Model forecast", "v": _mdl_ar, "v_en": _mdl_en,
             "d": _mdl_d_ar, "d_en": _mdl_d_en},
        ]

        out.update(ok=True, price=price, change24h=round(ch24, 2), rsi=round(rsi_v, 1),
                   range_pos=round(range_pos, 2), ob_pressure=None if obp is None else round(obp, 2),
                   cvd_flow=flow, p_long=round(p_long * 100), p_short=round(p_short * 100),
                   verdict=verdict, reason=reason_ar, reason_en=reason_en,
                   spot_verdict=spot_verdict, spot_reason=spot_ar, spot_reason_en=spot_en,
                   lev=int(lev), brief=brief_ar, brief_en=brief_en, facts=facts)
    except Exception as e:
        log.error("scan %s: %s", sym, e)
        out["error"] = str(e)
    return out
