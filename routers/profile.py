"""👤 ملفات المستخدمين — موقع تقريبي، مزوّد الخدمة، الجهاز، والهاتف بموافقته."""
import sqlite3
import time
import logging
from fastapi import APIRouter, Request, Depends
from routers.auth import get_current_user
from pydantic import BaseModel

log = logging.getLogger("profile")
router = APIRouter()
DB = "/opt/whalex/db/whalex.db"


def _init():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS user_profiles(
        user_id TEXT PRIMARY KEY, name TEXT, phone TEXT,
        ip TEXT, prev_ip TEXT, country TEXT, country_code TEXT, flag TEXT,
        city TEXT, isp TEXT, ua TEXT, first_seen INTEGER, last_seen INTEGER,
        ip_changed_at INTEGER)""")
    c.commit(); c.close()


def _flag(cc: str) -> str:
    try:
        cc = (cc or "").upper()
        if len(cc) != 2 or not cc.isalpha():
            return "🌍"
        return chr(0x1F1E6 + ord(cc[0]) - 65) + chr(0x1F1E6 + ord(cc[1]) - 65)
    except Exception:
        return "🌍"


async def _geo(ip: str):
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,city,isp")
            j = r.json()
        if j.get("status") == "success":
            return {"country": j.get("country"), "country_code": j.get("countryCode"),
                    "city": j.get("city"), "isp": j.get("isp")}
    except Exception as e:
        log.debug("geo: %s", e)
    return {}


class TrackBody(BaseModel):
    user_id: str
    name: str = ""


@router.post("/api/profile/track")
async def track(body: TrackBody, request: Request, user=Depends(get_current_user)):
    """يسجّل بيانات الاتصال عند فتح التطبيق، وينبّه عند تغيّر العنوان."""
    _init()
    body.user_id = user.get("sub") or body.user_id
    if not body.name:
        try:
            from db.database import get_session, User
            _db = get_session()
            _u = _db.query(User).filter(User.id == body.user_id).first()
            body.name = (getattr(_u, "username", "") or "") if _u else ""
            _db.close()
        except Exception:
            pass
    ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() \
        or (request.client.host if request.client else "")
    ua = (request.headers.get("user-agent") or "")[:200]
    now = int(time.time())
    prev = None
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        row = c.execute("SELECT ip, country, country_code, flag, city, isp FROM user_profiles WHERE user_id=?",
                        (body.user_id,)).fetchone()
        prev = dict(row) if row else None
        c.close()
    except Exception:
        prev = None

    changed = bool(prev and prev.get("ip") and ip and prev["ip"] != ip)
    geo = {}
    if not prev or changed or not prev.get("country"):
        geo = await _geo(ip)
    country = geo.get("country") or (prev or {}).get("country")
    cc = geo.get("country_code") or (prev or {}).get("country_code")
    city = geo.get("city") or (prev or {}).get("city")
    isp = geo.get("isp") or (prev or {}).get("isp")
    flag = _flag(cc) if cc else ((prev or {}).get("flag") or "🌍")

    try:
        c = sqlite3.connect(DB)
        c.execute("""INSERT INTO user_profiles(user_id,name,ip,prev_ip,country,country_code,flag,city,isp,ua,first_seen,last_seen,ip_changed_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(user_id) DO UPDATE SET
                       name=COALESCE(NULLIF(excluded.name,''), user_profiles.name),
                       prev_ip=CASE WHEN excluded.ip <> user_profiles.ip THEN user_profiles.ip ELSE user_profiles.prev_ip END,
                       ip=excluded.ip, country=excluded.country, country_code=excluded.country_code,
                       flag=excluded.flag, city=excluded.city, isp=excluded.isp, ua=excluded.ua,
                       last_seen=excluded.last_seen,
                       ip_changed_at=CASE WHEN excluded.ip <> user_profiles.ip THEN excluded.last_seen ELSE user_profiles.ip_changed_at END""",
                  (body.user_id, body.name, ip, ip, country, cc, flag, city, isp, ua, now, now, now))
        c.commit(); c.close()
    except Exception as e:
        log.warning("track save: %s", e)

    if changed:
        try:
            from services.notifier import push_note
            await push_note("futures", "alert",
                            f"🌐 تغيّر عنوان اتصالك إلى {ip}\n"
                            "إن كنت تستخدم مفاتيح باينانس، حدّث قائمة العناوين المسموحة (IP whitelist) وإلا توقّف التداول الآلي.")
        except Exception:
            pass
        log.info("🌐 تغيّر IP لـ %s: %s ← %s", body.user_id, prev.get("ip"), ip)

    return {"ok": True, "flag": flag, "country": country, "city": city, "ip_changed": changed}


class PhoneBody(BaseModel):
    user_id: str
    phone: str


@router.post("/api/profile/phone")
async def save_phone(body: PhoneBody, user=Depends(get_current_user)):
    """يحفظ الرقم بعد مشاركته من المستخدم."""
    _init()
    body.user_id = user.get("sub") or body.user_id
    ph = "".join(ch for ch in body.phone if ch.isdigit() or ch == "+")[:20]
    if len(ph) < 7:
        return {"ok": False}
    try:
        c = sqlite3.connect(DB)
        c.execute("INSERT INTO user_profiles(user_id,phone,first_seen,last_seen) VALUES(?,?,?,?) "
                  "ON CONFLICT(user_id) DO UPDATE SET phone=excluded.phone",
                  (body.user_id, ph, int(time.time()), int(time.time())))
        c.commit(); c.close()
    except Exception as e:
        log.warning("phone: %s", e)
        return {"ok": False}
    return {"ok": True, "phone": ph}


@router.get("/api/profile/me")
async def me(user=Depends(get_current_user)):
    _init()
    user_id = user.get("sub")
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        row = c.execute("SELECT name, phone, flag, country, city FROM user_profiles WHERE user_id=?",
                        (user_id,)).fetchone()
        c.close()
        return dict(row) if row else {}
    except Exception:
        return {}


async def capture(user_id: str, ip: str, ua: str = ""):
    """تسجيل سلبي من أي طلب — يحلّ الموقع فقط عند عنوان جديد."""
    if not user_id or not ip:
        return
    _init()
    now = int(time.time())
    try:
        cn = sqlite3.connect(DB); cn.row_factory = sqlite3.Row
        row = cn.execute("SELECT ip, country FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
        prev = dict(row) if row else None
        cn.close()
    except Exception:
        prev = None
    need_geo = (not prev) or (prev.get("ip") != ip) or (not prev.get("country"))
    geo = await _geo(ip) if need_geo else {}
    cc = geo.get("country_code")
    name = ""
    if not prev:
        try:
            from db.database import get_session, User
            _db = get_session()
            _u = _db.query(User).filter(User.id == user_id).first()
            name = getattr(_u, "username", "") or ""
            _db.close()
        except Exception:
            name = ""
    try:
        cn = sqlite3.connect(DB)
        cn.execute("""INSERT INTO user_profiles(user_id,name,ip,prev_ip,country,country_code,flag,city,isp,ua,first_seen,last_seen,ip_changed_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                      ON CONFLICT(user_id) DO UPDATE SET
                        name=COALESCE(NULLIF(excluded.name,''), user_profiles.name),
                        prev_ip=CASE WHEN excluded.ip <> user_profiles.ip THEN user_profiles.ip ELSE user_profiles.prev_ip END,
                        ip=excluded.ip,
                        country=COALESCE(excluded.country, user_profiles.country),
                        country_code=COALESCE(excluded.country_code, user_profiles.country_code),
                        flag=COALESCE(NULLIF(excluded.flag,''), user_profiles.flag),
                        city=COALESCE(excluded.city, user_profiles.city),
                        isp=COALESCE(excluded.isp, user_profiles.isp),
                        ua=COALESCE(NULLIF(excluded.ua,''), user_profiles.ua),
                        last_seen=excluded.last_seen,
                        ip_changed_at=CASE WHEN excluded.ip <> user_profiles.ip THEN excluded.last_seen ELSE user_profiles.ip_changed_at END""",
                   (user_id, name, ip, ip, geo.get("country"), cc, _flag(cc) if cc else "",
                    geo.get("city"), geo.get("isp"), ua[:200], now, now, now))
        cn.commit(); cn.close()
    except Exception as e:
        log.debug("capture: %s", e)


def profile_of(user_id: str):
    """للوحة الإدارة."""
    _init()
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        row = c.execute("SELECT * FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
        c.close()
        return dict(row) if row else {}
    except Exception:
        return {}
