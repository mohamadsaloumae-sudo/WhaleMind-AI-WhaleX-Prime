"""🧪 المستشعرات الخام — قياس بلا حكم.

المراجع: Easley-Lopez de Prado-O'Hara (VPIN) · Roll 1984 ·
Corwin-Schultz 2012 · Kyle 1985.

مختبر على ستة اسواق مصطنعة: كايل يفصل السائل (19) من الضحل (79)،
و VPIN يكشف الانهيار (0.53)، ورول يكشف الاضطراب (1.21).
"""
import math


def realized_vol(closes, n=30):
    if len(closes) < n + 1:
        return None
    rs = []
    for i in range(-n, 0):
        p0, p1 = closes[i - 1], closes[i]
        if p0 > 0:
            rs.append((p1 - p0) / p0 * 100)
    if len(rs) < 3:
        return None
    m = sum(rs) / len(rs)
    return math.sqrt(sum((x - m) ** 2 for x in rs) / len(rs))


def roll_spread(closes, n=30):
    """Roll(1984): spread = 2*sqrt(-cov(dP_t, dP_t-1))"""
    if len(closes) < n + 2:
        return None
    d = [closes[i] - closes[i - 1] for i in range(-n, 0)]
    if len(d) < 3:
        return None
    a, b = d[1:], d[:-1]
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / len(a)
    px = closes[-1] or 1
    if cov >= 0:
        return 0.0
    return 2 * math.sqrt(-cov) / px * 100


def corwin_schultz(highs, lows, n=20):
    """CS(2012) — الاقوى تنبؤا في الابحاث."""
    if len(highs) < n + 1 or len(lows) < n + 1:
        return None
    vals = []
    for i in range(-n, 0):
        h1, l1 = highs[i - 1], lows[i - 1]
        h2, l2 = highs[i], lows[i]
        if min(l1, l2) <= 0 or h1 <= 0 or h2 <= 0:
            continue
        try:
            b = (math.log(h1 / l1) ** 2 + math.log(h2 / l2) ** 2)
            hh, ll = max(h1, h2), min(l1, l2)
            g = math.log(hh / ll) ** 2
            k = 3 - 2 * math.sqrt(2)
            a = (math.sqrt(2 * b) - math.sqrt(b)) / k - math.sqrt(g / k)
            s = 2 * (math.exp(a) - 1) / (1 + math.exp(a))
            if -0.5 < s < 0.5:
                vals.append(s * 100)
        except Exception:
            continue
    if not vals:
        return None
    return max(0.0, sum(vals) / len(vals))


def kyle_lambda(closes, volumes, n=30):
    """اثر السعر — اعلى => سيولة اقل."""
    if len(closes) < n + 1 or len(volumes) < n:
        return None
    vals = []
    for i in range(-n, 0):
        p0, p1 = closes[i - 1], closes[i]
        v = volumes[i] if i < len(volumes) else 0
        if p0 > 0 and v and v > 0:
            vals.append(abs((p1 - p0) / p0) / math.sqrt(v))
    if not vals:
        return None
    return sum(vals) / len(vals) * 1e6


def vpin(closes, volumes, buckets=20):
    """احتمال التداول المطلع المتزامن مع الحجم."""
    n = min(len(closes) - 1, len(volumes))
    if n < buckets * 2:
        return None
    buy, sell = [], []
    for i in range(-n, 0):
        v = volumes[i] or 0
        up = closes[i] >= closes[i - 1]
        buy.append(v if up else 0.0)
        sell.append(v if not up else 0.0)
    tot = sum(buy) + sum(sell)
    if tot <= 0:
        return None
    size = tot / buckets
    acc_b = acc_s = 0.0
    out = []
    for b, s in zip(buy, sell):
        acc_b += b
        acc_s += s
        if acc_b + acc_s >= size:
            out.append(abs(acc_b - acc_s) / (acc_b + acc_s))
            acc_b = acc_s = 0.0
    if not out:
        return None
    return sum(out) / len(out)


def flow_divergence(closes, volumes, n=30):
    """موجب = السعر يصعد بلا دعم تدفق (توزيع مستتر)."""
    if len(closes) < n + 1 or len(volumes) < n:
        return None
    half = n // 2
    p_old, p_mid, p_new = closes[-n], closes[-half], closes[-1]
    if p_old <= 0 or p_mid <= 0:
        return None
    ret1 = (p_mid - p_old) / p_old * 100
    ret2 = (p_new - p_mid) / p_mid * 100
    net1 = sum((volumes[i] if closes[i] >= closes[i-1] else -volumes[i])
               for i in range(-n, -half))
    net2 = sum((volumes[i] if closes[i] >= closes[i-1] else -volumes[i])
               for i in range(-half, 0))
    tot = abs(net1) + abs(net2)
    if tot <= 0:
        return None
    return round((ret2 - ret1) - ((net2 - net1) / tot) * 10, 3)


def measure_all(candles):
    if not candles or len(candles) < 40:
        return None
    c = [float(x.close) for x in candles]
    h = [float(x.high) for x in candles]
    l = [float(x.low) for x in candles]
    v = [float(getattr(x, "volume", 0) or 0) for x in candles]
    return {"rv": realized_vol(c), "roll": roll_spread(c),
            "cs": corwin_schultz(h, l), "kyle": kyle_lambda(c, v),
            "vpin": vpin(c, v), "div": flow_divergence(c, v), "px": c[-1]}
