"""
WhaleMind Market Cap Filter
═══════════════════════════════════════════════════════════════════
يحسب Market Cap الحقيقي لكل عملة من Binance مباشرة
ويُعيد فلترة العملات بناءً على MC وليس Futures volume فقط

المنطق:
- MC = Price × Circulating Supply
- Circulating Supply من: Binance Spot Exchange Info + CoinGecko fallback
- نستخدمه مع Futures Volume للحصول على صورة كاملة
"""

import asyncio
import httpx
import logging
import time
from typing import Optional, Dict, List

log = logging.getLogger("market_cap_filter")

BINANCE_FAPI = "https://fapi.binance.com/fapi/v1"
BINANCE_SPOT = "https://api.binance.com/api/v3"
COINGECKO = "https://api.coingecko.com/api/v3"


# قاموس Circulating Supply لأهم 100 عملة (تحديث 2026)
# نستخدمه كـ fallback في حال CoinGecko لم يستجب
KNOWN_SUPPLIES = {
    "BTC": 19_800_000,
    "ETH": 120_500_000,
    "BNB": 145_000_000,
    "SOL": 480_000_000,
    "XRP": 58_000_000_000,
    "ADA": 36_000_000_000,
    "DOGE": 148_000_000_000,
    "TRX": 96_000_000_000,
    "LINK": 660_000_000,
    "AVAX": 420_000_000,
    "DOT": 1_540_000_000,
    "MATIC": 9_400_000_000,
    "SHIB": 589_000_000_000_000,
    "LTC": 75_000_000,
    "BCH": 19_800_000,
    "APT": 620_000_000,
    "ARB": 4_500_000_000,
    "OP": 1_400_000_000,
    "SUI": 3_200_000_000,
    "INJ": 100_000_000,
    "ATOM": 390_000_000,
    "NEAR": 1_150_000_000,
    "FIL": 600_000_000,
    "ETC": 150_000_000,
    "UNI": 600_000_000,
    "AAVE": 15_000_000,
    "GRT": 9_500_000_000,
    "IMX": 1_800_000_000,
    "RNDR": 520_000_000,
    "RENDER": 520_000_000,
    "FET": 2_700_000_000,
    "TAO": 8_500_000,
    "ICP": 480_000_000,
    "HBAR": 42_000_000_000,
    "SEI": 4_200_000_000,
    "ORDI": 21_000_000,
    "FTM": 2_800_000_000,
    "ALGO": 8_400_000_000,
    "SAND": 2_500_000_000,
    "MANA": 2_400_000_000,
    "AXS": 152_000_000,
    "GALA": 36_000_000_000,
    "VET": 73_000_000_000,
    "IOTA": 3_500_000_000,
    "EOS": 1_500_000_000,
    "XLM": 30_000_000_000,
    "EGLD": 30_000_000,
    "NEO": 70_000_000,
    "KAS": 25_000_000_000,
    "RUNE": 350_000_000,
    "KAVA": 1_100_000_000,
    "COMP": 9_500_000,
    "PAXG": 100_000,
    "XAUT": 500_000,
    "TIA": 240_000_000,
    "WLD": 1_600_000_000,
    "STX": 1_500_000_000,
    "ARKM": 850_000_000,
    "PYTH": 4_500_000_000,
    "JTO": 130_000_000,
    "JUP": 1_400_000_000,
    "BONK": 73_000_000_000_000,
    "PEPE": 420_000_000_000_000,
    "FLOKI": 9_600_000_000_000,
    "WIF": 1_000_000_000,
    "1000PEPE": 420_000_000_000,
    "1000FLOKI": 9_600_000_000,
    "1000SHIB": 589_000_000_000,
    "1000BONK": 73_000_000_000,
    "MEME": 6_700_000_000,
    "DYDX": 530_000_000,
    "BLUR": 1_400_000_000,
    "CRV": 1_280_000_000,
    "MKR": 925_000,
    "SUSHI": 270_000_000,
    "SNX": 320_000_000,
    "1INCH": 1_100_000_000,
    "YFI": 33_000,
    "ENS": 35_000_000,
    "ETHFI": 1_000_000_000,
    "ENA": 1_500_000_000,
    "ONDO": 1_400_000_000,
    "STRK": 1_700_000_000,
    "MANTA": 250_000_000,
    "ALT": 1_100_000_000,
    "OMNI": 100_000_000,
    "REZ": 1_900_000_000,
    "BB": 410_000_000,
    "NOT": 100_000_000_000,
    "IO": 90_000_000,
    "ZK": 6_700_000_000,
    "BLAST": 19_000_000_000,
    "MEW": 89_000_000_000,
    "POPCAT": 980_000_000,
    "ORDER": 1_200_000_000,
    "AERO": 580_000_000,
    "MOG": 390_000_000_000_000,
    "GOAT": 1_000_000_000,
    "MOODENG": 1_000_000_000,
    "PNUT": 1_000_000_000,
    "ACT": 1_000_000_000,
    "NEIRO": 1_000_000_000_000,
    "DOGS": 550_000_000_000,
    "HMSTR": 64_000_000_000,
    "CATI": 600_000_000,
    "REEF": 22_000_000_000,
    "QTUM": 110_000_000,
    "ZEC": 16_000_000,
    "DASH": 12_000_000,
    "BAT": 1_500_000_000,
    "ZIL": 18_000_000_000,
    "THETA": 1_000_000_000,
    "TFUEL": 6_900_000_000,
    "ICX": 990_000_000,
    "ONT": 880_000_000,
    "WAVES": 130_000_000,
    "ZRX": 850_000_000,
    "KNC": 180_000_000,
    "GLM": 1_000_000_000,
    "ANKR": 10_000_000_000,
    "SKL": 5_700_000_000,
    "STORJ": 470_000_000,
    "OCEAN": 600_000_000,
    "BAND": 145_000_000,
    "API3": 130_000_000,
    "REQ": 1_300_000_000,
    "RLC": 87_000_000,
    "BTS": 3_000_000_000,
    "MTL": 50_000_000,
    "GAS": 14_000_000,
    "CKB": 44_000_000_000,
    "BEL": 33_000_000,
    "XEM": 9_000_000_000,
    "ROSE": 6_900_000_000,
    "CELR": 8_300_000_000,
    "FLOW": 1_500_000_000,
    "CHZ": 9_000_000_000,
    "ENJ": 1_500_000_000,
    "HOT": 178_000_000_000,
    "CFX": 4_500_000_000,
    "ZEN": 15_000_000,
    "JST": 9_300_000_000,
    "TLM": 2_700_000_000,
    "ALICE": 230_000_000,
    "ANT": 35_000_000,
    "ARDR": 1_000_000_000,
    "ARK": 170_000_000,
    "ASTR": 5_600_000_000,
    "AUDIO": 1_300_000_000,
    "ACX": 600_000_000,
    "C98": 880_000_000,
    "COTI": 1_400_000_000,
    "CTSI": 800_000_000,
    "CYBER": 60_000_000,
    "DENT": 99_000_000_000,
    "DOCK": 240_000_000,
    "DUSK": 500_000_000,
    "FXS": 90_000_000,
    "HIGH": 60_000_000,
    "HIVE": 49_000_000,
    "ID": 540_000_000,
    "IDEX": 700_000_000,
    "IOTX": 9_400_000_000,
    "JOE": 360_000_000,
    "LDO": 890_000_000,
    "LEVER": 30_000_000_000,
    "LINA": 9_300_000_000,
    "LIT": 75_000_000,
    "LPT": 39_000_000,
    "LRC": 1_300_000_000,
    "MAGIC": 360_000_000,
    "MASK": 92_000_000,
    "MAV": 360_000_000,
    "MDT": 950_000_000,
    "MINA": 1_180_000_000,
    "MTLX": 5_000_000,
    "MULTI": 100_000_000,
    "NKN": 700_000_000,
    "NTRN": 320_000_000,
    "ORDI": 21_000_000,
    "OXT": 1_000_000_000,
    "PERP": 64_000_000,
    "PHB": 65_000_000,
    "POLYX": 850_000_000,
    "POWR": 1_000_000_000,
    "PROM": 19_000_000,
    "PUNDIX": 260_000_000,
    "QNT": 12_000_000,
    "RDNT": 380_000_000,
    "REI": 1_000_000_000,
    "RIF": 555_000_000,
    "RPL": 19_500_000,
    "RSR": 56_000_000_000,
    "RVN": 14_400_000_000,
    "SC": 56_000_000_000,
    "SFP": 470_000_000,
    "SLP": 51_000_000_000,
    "SPELL": 78_000_000_000,
    "SSV": 11_000_000,
    "STG": 200_000_000,
    "STMX": 9_500_000_000,
    "STPT": 2_000_000_000,
    "SUPER": 700_000_000,
    "SYS": 760_000_000,
    "T": 9_700_000_000,
    "TROY": 10_300_000_000,
    "TRU": 1_500_000_000,
    "TWT": 410_000_000,
    "UMA": 91_000_000,
    "UNFI": 8_500_000,
    "USTC": 9_660_000_000,
    "VANRY": 2_400_000_000,
    "WAXP": 3_300_000_000,
    "WLD": 1_600_000_000,
    "WOO": 1_900_000_000,
    "XEC": 19_700_000_000_000,
    "XVG": 16_600_000_000,
    "XVS": 17_000_000,
    "YGG": 470_000_000,
    "ZIL": 18_000_000_000,
    "RAY": 280_000_000,
    "MOVE": 2_700_000_000,
    "VANA": 12_000_000,
    "ME": 150_000_000,
    "PENGU": 6_300_000_000,
    "USUAL": 470_000_000,
    "TRUMP": 200_000_000,
    "MELANIA": 250_000_000,
    "AI16Z": 1_100_000_000,
    "AIXBT": 1_000_000_000,
    "GRIFFAIN": 1_000_000_000,
    "SWARMS": 1_000_000_000,
    "TST": 1_000_000_000,
    "LAYER": 260_000_000,
    "S": 3_200_000_000,
    "BERA": 110_000_000,
    "TON": 2_500_000_000,
}


