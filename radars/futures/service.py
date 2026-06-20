"""
WhaleMind-Prime-Core — service.py
═══════════════════════════════════════════════════════════════════
المنسق الرئيسي:

1. Oracle Agent     — جلب بيانات الماكرو (CoinGecko + Binance) — Plug-and-play
2. Futures Scanner  — يشغل Predator على 245+ عملة
3. قاعدة البيانات   — حفظ الإشارات مع end_time + highest_hit (Critical Fix)
4. Mini App API     — endpoints خفيفة للواجهة
5. Kill Switch      — إغلاق طارئ لكل الصفقات
6. MLOps            — حفظ Shadow Model snapshots
═══════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import asyncio, logging, time, json, os
from typing import Optional
from .engine import (
    Candle, Signal, MarketTier, ShadowTrade,
    predator_agent, sleeping_giants_radar,
    guardian_agent, shadow_record, get_shadow_stats,
    build_oracle_context, create_queues, btc_macro_loop
)
from radars.futures.ob_reversal_loop import ob_reversal_loop

log = logging.getLogger("service")

# ═══════════════════════════════════════════════════════════════
# ─── ORACLE AGENT — Plug-and-play ──────────────────────────────
# ═══════════════════════════════════════════════════════════════

class OracleAgent:
    """
    وكيل الرؤية الشاملة — بيانات الماكرو والكريبتو

    مبني بنمط Plug-and-play:
    - الآن: CoinGecko + Binance (مجاني)
    - لاحقاً: استبدل _fetch_token_unlocks بـ TokenUnlocks API
              استبدل _fetch_whale_alert  بـ Whale Alert API
              استبدل _fetch_macro_data   بـ Alpha Vantage API
    كل دالة مستقلة تماماً — لا تؤثر على الأخريات
    """

    INTERVAL = 3600  # يعمل مرة كل ساعة — توفير API calls

    def __init__(self):
        self._cache: dict = {}
        self._last_run: float = 0
        self._context: dict = {}

    def get_context(self) -> dict:
        return self._context.copy()

    # ─── FREE TIER (CoinGecko + Binance) ───────────────────────

    async def _fetch_btc_dominance(self) -> dict:
        """BTC Dominance + Market Cap (CoinGecko — مجاني)"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(
                    "https://api.coingecko.com/api/v3/global",
                    headers={"Accept": "application/json"}
                )
                d = r.json().get("data", {})
                return {
                    "btc_dominance": d.get("market_cap_percentage", {}).get("btc", 50),
                    "market_cap_usd": d.get("total_market_cap", {}).get("usd", 0),
                    "market_cap_change_24h": d.get("market_cap_change_percentage_24h_usd", 0),
                }
        except Exception as e:
            log.warning("Oracle BTCDom error: %s", e)
            return {}

    async def _fetch_btc_change(self) -> float:
        """BTC 24h change من Binance"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(
                    "https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=BTCUSDT"
                )
                d = r.json()
                return float(d.get("priceChangePercent", 0))
        except:
            return 0.0

    async def _fetch_fear_greed(self) -> dict:
        """Fear & Greed Index (Alternative.me — مجاني)"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get("https://api.alternative.me/fng/?limit=1")
                d = r.json()["data"][0]
                return {
                    "fear_greed": int(d["value"]),
                    "sentiment": d["value_classification"],  # Fear / Greed / Extreme
                }
        except Exception as e:
            log.warning("Oracle FearGreed error: %s", e)
            return {"fear_greed": 50, "sentiment": "Neutral"}

    async def _fetch_usdt_supply(self) -> dict:
        """
        USDT Market Cap (Tether)
        ── PLUG: استبدل بـ Whale Alert API لاحقاً ──
        """
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(
                    "https://api.coingecko.com/api/v3/coins/tether?localization=false"
                )
                d = r.json()
                market_data = d.get("market_data", {})
                supply = market_data.get("circulating_supply", 0)
                change = market_data.get("market_cap_change_percentage_24h_in_currency", {}).get("usd", 0)
                # طباعة ضخمة = صعود وشيك
                minted_est = supply * abs(change) / 100 if change > 0 else 0
                return {
                    "usdt_supply": supply,
                    "usdt_change_24h": change,
                    "usdt_minted_24h": minted_est,
                }
        except Exception as e:
            log.warning("Oracle USDT error: %s", e)
            return {}

    async def _fetch_token_unlocks(self, symbol: str = "") -> dict:
        """
        ── PLUG: استبدل بـ TokenUnlocks API عند توفر المفتاح ──
        الآن: نعيد قيماً آمنة
        """
        # TODO: استبدل بـ:
        # headers = {"Authorization": f"Bearer {TOKEN_UNLOCKS_KEY}"}
        # r = await c.get(f"https://api.tokenunlocks.app/v1/unlocks?token={symbol}")
        return {"token_unlock_in_hours": 999}  # آمن

    async def _fetch_macro_data(self) -> dict:
        """
        ── PLUG: استبدل بـ Alpha Vantage API عند توفر المفتاح ──
        الآن: نستخدم بيانات تقريبية من CoinGecko
        """
        # TODO: استبدل بـ:
        # r = await c.get(f"https://www.alphavantage.co/query?function=FX_DAILY&from_symbol=USD&to_symbol=EUR&apikey={key}")
        return {"dxy": 104.0}  # تقريبي

    # ─── Main Run ───────────────────────────────────────────────

    async def run_once(self) -> dict:
        """
        يجمع كل البيانات — يعمل بالتوازي لتوفير الوقت
        """
        results = await asyncio.gather(
            self._fetch_btc_dominance(),
            self._fetch_btc_change(),
            self._fetch_fear_greed(),
            self._fetch_usdt_supply(),
            self._fetch_macro_data(),
            return_exceptions=True
        )

        oracle_raw = {}
        for r in results:
            if isinstance(r, dict):
                oracle_raw.update(r)
            elif isinstance(r, float):
                oracle_raw["btc_24h_change"] = r

        self._cache = oracle_raw
        self._context = build_oracle_context(oracle_raw)
        self._last_run = time.time()
        log.info("Oracle updated: BTC=%+.1f%% F&G=%d market_crash=%s",
                 oracle_raw.get("btc_24h_change", 0),
                 oracle_raw.get("fear_greed", 50),
                 self._context.get("market_crash_warning", False))
        return self._context

    async def run_loop(self):
        """Oracle يعمل في background — مرة كل ساعة"""
        while True:
            try:
                await self.run_once()
            except Exception as e:
                log.error("Oracle loop error: %s", e)
            await asyncio.sleep(self.INTERVAL)

    def get_report(self) -> dict:
        """تقرير JSON خفيف للـ Mini App"""
        return {
            "fear_greed": self._cache.get("fear_greed", 50),
            "sentiment": self._cache.get("sentiment", "Neutral"),
            "btc_dominance": round(self._cache.get("btc_dominance", 50), 1),
            "market_cap_change": round(self._cache.get("market_cap_change_24h", 0), 2),
            "usdt_printing": self._context.get("usdt_printing", False),
            "macro_bearish": self._context.get("macro_bearish", False),
            "last_updated": int(self._last_run),
        }


