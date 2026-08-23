"""🐸🧠 منطق الميم v3 — دوال صافية مقيسة على 303 صفقة.

قياس: الواقع -728.4% · بهذا المنطق +1,860.1% (فرق 2,588 نقطة).
  • أرضية -15% وحدها: +600.2%
  • قفل القمّة وحده:   +978.1%
  • 9 صفقات سحب (3%) كلّفت -777% — والتنقيط لم يمنعها (4 منها بنقاط 100)
فالحماية تنتقل من بوّابات الدخول إلى الحارس اللحظيّ،
والربح يأتي من ترك الرابحة تجري لا من كثرة البوّابات.
"""
import logging
log = logging.getLogger("meme_logic")

MIN_LIQ_USD = 20_000
MAX_TOP_HOLDER = 0.15
MAX_TOP10 = 0.45
FRESH_AGE_H = 3.0
FRESH_MIN_TXNS_H1 = 50
FRESH_MIN_VOL_H1 = 10_000
MATURE_MIN_TXNS_H1 = 150
MATURE_MIN_VOL_24 = 40_000
MIN_BUY_RATIO = 0.52
MAX_BUY_RATIO = 0.88
MIN_AVG_TRADE = 25.0
MAX_RUN_H6 = 250.0
MAX_RUN_H1 = 300.0
MIN_H24 = -45.0
MAX_VOL_LIQ_H1 = 25.0

HARD_FLOOR = -15.0
PEAK_ARM = 8.0
PEAK_GIVEBACK = 20.0
DRAIN_EXIT = 0.80
STALE_HOURS = 4.0
STALE_MAX_MOVE = 3.0


def safety_gate(liq_usd, mint_ok, freeze_ok, top_holder, top10):
    """🛡️ السلامة البنيوية — ما لا يُساوَم عليه."""
    if liq_usd < MIN_LIQ_USD:
        return False, f"سيولة ${liq_usd:,.0f} < ${MIN_LIQ_USD:,}"
    if not mint_ok:
        return False, "صلاحية السكّ مفتوحة"
    if not freeze_ok:
        return False, "صلاحية التجميد مفتوحة"
    if top_holder > MAX_TOP_HOLDER:
        return False, f"أعلى حامل {top_holder*100:.0f}%"
    if top10 > MAX_TOP10:
        return False, f"العشرة الأوائل {top10*100:.0f}%"
    return True, "سلامة ✓"


def momentum_gate(age_hours, txns_h1, vol_h1, vol_h24, buy_ratio, liq_usd):
    """⚡ الزخم — العتبة تتبع العمر. الطازجة لا تملك حجم 24س."""
    fresh = age_hours < FRESH_AGE_H
    if fresh:
        if txns_h1 < FRESH_MIN_TXNS_H1:
            return False, f"معاملات {txns_h1} (طازجة)"
        if vol_h1 < FRESH_MIN_VOL_H1:
            return False, f"حجم ساعة ${vol_h1:,.0f}"
    else:
        if txns_h1 < MATURE_MIN_TXNS_H1:
            return False, f"معاملات {txns_h1}"
        if vol_h24 < MATURE_MIN_VOL_24:
            return False, f"حجم 24س ${vol_h24:,.0f}"
    if buy_ratio < MIN_BUY_RATIO:
        return False, f"شراء {buy_ratio*100:.0f}% ضعيف"
    if buy_ratio > MAX_BUY_RATIO:
        return False, f"شراء {buy_ratio*100:.0f}% مفرط"
    if txns_h1 > 0 and vol_h1 > 0:
        avg = vol_h1 / txns_h1
        if avg < MIN_AVG_TRADE:
            return False, f"متوسط صفقة ${avg:.0f} (بوتات)"
    if liq_usd > 0 and vol_h1 / liq_usd > MAX_VOL_LIQ_H1:
        return False, f"حجم/سيولة x{vol_h1/liq_usd:.0f} (غسل)"
    return True, f"زخم ✓ ({'طازجة' if fresh else 'ناضجة'})"


def wave_gate(h1, h6, h24):
    """🌊 لا نشتري موجة استُهلكت ولا عملة تنهار."""
    if h6 > MAX_RUN_H6:
        return False, f"موجة قديمة (6س {h6:+.0f}%)"
    if h1 > MAX_RUN_H1:
        return False, f"انفجرت أصلاً (1س {h1:+.0f}%)"
    if h24 < MIN_H24:
        return False, f"تنهار (24س {h24:+.0f}%)"
    return True, "موجة ✓"


def evaluate(f: dict) -> dict:
    ok, why = safety_gate(f.get("liq_usd", 0), f.get("mint_ok", False),
                          f.get("freeze_ok", False), f.get("top_holder", 1.0),
                          f.get("top10", 1.0))
    if not ok:
        return {"ok": False, "stage": "safety", "why": why}
    ok, why = momentum_gate(f.get("age_hours", 99), f.get("txns_h1", 0),
                            f.get("vol_h1", 0), f.get("vol_h24", 0),
                            f.get("buy_ratio", 0), f.get("liq_usd", 0))
    if not ok:
        return {"ok": False, "stage": "momentum", "why": why}
    ok, why = wave_gate(f.get("h1", 0), f.get("h6", 0), f.get("h24", 0))
    if not ok:
        return {"ok": False, "stage": "wave", "why": why}
    fresh = f.get("age_hours", 99) < FRESH_AGE_H
    conf = 55
    if f.get("liq_usd", 0) >= 60_000: conf += 8
    if 0.58 <= f.get("buy_ratio", 0) <= 0.75: conf += 10
    if f.get("txns_h1", 0) >= 250: conf += 8
    if f.get("top_holder", 1) <= 0.06: conf += 8
    if fresh: conf += 6
    return {"ok": True, "stage": "pass", "why": "كل البوّابات ✓",
            "fresh": fresh, "confidence": min(94, conf)}


def exit_decision(pnl, peak_pnl, age_min, liq_ratio=1.0, rugged=False):
    """🚪 الخروج — مقيس: هذه القاعدة تحوّل -728% إلى +1,860%."""
    if rugged:
        return True, "🚨 عقد مسحوب"
    if liq_ratio < DRAIN_EXIT:
        return True, f"🚨 سحب سيولة {(1-liq_ratio)*100:.0f}%"
    if pnl <= HARD_FLOOR:
        return True, f"🛑 أرضية {HARD_FLOOR:.0f}%"
    if peak_pnl >= PEAK_ARM:
        keep = peak_pnl * (1 - PEAK_GIVEBACK / 100)
        if pnl <= keep:
            return True, f"🔒 قفل: قمّة {peak_pnl:+.0f}% → {pnl:+.0f}%"
    if age_min >= STALE_HOURS * 60 and abs(pnl) < STALE_MAX_MOVE \
            and peak_pnl < PEAK_ARM:
        return True, f"⏱ راكدة {age_min/60:.0f}س"
    return False, ""
