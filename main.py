from __future__ import annotations
import asyncio, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from core.config import get_settings
from db.database import create_tables, seed_admin
from routers.auth import router as auth_router
from routers.binance import router as binance_router
from routers.binance_manual import router as binance_manual_router
from routers.signals import router as signals_router
from routers.trade import router as trade_router
from routers.wallet import router as wallet_router
from routers.subscription import router as sub_router
from routers.admin import router as admin_router
from routers.telegram import router as tg_router
from routers.ai import router as ai_router
from routers.prices import router as prices_router
from routers.ws import router as ws_router
from routers.live_positions import router as live_router
from routers.push import router as push_router
from services.telegram import TG

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s - %(message)s")
log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("WhaleX Prime starting up")
    create_tables()
    seed_admin()
    await TG.setup()
    from radars.futures.service import start_all_services
    from radars.futures.position_manager import run_position_manager, open_from_signal
    from routers.ws import registry
    async def _broadcast(data):
        try:
            # (أُزيل الإدراج المزدوج: المصدر — notify في المدير — يحفظ بالعربية والإنجليزية معاً)
            pass
        except Exception as _e:
            log.debug("notif save error: %s", _e)
        await registry.broadcast(data)
    asyncio.create_task(start_all_services(broadcast_fn=_broadcast, position_manager_fn=open_from_signal))
    asyncio.create_task(run_position_manager())
    from services.prices import start_price_stream
    asyncio.create_task(start_price_stream(), name="prices")
    # 🔔 حارس الربط — يفحص مفاتيح المشتركين كل ستّ ساعات ويُرشدهم.
    #    مقيس: 8 من 9 مشتركين عندهم خلل، وأغلبه صلاحية العقود الآجلة.
    try:
        from services.link_watcher import watcher_loop as _lw
        asyncio.create_task(_lw(), name="link_watcher")
    except Exception as _lwe:
        log.warning("حارس الربط: %s", _lwe)
    # 🛡️ حارس اليتيمة — لا مركز على المنصّة بلا حارس في النظام.
    #    مقيس: 10 صفقات بقيت مكشوفة على حسابين بعد فشل الإغلاق الصامت.
    try:
        from services.orphan_guard import guard_loop as _og
        asyncio.create_task(_og(), name="orphan_guard")
    except Exception as _oge:
        log.warning("حارس اليتيمة: %s", _oge)
    # 🚑 منقذ الهامش — يُحرّر رصيد المشترك حين يضيق تحت الاحتياطيّ.
    #    مقيس: مشترك رصيده 10.14$ بقي متاحاً 2.17$ بعد أربع صفقات.
    try:
        from services.margin_rescue import rescue_loop as _mr
        asyncio.create_task(_mr(), name="margin_rescue")
    except Exception as _mre:
        log.warning("منقذ الهامش: %s", _mre)
    # 🌡️ نبض السوق — يقيس ويُسجّل فقط، ولا يمنع إشارة ولا يُعدّل قراراً.
    #    حقول حالة السوق كانت ميّتة (regime فارغ في 91% من السجلّ)،
    #    فنجمع بيانات حقيقية أوّلاً ثم نقيس أثرها قبل أن نبني عليها.
    try:
        from services.market_pulse import pulse_loop as _mp
        asyncio.create_task(_mp(), name="market_pulse")
    except Exception as _mpe:
        log.warning("نبض السوق: %s", _mpe)
    # 🧹 تحرير الذاكرة المفكوكة كل عشر دقائق — بايثون يحتفظ بالساحات
    #    المحرّرة ولا يُعيدها للنظام، فتنمو RSS بلا سبب حقيقيّ.
    async def _trim_loop():
        import gc
        while True:
            await asyncio.sleep(600)
            try:
                from services.ccxt_pool import trim
                n = trim()
                log.info("🧹 تحرير الذاكرة: %d كائن", n)
            except Exception as _te:
                log.debug("تحرير: %s", _te)
    try:
        asyncio.create_task(_trim_loop(), name="mem_trim")
    except Exception:
        pass
    # 🔭 Explosion Scout — رادار الطبقة الثانية (وضع تجريبي، منفصل تماماً)
    try:
        from radars.explosion.scout import scout_loop
        asyncio.create_task(scout_loop(broadcast_fn=_broadcast, position_manager_fn=open_from_signal), name="explosion_scout")
        log.info("🔭 Explosion Scout started (وضع تجريبي)")
    except Exception as e:
        log.error("Explosion Scout failed to start: %s", e)

    # 📊 Report Engine — تقرير كل 8 ساعات للقناة
    try:
        from report_engine import report_loop
        from radars.futures.position_manager import notify
        asyncio.create_task(report_loop(notify_fn=notify), name="report")
        log.info("📊 Report Engine started (كل 8 ساعات)")
    except Exception as e:
        log.error("Report Engine failed to start: %s", e)
    log.info("WhaleX Prime ready")
    yield
    log.info("WhaleX Prime shutting down")