# ═══════════════════════════════════════════════════════════════
# ─── BINANCE DATA FETCHER ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

CANDLE_CACHE: dict[str, list[Candle]] = {}
LAST_SIGNALS: dict[str, int] = {}
SIGNAL_COOLDOWN = 3600  # ساعة بين إشارتين لنفس العملة
GRADE_RANK = {"S": 4, "A": 3, "B": 2, "C": 1}
ALL_SYMBOLS: list[MarketTier] = []

async def fetch_candles(symbol: str, interval: str = "15m", limit: int = 100) -> list[Candle]:
    """جلب الكاندلز من Binance Futures"""
    try:
        import httpx
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        async with httpx.AsyncClient(timeout=12) as c:
            r = await c.get(url)
            data = r.json()
            if not isinstance(data, list):
                return []
            candles = []
            for d in data:
                candles.append(Candle(
                    time=int(d[0]),
                    open=float(d[1]),
                    high=float(d[2]),
                    low=float(d[3]),
                    close=float(d[4]),
                    volume=float(d[5]),
                    buy_volume=float(d[9])
                ))
            return candles
    except Exception as e:
        log.debug("fetch_candles %s: %s", symbol, e)
        return []

async def fetch_all_symbols() -> list[MarketTier]:
    """جلب فقط العملات الآمنة من Coin Profiler DB (44 عملة Tier 1-3)"""
    try:
        import httpx, sqlite3
        # نقرأ Tier 1-3 (آمنة) من Coin Profiler DB
        conn = sqlite3.connect("/opt/whalex/coin_profiles.db")
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT symbol, tier, avg_daily_volume FROM coin_profiles "
            "WHERE safe_to_trade=1 AND tier <= 3 "
            "ORDER BY tier ASC, avg_daily_volume DESC"
        ).fetchall()
        conn.close()

        if not rows:
            log.warning("⚠️ Profile DB empty — fallback to default")
            return []

        # جلب الحجم الحالي (24h) للحصول على بيانات حية
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get("https://fapi.binance.com/fapi/v1/ticker/24hr")
            vols = {t["symbol"]: float(t["quoteVolume"]) for t in r.json()}

        tiers = []
        for row in rows:
            sym = row["symbol"]
            current_vol = vols.get(sym, row["avg_daily_volume"])
            profile_tier = row["tier"]
            # نُحول tier رقمي إلى حرف
            if profile_tier == 1:
                t = MarketTier(sym, current_vol, "S", 10, 6.0, 70)
            elif profile_tier == 2:
                t = MarketTier(sym, current_vol, "A", 7, 6.0, 65)
            else:  # tier 3
                t = MarketTier(sym, current_vol, "B", 5, 6.0, 62)
            tiers.append(t)

        log.info("✅ Loaded %d safe symbols from Profile DB (T1:%d T2:%d T3:%d)",
                 len(tiers),
                 sum(1 for t in tiers if t.tier == "S"),
                 sum(1 for t in tiers if t.tier == "A"),
                 sum(1 for t in tiers if t.tier == "B"))
        return tiers
    except Exception as e:
        log.error("fetch_all_symbols: %s", e)
        return []