# ═══════════════════════════════════════════════════════════════
# ─── BINANCE PRICE FETCH ──────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def fetch_all_prices() -> Dict[str, float]:
    """يجلب أسعار كل عملات Binance Futures دفعة واحدة"""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{BINANCE_FAPI}/ticker/price")
            data = r.json()
            return {t["symbol"]: float(t["price"]) for t in data}
    except Exception as e:
        log.warning("fetch_all_prices: %s", e)
        return {}


# ═══════════════════════════════════════════════════════════════
# ─── COINGECKO FALLBACK ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def fetch_coingecko_supplies(symbols: List[str]) -> Dict[str, float]:
    """
    يجلب Circulating Supply من CoinGecko للعملات غير الموجودة في القاموس
    """
    result = {}
    try:
        # نطلب top 250 لتغطية كل العملات الرئيسية
        async with httpx.AsyncClient(timeout=20) as c:
            for page in range(1, 4):  # 3 صفحات × 250 = 750 عملة
                r = await c.get(
                    f"{COINGECKO}/coins/markets",
                    params={
                        "vs_currency": "usd",
                        "order": "market_cap_desc",
                        "per_page": 250,
                        "page": page,
                        "sparkline": "false"
                    }
                )
                if r.status_code != 200:
                    break
                for coin in r.json():
                    sym = coin.get("symbol", "").upper()
                    supply = coin.get("circulating_supply", 0)
                    if sym and supply:
                        result[sym] = supply
                await asyncio.sleep(1)  # rate limit
    except Exception as e:
        log.warning("fetch_coingecko_supplies: %s", e)
    return result