import logging as _lg
_lg.getLogger("httpx").setLevel(_lg.WARNING)
_lg.getLogger("httpcore").setLevel(_lg.WARNING)
_lg.getLogger("websockets").setLevel(_lg.WARNING)

app = FastAPI(title="WhaleX Prime", version="1.0.0", lifespan=lifespan)
settings = get_settings()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

from routers.scanner import router as scanner_router
from routers.diag import router as diag_router
app.include_router(diag_router)
from routers.sol_wallet_api import router as memewallet_router
app.include_router(memewallet_router)
from routers.profile import router as profile_router


@app.middleware("http")
async def _passive_profile(request, call_next):
    """يلتقط بيانات اتصال أي مشترك موثّق من أي طلب."""
    response = await call_next(request)
    try:
        path = request.url.path
        auth = request.headers.get("authorization") or ""
        if path.startswith("/api/") and auth.lower().startswith("bearer "):
            import jwt as _jwt
            from core.config import get_settings as _gs
            try:
                _p = _jwt.decode(auth.split(" ", 1)[1], _gs().secret_key, algorithms=["HS256"])
                _uid = _p.get("sub")
            except Exception:
                _uid = None
            if _uid:
                _ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() \
                    or (request.client.host if request.client else "")
                if _ip and not _ip.startswith("127."):
                    import asyncio as _aio
                    from routers.profile import capture as _cap
                    _aio.create_task(_cap(_uid, _ip, request.headers.get("user-agent") or ""))
    except Exception:
        pass
    return response


app.include_router(profile_router)
from routers.device import router as device_router
app.include_router(device_router)
from routers.support import router as support_router
app.include_router(support_router)
app.include_router(scanner_router)
app.include_router(auth_router)
app.include_router(binance_router)
app.include_router(binance_manual_router)
app.include_router(signals_router)
from routers.history import router as history_router
app.include_router(history_router)
app.include_router(trade_router)
app.include_router(wallet_router)
app.include_router(live_router)
app.include_router(push_router)
app.include_router(sub_router)
app.include_router(admin_router)
app.include_router(tg_router)
app.include_router(ai_router)
app.include_router(prices_router)
app.include_router(ws_router)
# 📊 أرقام عامّة لصفحة المقدّمة — بلا مصادقة
from routers.public_stats import router as public_router
app.include_router(public_router)
# 🎁 التجربة المجانية
from routers.trial import router as trial_router
app.include_router(trial_router)
# 🎁 نظام الإحالة
from routers.referral import router as ref_router
app.include_router(ref_router)

@app.get("/", include_in_schema=False)
async def root(): return RedirectResponse("/static/index.html", 302)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0", "telegram": bool(settings.telegram_bot_token)}

# 📎 ملفّات المحادثة (صور وفيديو)
import os as _os
_os.makedirs("/opt/whalex/static/uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="/opt/whalex/static/uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="/opt/whalex/static"), name="static")