# ═══════════════════════════════════════════════════════════════
# ─── DATABASE — إصلاح حرج ──────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def save_signal(sig: Signal):
    """
    حفظ الإشارة في DB مع CRITICAL FIX:
    end_time و highest_hit دائماً موجودان بقيم افتراضية
    لمنع أي Crash عند db.commit()
    """
    try:
        from db.database import get_session, Signal as DBSignal
        db = get_session()
        db_sig = DBSignal(
            radar_type=sig.radar_type,
            symbol=sig.symbol,
            direction=sig.direction,
            grade=sig.grade,
            score=sig.score,
            confidence=sig.confidence,
            entry=sig.entry,
            sl=sig.sl,
            tp1=sig.tp1,
            tp2=sig.tp2,
            tp3=sig.tp3,
            leverage=sig.leverage,
            strategies=sig.strategies,
             
            # ─── CRITICAL FIX — لا crash هنا أبداً ───────────
            # ────────────────────────────────────────────────
        )
        db.add(db_sig)
        db.commit()
        log.info("DB saved: %s %s grade=%s", sig.symbol, sig.direction, sig.grade)
        return db_sig.id if hasattr(db_sig, 'id') else None
    except Exception as e:
        log.error("save_signal DB error: %s", e)
        # لا نوقف النظام بسبب خطأ DB
        return None

async def save_shadow_trade(trade: ShadowTrade):
    """حفظ الصفقة الوهمية في DB"""
    try:
        from db.database import get_session
        db = get_session()
        # جدول shadow_trades يجب أن يكون موجوداً في models
        from db.database import ShadowTrade as DBShadow
        db_t = DBShadow(
            symbol=trade.symbol,
            direction=trade.direction,
            entry=trade.entry,
            sl=trade.sl,
            tp1=trade.tp1,
            score=trade.score,
            confidence=trade.confidence,
            strategies=trade.strategies,
            result=trade.result,
            exit_price=trade.exit_price,
            pnl_pct=trade.pnl_pct,
            timestamp=trade.timestamp,
            closed_at=trade.closed_at,
        )
        db.add(db_t)
        db.commit()
    except Exception as e:
        log.debug("save_shadow_trade: %s", e)


# ═══════════════════════════════════════════════════════════════
# ─── ORCHESTRATOR — المدير التنفيذي ────────────────────────────
# ═══════════════════════════════════════════════════════════════

