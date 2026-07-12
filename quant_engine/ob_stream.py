"""المراقبة اللحظية للأوردر بوك (WebSocket فيوتشرز).
spoofing + iceberg لحظي. الرادار/المدير يقرآن عبر get_signals(symbol)."""
import asyncio, json, time
from collections import deque, defaultdict
import websockets
import logging
log=logging.getLogger('ob_stream')
from quant_engine.order_book_analyzer import OrderBookSnapshot, detect_walls

WS = "wss://fstream.binance.com/public/stream?streams="
_books = defaultdict(lambda: deque(maxlen=1800))
_signals = {}

def _build(sym, d):
    b = [(float(p), float(q)) for p, q in d.get("b", [])]
    a = [(float(p), float(q)) for p, q in d.get("a", [])]
    if not b or not a: return None
    return OrderBookSnapshot(symbol=sym.upper(), timestamp=time.time(),
                             bids=b, asks=a, mid_price=(b[0][0]+a[0][0])/2)

def _spoof(book):
    if len(book) < 40: return []
    s = list(book); now, ago = s[-1], s[-30]
    nbw, naw = detect_walls(now,20,7.0); abw, aaw = detect_walls(ago,20,7.0)
    mid = now.mid_price; out, seen = [], set()
    for w in abw:
        p = w["price"]
        if p not in seen and not any(abs(x["price"]-p)/p<0.0015 for x in nbw) and mid>p*1.0005:
            out.append({"side":"bid","price":p,"mult":w["multiplier"]}); seen.add(p)
    for w in aaw:
        p = w["price"]
        if p not in seen and not any(abs(x["price"]-p)/p<0.0015 for x in naw) and mid<p*0.9995:
            out.append({"side":"ask","price":p,"mult":w["multiplier"]}); seen.add(p)
    return out

def _iceberg(book):
    if len(book) < 50: return []
    snaps = list(book)[-50:]; bq, aq = defaultdict(list), defaultdict(list)
    for s in snaps:
        for p,q in s.bids[:5]: bq[round(p,8)].append(q)
        for p,q in s.asks[:5]: aq[round(p,8)].append(q)
    def refills(ser):
        if len(ser)<10: return 0
        base=max(ser); cnt,low=0,False
        for q in ser:
            if q<base*0.4: low=True
            elif low and q>base*0.8: cnt+=1; low=False
        return cnt
    out=[]
    for p,ser in bq.items():
        r=refills(ser)
        if r>=2: out.append({"side":"bid","price":p,"refills":r})
    for p,ser in aq.items():
        r=refills(ser)
        if r>=2: out.append({"side":"ask","price":p,"refills":r})
    return out

# الأطر المبثوثة مباشرة (bootstrap تاريخي + تحديث WS). النادرة (1d) تبقى REST.
STREAM_TFS = ["5m", "15m", "1h", "4h"]
# مخزن منفصل لكل (sym_lower, tf) → deque شموع مغلقة
_klines = defaultdict(lambda: deque(maxlen=250))

def _kkey(sym_lower, tf):
    return f"{sym_lower}|{tf}"

def get_klines(symbol, interval="1m", limit=50):
    """شموع من مخزن الإطار المطلوب. None إن غير مبثوث/غير جاهز → المستهلك يسقط لـREST."""
    if interval not in STREAM_TFS:
        return None
    sym = symbol.upper().replace("/","").replace("-","")
    if not sym.endswith("USDT"): sym += "USDT"
    dq = _klines.get(_kkey(sym.lower(), interval))
    if not dq or len(dq) < 20:
        return None
    return list(dq)[-limit:]

def get_signals(symbol):
    return _signals.get(symbol.upper(), {"spoof":[],"iceberg":[],"ts":0})

def get_price(symbol):
    """السعر اللحظي (mid) من آخر snapshot — بلا REST. None إن لا بثّ للعملة."""
    sym = symbol.upper().replace("/","").replace("-","")
    if not sym.endswith("USDT"): sym += "USDT"
    bk = _books.get(sym.lower())
    if bk and len(bk):
        return bk[-1].mid_price
    return None