# ═══════════════════════════════════════════════════════════════
# ─── MARKET CAP CALCULATION ───────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def extract_base_symbol(symbol: str) -> str:
    """يستخرج اسم العملة الأساسي من symbol Binance"""
    # إزالة لاحقات
    for suffix in ["USDT", "BUSD", "USDC"]:
        if symbol.endswith(suffix):
            return symbol[:-len(suffix)]
    return symbol


def calculate_market_cap(symbol: str, price: float, supplies: Dict[str, float]) -> Optional[float]:
    """يحسب MC للعملة"""
    base = extract_base_symbol(symbol)
    
    # أولاً: القاموس المُحدّث
    if base in KNOWN_SUPPLIES:
        return price * KNOWN_SUPPLIES[base]
    
    # ثانياً: CoinGecko
    if base in supplies:
        return price * supplies[base]
    
    return None


# ═══════════════════════════════════════════════════════════════
# ─── TIER CLASSIFICATION (با MC) ──────────────────────────────
# ═══════════════════════════════════════════════════════════════

def classify_by_market_cap(mc_usd: float, daily_volume: float) -> tuple[int, str]:
    """
    تصنيف Tier بناءً على Market Cap + Daily Volume
    
    Tier 1: MC > $5B (أو MC > $1B + Vol > $50M)
    Tier 2: MC > $500M (أو MC > $200M + Vol > $20M)
    Tier 3: MC > $100M + Vol > $10M
    Tier 4: أقل
    """
    
    # Tier 1: العملات الكبيرة
    if mc_usd >= 5_000_000_000:
        return 1, "MC > $5B"
    if mc_usd >= 1_000_000_000 and daily_volume >= 50_000_000:
        return 1, "MC > $1B + Vol > $50M"
    
    # Tier 2: متوسط الحجم
    if mc_usd >= 500_000_000:
        return 2, "MC > $500M"
    if mc_usd >= 200_000_000 and daily_volume >= 20_000_000:
        return 2, "MC > $200M + Vol > $20M"
    
    # Tier 3: صغير لكن مقبول
    if mc_usd >= 100_000_000 and daily_volume >= 10_000_000:
        return 3, "MC > $100M + Vol > $10M"
    if mc_usd >= 50_000_000 and daily_volume >= 20_000_000:
        return 3, "MC > $50M + Vol > $20M"
    
    return 4, f"MC ${mc_usd/1_000_000:.1f}M / Vol ${daily_volume/1_000_000:.1f}M - ضعيف"


# ═══════════════════════════════════════════════════════════════
# ─── DB UPDATE (يحدّث coin_profiles بـ MC) ──────────────────────
# ═══════════════════════════════════════════════════════════════