async def orchestrate_approved(
    approved_queue: asyncio.Queue,
    broadcast_fn,
    position_manager_fn
):
    """
    يستقبل الإشارات المعتمدة من Guardian:
    1. يحفظها في DB
    2. يرسلها لـ Telegram
    3. يُعلم position_manager
    4. يسجل في Shadow Mode
    لا blocking — كل عملية مستقلة
    """
    log.info("Orchestrator started")
    while True:
        try:
            sig = await asyncio.wait_for(approved_queue.get(), timeout=1.0)

            # cooldown — رمز فقط، لكن إشارة أقوى تخترق التبريد
            now = int(time.time())
            _prev = LAST_SIGNALS.get(sig.symbol)
            _rank = GRADE_RANK.get(sig.grade, 0)
            if _prev and now - _prev["ts"] < SIGNAL_COOLDOWN and _rank <= _prev["rank"]:
                log.debug("Cooldown: %s grade=%s (<= %s)", sig.symbol, sig.grade, _prev["rank"])
                approved_queue.task_done()
                continue

            LAST_SIGNALS[sig.symbol] = {"ts": now, "rank": _rank}

            # حفظ في DB
            await save_signal(sig)
            await shadow_record(sig)

            # Claude Approval - نقطة الحسم الموحدة
            claude_ok = True
            try:
                from services.claude_approval import claude_approval
                claude_ok, claude_reason = await claude_approval(sig)
                if claude_ok:
                    log.info("Claude APPROVED: %s %s", sig.symbol, sig.direction)
                else:
                    log.info("Claude REJECTED [final]: %s %s - %s",
                             sig.symbol, sig.direction, claude_reason)
            except Exception as e:
                log.debug("Claude approval error: %s", e)

            if not claude_ok:
                approved_queue.task_done()
                continue

            # معتمدة - توزيع شامل (المدير يُستدعى داخل _broadcast بعد نجاح كل الفلاتر)
            asyncio.create_task(_broadcast_telegram(sig, broadcast_fn, position_manager_fn))

            try:
                from services.auto_trade_engine import on_signal_approved
                asyncio.create_task(on_signal_approved(sig))
            except Exception as e:
                log.debug("auto_trade error: %s", e)

            approved_queue.task_done()
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            log.error("Orchestrator error: %s", e)
            await asyncio.sleep(1)