async def _bootstrap(symbols):
    """ملء المخزون تاريخياً مرة واحدة (REST مُباعد) — بعده التحديث من WS فقط."""
    import httpx
    async with httpx.AsyncClient(timeout=10) as cl:
        for tf in STREAM_TFS:
            for s in symbols:
                sl = s.lower()
                try:
                    r = await cl.get("https://fapi.binance.com/fapi/v1/klines",
                                     params={"symbol": s.upper(), "interval": tf, "limit": 150})
                    dq = _klines[_kkey(sl, tf)]
                    for k in r.json():
                        dq.append({"t":int(k[0])//1000,"o":float(k[1]),"h":float(k[2]),
                                   "l":float(k[3]),"c":float(k[4]),"v":float(k[5]),
                                   "bv":float(k[9])})
                except Exception:
                    pass
                await asyncio.sleep(0.05)   # تباعد لتفادي حظر لحظي
    log.info("🌊 Bootstrap done: %d رمز × %d أطر", len(symbols), len(STREAM_TFS))

async def run(symbols, refresh=2.0):
    asyncio.create_task(_bootstrap(symbols))   # لا يحجب اتصال الأوردر بوك
    _kl = [f"{s.lower()}@kline_{tf}" for s in symbols for tf in STREAM_TFS]
    _streams = [f"{s.lower()}@depth20@100ms" for s in symbols] + _kl
    url = WS + "/".join(_streams)
    while True:
        try:
            async with websockets.connect(url, open_timeout=20, max_size=2**23) as ws:
                log.info("🌊 OB-Stream connected: %d رمز (depth + %d أطر kline)",
                         len(symbols), len(STREAM_TFS))
                last=time.time()
                async for raw in ws:
                    m=json.loads(raw); _st=m.get("stream",""); sym=_st.split("@")[0]
                    if "@kline" in _st:
                        _tf=_st.split("kline_")[-1]
                        k=m.get("data",{}).get("k",{})
                        if k.get("x") and _tf in STREAM_TFS:
                            dq=_klines[_kkey(sym,_tf)]
                            row={"t":int(k["t"])//1000,"o":float(k["o"]),"h":float(k["h"]),
                                 "l":float(k["l"]),"c":float(k["c"]),"v":float(k["v"]),
                                 "bv":float(k.get("V",0))}
                            if not dq or dq[-1]["t"]!=row["t"]: dq.append(row)
                            elif dq: dq[-1]=row
                        continue
                    snap=_build(sym, m.get("data",{}))
                    if snap: _books[sym].append(snap)
                    if time.time()-last>=refresh:
                        for s,bk in _books.items():
                            _signals[s.upper()]={"spoof":_spoof(bk),"iceberg":_iceberg(bk),"ts":time.time()}
                        last=time.time()
                        try:
                            from quant_engine.watchdog import beat as _wbeat; _wbeat("ob_stream")
                        except Exception: pass
        except Exception:
            await asyncio.sleep(2)

if __name__ == "__main__":
    import httpx
    r=httpx.get("https://fapi.binance.com/fapi/v1/ticker/24hr",timeout=10)
    d=[x for x in r.json() if x["symbol"].endswith("USDT")]
    d.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
    syms=[x["symbol"] for x in d[:25]]
    async def test():
        asyncio.create_task(run(syms))
        for _ in range(7):
            await asyncio.sleep(10)
            print(f"[{time.strftime('%H:%M:%S')}]", flush=True)
            for s in syms:
                g=get_signals(s)
                if g["spoof"] or g["iceberg"]:
                    sp=",".join(f"{x['side']}@{x['price']:.4g}x{x['mult']:.0f}" for x in g["spoof"][:2])
                    ic=",".join(f"{x['side']}@{x['price']:.4g}R{x['refills']}" for x in g["iceberg"][:2])
                    print(f"  {s}: فخ[{sp}] جبل[{ic}]", flush=True)
    asyncio.run(test())