async def update_profiles_with_market_cap(db_path: str = "/opt/whalex/coin_profiles.db"):
    """
    يحدّث جدول coin_profiles بإضافة Market Cap وإعادة تصنيف Tier
    
    يحتفظ بكل البيانات الأخرى (manipulation, false_breakouts, إلخ)
    لكن يعيد تقييم safe_to_trade + tier + leverage
    """
    import sqlite3
    
    log.info("🚀 Starting Market Cap update...")
    
    # 1. جلب الأسعار الحية
    prices = await fetch_all_prices()
    log.info("✅ Loaded %d prices from Binance", len(prices))
    
    # 2. جلب CoinGecko supplies (للـ fallback)
    coingecko_supplies = await fetch_coingecko_supplies([])
    log.info("✅ Loaded %d supplies from CoinGecko", len(coingecko_supplies))
    
    # 3. إضافة عمود market_cap إذا غير موجود
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # نضيف الأعمدة الجديدة
    try:
        cur.execute("ALTER TABLE coin_profiles ADD COLUMN market_cap REAL")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE coin_profiles ADD COLUMN mc_tier_reason TEXT")
    except sqlite3.OperationalError:
        pass
    
    # 4. حلقة على كل العملات
    cur.execute("SELECT symbol, avg_daily_volume, manipulation_score, false_breakout_rate, "
                "behavior_pattern, volatility_class, spike_count FROM coin_profiles")
    rows = cur.fetchall()
    
    updated = 0
    promoted = 0  # العملات التي رُقّيت من Tier 4
    
    for row in rows:
        symbol, daily_vol, manip, false_bk, pattern, vol_class, spikes = row
        
        price = prices.get(symbol, 0)
        if price == 0:
            continue
        
        mc = calculate_market_cap(symbol, price, coingecko_supplies)
        if mc is None:
            continue
        
        # تصنيف Tier جديد بناءً على MC + Volume
        new_tier, reason = classify_by_market_cap(mc, daily_vol)
        
        # تحقق من شروط الرفض الأخرى
        safe = True
        rejection = ""
        
        if pattern == "dead":
            safe = False
            rejection = "Dead coin"
            new_tier = 4
        elif manip > 0.15:
            safe = False
            rejection = f"Manipulation {manip*100:.0f}%"
            new_tier = 4
        elif new_tier == 4:
            safe = False
            rejection = reason
        
        # تحديد threshold + leverage بناءً على Tier
        if new_tier == 1:
            threshold = 65.0
            leverage = 5
        elif new_tier == 2:
            threshold = 72.0
            leverage = 4
        elif new_tier == 3:
            threshold = 80.0
            leverage = 3
        else:
            threshold = 0
            leverage = 0
        
        # تعديلات للتقلب
        if vol_class == "extreme":
            threshold += 10
            leverage = max(1, leverage - 4)
        elif vol_class == "high":
            threshold += 5
            leverage = max(2, leverage - 2)
        elif vol_class == "low":
            threshold = max(60, threshold - 3)
            leverage = min(6, leverage + 2)
        
        # update DB
        cur.execute(
            "UPDATE coin_profiles SET "
            "market_cap = ?, mc_tier_reason = ?, "
            "tier = ?, safe_to_trade = ?, "
            "confidence_threshold = ?, recommended_leverage = ?, "
            "rejection_reason = ? "
            "WHERE symbol = ?",
            (round(mc), reason, new_tier, 1 if safe else 0,
             round(threshold, 1), leverage, rejection, symbol)
        )
        updated += 1
        if safe:
            promoted += 1
    
    conn.commit()
    conn.close()
    
    log.info("✅ Updated %d coins | Safe: %d", updated, promoted)
    return updated, promoted


# ═══════════════════════════════════════════════════════════════
# ─── CLI ──────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def cli_main():
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # اختبار عملة واحدة
        symbol = sys.argv[2] if len(sys.argv) > 2 else "BTCUSDT"
        prices = await fetch_all_prices()
        price = prices.get(symbol, 0)
        cg = await fetch_coingecko_supplies([])
        mc = calculate_market_cap(symbol, price, cg)
        if mc:
            tier, reason = classify_by_market_cap(mc, 1_000_000_000)
            print(f"\n{symbol}:")
            print(f"  Price: ${price:,.4f}")
            print(f"  Market Cap: ${mc/1_000_000:,.0f}M")
            print(f"  Tier: {tier} ({reason})")
        else:
            print(f"❌ Cannot calculate MC for {symbol}")
        return
    
    # Update كل profiles
    updated, safe = await update_profiles_with_market_cap()
    print(f"\n✅ Updated {updated} profiles | Now {safe} are safe to trade")


if __name__ == "__main__":
    asyncio.run(cli_main())