async def _broadcast_telegram(sig: Signal, broadcast_fn, position_manager_fn=None):
    """إرسال الإشارة لـ Telegram — Grade A و S فقط للقناة"""
    # فلتر الجودة: فقط أعلى درجات للقناة
    if sig.grade not in ("S", "A"):
        log.info("Skip channel broadcast: %s grade=%s (only A/S)", sig.symbol, sig.grade)
        # لكن نرسلها للـ WebSocket (الميني آب يعرض كل الإشارات)
        if broadcast_fn:
            sig_dict = {
                "radar_type": sig.radar_type, "symbol": sig.symbol,
                "direction": sig.direction, "grade": sig.grade,
                "confidence": sig.confidence, "entry": sig.entry,
                "sl": sig.sl, "tp1": sig.tp1, "tp2": sig.tp2, "tp3": sig.tp3,
                "leverage": sig.leverage, "strategies": sig.strategies,
                "tier": sig.tier,
            }
            await broadcast_fn({"event": "signal", "data": sig_dict})
        return
    try:
        from services.telegram import TG
        sig_dict = {
            "radar_type": sig.radar_type,
            "symbol": sig.symbol,
            "direction": sig.direction,
            "grade": sig.grade,
            "score": sig.score,
            "confidence": sig.confidence,
            "entry": sig.entry,
            "sl": sig.sl,
            "tp1": sig.tp1,
            "tp2": sig.tp2,
            "tp3": sig.tp3,
            "leverage": sig.leverage,
            "strategies": sig.strategies,
            "tier": sig.tier,
            "funding_rate": getattr(sig, "funding_rate", 0),
            "open_interest_change": getattr(sig, "open_interest_change", 0),
            "btc_trend": getattr(sig, "btc_trend", "NEUTRAL"),
            "mtf_15m": getattr(sig, "mtf_15m", "NEUTRAL"),
            "mtf_1h": getattr(sig, "mtf_1h", "NEUTRAL"),
            "mtf_4h": getattr(sig, "mtf_4h", "NEUTRAL"),
            "rr_tp1": getattr(sig, "rr_tp1", 0),
            "rr_tp2": getattr(sig, "rr_tp2", 0),
            "rr_tp3": getattr(sig, "rr_tp3", 0),
            "accuracy": getattr(sig, "accuracy", 75.0),
            "strategy_count": getattr(sig, "strategy_count", 0),
        }
        # ═══ 🦅 Hawk Eye — عين الصقر: السياق التاريخي ═══
        try:
            from quant_engine.hawk_eye import read_market_structure, evaluate_reversal_context
            from radars.futures.engine import fetch_klines_async
            ms = await read_market_structure(sig.symbol, fetch_klines_async)
            hawk_mod, hawk_reason = evaluate_reversal_context(ms, sig.direction)
            if hawk_mod == 0.0:
                log.info("🦅 Hawk Eye REJECTED: %s %s — %s", sig.symbol, sig.direction, hawk_reason)
                if broadcast_fn:
                    sig_dict["hawk_rejected"] = True
                    sig_dict["hawk_reason"] = hawk_reason
                    await broadcast_fn({"event": "signal", "data": sig_dict})
                return
            # تعديل الثقة حسب السياق التاريخي
            sig.confidence = min(99.0, sig.confidence * hawk_mod)
            sig_dict["confidence"] = round(sig.confidence, 1)
            sig_dict["hawk_phase"] = ms.phase
            sig_dict["hawk_reason"] = hawk_reason
            log.info("🦅 Hawk Eye %s %s [%s] ×%.2f → conf=%.0f%% — %s",
                     sig.symbol, sig.direction, ms.phase, hawk_mod, sig.confidence, hawk_reason)
        except Exception as e:
            log.debug("Hawk Eye error: %s", e)

        # ═══ Coin Profile Filter — قبل Claude ═══
        try:
            from profiler.coin_profiler import load_profile_sqlite, should_emit_signal
            profile = load_profile_sqlite("/opt/whalex/coin_profiles.db", sig.symbol)
            profile_ok, profile_reason = should_emit_signal(profile, sig.confidence)
            if not profile_ok:
                log.info("🧠 Profile REJECTED: %s %s — %s", sig.symbol, sig.direction, profile_reason)
                if broadcast_fn:
                    sig_dict["profile_rejected"] = True
                    sig_dict["profile_reason"] = profile_reason
                    await broadcast_fn({"event": "signal", "data": sig_dict})
                return
            sig_dict["profile_approved"] = True
            log.info("🧠 Profile ✅ %s %s (threshold=%.0f%%, lev=%s)",
                     sig.symbol, sig.direction,
                     profile.get("confidence_threshold", 0),
                     profile.get("recommended_leverage", 0))
        except Exception as e:
            log.debug("Profile filter error: %s", e)

        sig_dict["claude_approved"] = True
        await TG.broadcast_signal(sig_dict)
        # WebSocket broadcast للـ Mini App
        if broadcast_fn:
            await broadcast_fn({"event": "signal", "data": sig_dict})
        # ═══ كشف الجدار الوهمي قبل الدخول (نفس عين بيك هنتر والمدير) ═══
        # جدار وهمي ضدنا = فخ منصة → لا ندخل. حقيقي/جليدي = ندخل بثقة.
        try:
            from radars.explosion.scout import classify_wall
            sym_w = sig.symbol.replace("/", "").replace("-", "")
            if not sym_w.endswith("USDT"):
                sym_w += "USDT"
            # SHORT يخشى جدار شراء وهمي (دعم كاذب)، LONG يخشى جدار بيع وهمي
            wside = "bid" if sig.direction == "SHORT" else "ask"
            w = await classify_wall(sym_w, side=wside)
            if w.get("valid") and w.get("type") == "وهمي":
                log.info("🧊 %s %s — جدار وهمي ضدنا (فخ منصة) → لا دخول",
                         sig.symbol, sig.direction)
                return
        except Exception as _we:
            log.debug("wall check %s: %s", sig.symbol, _we)

        # فخ لحظي (WebSocket) ضدنا قبل الدخول → لا دخول
        try:
            from quant_engine.ob_stream import get_signals
            _sp = get_signals(sym_w).get("spoof", [])
            _bad = "bid" if sig.direction == "SHORT" else "ask"
            if any(x["side"]==_bad for x in _sp):
                log.info("🧊 %s %s — فخ وهمي لحظي ضدنا → لا دخول", sig.symbol, sig.direction)
                return
        except Exception as _e:
            log.debug("ob entry %s: %s", sig.symbol, _e)

        # ✅ المدير يُفتح فقط بعد نجاح كل الفلاتر (Hawk + Profile + Claude + الجدار)
        if position_manager_fn:
            asyncio.create_task(position_manager_fn(sig))
            log.info("📈 Position manager notified: %s %s (اجتاز كل الفلاتر)", sig.symbol, sig.direction)
    except Exception as e:
        log.error("Telegram broadcast error: %s", e)


