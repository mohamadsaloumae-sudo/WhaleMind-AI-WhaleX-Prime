# ═══════════════════════════════════════════════════════════════
# ─── SIGNAL_MSG V4 — نهائي ─────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

import html
from datetime import datetime, timezone, timedelta

UAE_TZ = timezone(timedelta(hours=4))

def signal_msg(s: dict) -> str:
    """التصميم النهائي — مضغوط وأنيق"""
    radar = s.get("radar_type", "futures").upper()
    sym   = s.get("symbol", "")
    dir_  = s.get("direction", "")
    grade = s.get("grade", "B")
    conf  = s.get("confidence", 0)
    score = s.get("score", 0)
    entry = s.get("entry", 0)
    sl    = s.get("sl", 0)
    tp1   = s.get("tp1", 0)
    tp2   = s.get("tp2", 0)
    tp3   = s.get("tp3", 0)
    lev   = s.get("leverage", 1)
    strats_raw = s.get("strategies", "")
    strats = strats_raw.split("\n") if strats_raw else []

    funding = s.get("funding_rate", 0)
    oi_change = s.get("open_interest_change", 0)
    btc_trend = s.get("btc_trend", "NEUTRAL")
    mtf_15m = s.get("mtf_15m", "NEUTRAL")
    mtf_1h  = s.get("mtf_1h", "NEUTRAL")
    mtf_4h  = s.get("mtf_4h", "NEUTRAL")
    rr_tp1 = s.get("rr_tp1", 0)
    rr_tp2 = s.get("rr_tp2", 0)
    rr_tp3 = s.get("rr_tp3", 0)
    accuracy = s.get("accuracy", 75.0)
    strat_count = s.get("strategy_count", len(strats))

    # ─ النجوم الذهبية ─
    stars_map = {
        "S": "🌟🌟🌟🌟🌟",
        "A": "🌟🌟🌟🌟",
        "B": "🌟🌟🌟",
        "C": "🌟🌟",
    }
    stars = stars_map.get(grade, "🌟🌟🌟")

    # ─ التوقيت ─
    now_uae = datetime.now(UAE_TZ).strftime("%H:%M • %d/%m/%Y")

    # ─ النسب ─
    def pct(target):
        if entry == 0: return 0
        return (abs(target - entry) / entry) * 100

    sl_pct  = pct(sl)
    tp1_pct = pct(tp1)
    tp2_pct = pct(tp2)
    tp3_pct = pct(tp3)

    # ─ تنسيق السعر ─
    def fmt(v):
        if v >= 1000: return f"{v:.2f}"
        if v >= 1:    return f"{v:.4f}"
        return f"{v:.6f}"

    # ─ MTF ─
    def mtf_ok(t, direction):
        required = "BULLISH" if direction == "LONG" else "BEARISH"
        return "✅" if t == required else ("⚪" if t == "NEUTRAL" else "❌")

    mtf_line = f"{mtf_ok(mtf_15m, dir_)} 15m  {mtf_ok(mtf_1h, dir_)} 1H  {mtf_ok(mtf_4h, dir_)} 4H"

    # ─ BTC ─
    btc_emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "⚪"}.get(btc_trend, "⚪")

    # ─ Direction ─
    if dir_ == "LONG":
        dir_line = "🟢 <b>LONG</b>"
    else:
        dir_line = "🔴 <b>SHORT</b>"

    # ─ Strategies top 4 ─
    strat_text = html.escape(" • ".join([s.strip() for s in strats[:4]]))

    msg = f"""🐋 <b>WhaleX Prime</b>  •  {stars}
━━━━━━━━━━━━━━━━━━━━━
💎 <b><code>{sym}</code></b>
{dir_line}  •  ⚡ Cross <b>{lev:.0f}x</b>
🏆 Grade <b>{grade}</b>  •  Score {score:.1f}  •  ثقة {conf:.0f}%

🛒 الدخول:  <code>{fmt(entry)}</code>
🛑 الوقف:    <code>{fmt(sl)}</code>  ({sl_pct:.2f}%)
🥇 TP1:     <code>{fmt(tp1)}</code>  ({tp1_pct:.1f}% • 1:{rr_tp1})
🥈 TP2:     <code>{fmt(tp2)}</code>  ({tp2_pct:.1f}% • 1:{rr_tp2})
🚀 TP3:     <code>{fmt(tp3)}</code>  ({tp3_pct:.1f}% • 1:{rr_tp3})

📊 {strat_count}/13: {strat_text}

🛡 MTF: {mtf_line}
{btc_emoji} BTC: <b>{btc_trend}</b>  •  Funding: <code>{funding:+.3f}%</code>  •  OI: <code>{oi_change:+.1f}%</code>
🎯 الدقة التاريخية: <b>{accuracy:.1f}%</b>

⏱ <i>{now_uae} • UTC+4</i>
<i>⚠️ ليست نصيحة مالية — DYOR</i>"""

    return msg