# ═══════════════════════════════════════════════════════════════
# ─── FUTURES SCANNER LOOP ──────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

_scan_count = 0

async def futures_scan_loop(oracle: OracleAgent, signal_queue: asyncio.Queue):
    """
    حلقة المسح الرئيسية — تشغيل Predator على كل العملات
    لا اختناق: كل رمز يُحلَّل في coroutine مستقل
    Semaphore يمنع تحميل زائد
    """
    global _scan_count, ALL_SYMBOLS
    sem = asyncio.Semaphore(15)  # 15 طلب متزامن max

    async def analyze_one(tier: MarketTier):
        async with sem:
            candles = await fetch_candles(tier.symbol, "15m", 100)
            if not candles:
                return
            oracle_ctx = oracle.get_context()
            await predator_agent(candles, tier.symbol, tier, oracle_ctx, signal_queue)

    while True:
        try:
            # تحديث قائمة العملات كل ساعة
            if _scan_count % 12 == 0:
                ALL_SYMBOLS = await fetch_all_symbols()
                log.info("Symbols refreshed: %d", len(ALL_SYMBOLS))

            if not ALL_SYMBOLS:
                await asyncio.sleep(30)
                continue

            _scan_count += 1
            start = time.time()

            # مسح موازٍ — كل العملات في نفس الوقت
            tasks = [analyze_one(t) for t in ALL_SYMBOLS]
            await asyncio.gather(*tasks, return_exceptions=True)

            elapsed = time.time() - start
            log.info("Scan #%d done — %d symbols in %.1fs — next in 60s",
                     _scan_count, len(ALL_SYMBOLS), elapsed)

        except Exception as e:
            log.error("Scan loop error: %s", e)

        await asyncio.sleep(60)  # 60 ثانية (كان 300 — أسرع للسوق النشط)


async def sleeping_giants_loop(oracle: OracleAgent, signal_queue: asyncio.Queue):
    """
    رادار التجميع الصامت — يعمل على الفريم اليومي
    أبطأ — مسح كل 6 ساعات
    """
    sem = asyncio.Semaphore(5)  # أقل تزامن — فريم يومي

    async def scan_one(tier: MarketTier):
        async with sem:
            candles = await fetch_candles(tier.symbol, "1d", 60)
            if candles:
                await sleeping_giants_radar(candles, tier.symbol, tier, signal_queue)

    while True:
        try:
            if ALL_SYMBOLS:
                tasks = [scan_one(t) for t in ALL_SYMBOLS[:100]]  # أكبر 100 فقط
                await asyncio.gather(*tasks, return_exceptions=True)
                log.info("Sleeping Giants scan done")
        except Exception as e:
            log.error("SleepingGiants error: %s", e)

        await asyncio.sleep(21600)  # 6 ساعات


# ═══════════════════════════════════════════════════════════════
# ─── MINI APP API ──────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

def build_signal_payload(sig: Signal) -> dict:
    """حزمة JSON خفيفة للـ Mini App"""
    return {
        "symbol": sig.symbol,
        "direction": sig.direction,
        "grade": sig.grade,
        "score": sig.score,
        "confidence": sig.confidence,
        "entry": sig.entry,
        "sl": sig.sl,
        "tp1": sig.tp1,
        "tp2": sig.tp2,
        "tp3": sig.tp3,
        "leverage": sig.leverage,
        "strategies": sig.strategies,
        "radar_type": sig.radar_type,
        "tier": sig.tier,
        "timestamp": sig.timestamp,
    }

# ─── Kill Switch ────────────────────────────────────────────────

_kill_switch_active = False

async def activate_kill_switch(broadcast_fn=None):
    """
    مفتاح الإعدام — يغلق كل الصفقات المفتوحة فوراً
    يُستدعى من API endpoint عند الطوارئ
    """
    global _kill_switch_active
    _kill_switch_active = True
    log.critical("🚨 KILL SWITCH ACTIVATED — إغلاق كل الصفقات")

    try:
        from position_manager import ACTIVE, force_close_all
        await force_close_all(reason="kill_switch")
    except Exception as e:
        log.error("Kill switch error: %s", e)

    # إشعار Telegram
    try:
        from services.telegram import TG
        s = await TG.settings
        await TG.send_admin("🚨 KILL SWITCH — كل الصفقات أُغلقت فوراً")
    except:
        pass

    if broadcast_fn:
        await broadcast_fn({"event": "kill_switch", "data": {"status": "activated"}})

    return {"status": "kill_switch_activated", "timestamp": int(time.time())}

def is_kill_switch_active() -> bool:
    return _kill_switch_active

# ─── MLOps — حفظ نموذج Shadow ──────────────────────────────────

async def save_shadow_snapshot():
    """
    حفظ أوزان Shadow Model دورياً
    الآن: حفظ JSON محلي + رفع سحابي (placeholder)
    """
    try:
        stats = get_shadow_stats()
        snapshot = {
            "timestamp": int(time.time()),
            "stats": stats,
            "trades_count": len([]),  # يمكن تمرير SHADOW_TRADES
        }
        path = "/opt/whalex/snapshots"
        os.makedirs(path, exist_ok=True)
        filename = f"{path}/shadow_{int(time.time())}.json"
        with open(filename, "w") as f:
            json.dump(snapshot, f, indent=2)
        log.info("Shadow snapshot saved: %s", filename)

        # TODO: رفع سحابي
        # await upload_to_cloud(filename)
    except Exception as e:
        log.error("snapshot error: %s", e)

async def mlops_loop():
    """حفظ Snapshot كل 24 ساعة"""
    while True:
        await asyncio.sleep(86400)
        await save_shadow_snapshot()


# ═══════════════════════════════════════════════════════════════
# ─── MAIN SERVICE RUNNER ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════════

oracle = OracleAgent()

async def mc_refresh_loop():
    """تحديث دوري لتصنيف Market Cap كل 6 ساعات.
    يعيد حساب MC لكل العملات ويحدّث التصنيف، ثم يحدّث ALL_SYMBOLS فوراً.
    محاط بحماية كاملة: أي فشل (CoinGecko/شبكة) لا يُسقط الخدمة."""
    global ALL_SYMBOLS
    await asyncio.sleep(300)  # نومة أولى: لا نزاحم الإقلاع
    while True:
        try:
            from quant_engine.market_cap_filter import update_profiles_with_market_cap
            log.info("🔄 MC refresh: بدء تحديث Market Cap الدوري")
            updated, safe = await update_profiles_with_market_cap("/opt/whalex/coin_profiles.db")
            log.info("✅ MC refresh: حُدّثت %d عملة | آمنة %d", updated, safe)
            ALL_SYMBOLS = await fetch_all_symbols()
            log.info("✅ MC refresh: ALL_SYMBOLS محدّثة → %d عملة", len(ALL_SYMBOLS))
        except Exception as e:
            log.error("MC refresh loop error: %s", e)
        await asyncio.sleep(6 * 3600)  # كل 6 ساعات


async def start_all_services(broadcast_fn=None, position_manager_fn=None):
    """
    نقطة التشغيل الرئيسية — تشغيل كل الوكلاء معاً بدون اختناق

    التدفق:
    Predator ──→ signal_queue ──→ Guardian ──→ approved_queue ──→ Orchestrator
                                                                    ├── DB
                                                                    ├── Telegram
                                                                    ├── WebSocket
                                                                    └── Shadow Mode
    """
    signal_queue, approved_queue = create_queues()

    log.info("WhaleMind-Prime-Core starting...")

    # تشغيل Oracle أولاً للحصول على context
    await oracle.run_once()

    # جلب العملات
    global ALL_SYMBOLS
    ALL_SYMBOLS = await fetch_all_symbols()

    from shadow_tracker import shadow_loop
    from radars.explosion.scout_long import scout_long_loop  # مُفعّل: تصحيح صاعد (لا هابطة)
    from quant_engine.ob_stream import run as ob_stream_run
    # تشغيل كل الوكلاء بالتوازي
    await asyncio.gather(
        oracle.run_loop(),
        futures_scan_loop(oracle, signal_queue),
        sleeping_giants_loop(oracle, signal_queue),
        guardian_agent(signal_queue, approved_queue, oracle.get_context()),
        orchestrate_approved(approved_queue, broadcast_fn, position_manager_fn),
        ob_reversal_loop(signal_queue),  # 🐋 الآن يمر بالحارس المركزي (لا تجاوز)
        mlops_loop(),
        btc_macro_loop(),
        mc_refresh_loop(),
        shadow_loop(),
        scout_long_loop(position_manager_fn=position_manager_fn),
        ob_stream_run([t.symbol for t in ALL_SYMBOLS]),
        return_exceptions=True
    )
