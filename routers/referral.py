"""🎁 نظام الإحالة — 15% من أول اشتراك · 10% لثلاثة تجديدات.

لكل مستخدم رمز فريد. من يسجّل به يُنسَب إليه، وتُحتسب العمولة
عند كل دفعة يدفعها المُحال (حتى أربع دفعات).
"""
import hashlib
import logging
import sqlite3
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException

from routers.auth import get_current_user

router = APIRouter(prefix="/api/referral", tags=["referral"])
log = logging.getLogger("referral")

DB = "/opt/whalex/db/whalex.db"
PCT_FIRST = 15.0        # أول اشتراك
PCT_RENEW = 10.0        # التجديدات
MAX_PAYOUTS = 4         # أول اشتراك + 3 تجديدات
MIN_WITHDRAW = 50.0     # حدّ السحب بالدولار


def _init():
    cn = sqlite3.connect(DB)
    cn.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            code       TEXT PRIMARY KEY,
            owner_id   TEXT UNIQUE,
            created_at INTEGER
        )""")
    cn.execute("""
        CREATE TABLE IF NOT EXISTS referral_links (
            referred_id TEXT PRIMARY KEY,
            referrer_id TEXT,
            code        TEXT,
            created_at  INTEGER
        )""")
    cn.execute("""
        CREATE TABLE IF NOT EXISTS referral_earnings (
            id          TEXT PRIMARY KEY,
            referrer_id TEXT,
            referred_id TEXT,
            amount      REAL,
            pct         REAL,
            payout_no   INTEGER,
            status      TEXT DEFAULT 'pending',
            created_at  INTEGER
        )""")
    cn.execute("""
        CREATE TABLE IF NOT EXISTS referral_withdrawals (
            id         TEXT PRIMARY KEY,
            user_id    TEXT,
            amount     REAL,
            wallet     TEXT,
            status     TEXT DEFAULT 'pending',
            created_at INTEGER,
            paid_at    INTEGER
        )""")
    for t, c in (("referral_links", "referrer_id"),
                 ("referral_earnings", "referrer_id"),
                 ("referral_withdrawals", "user_id")):
        cn.execute(f"CREATE INDEX IF NOT EXISTS ix_{t}_{c} ON {t}({c})")
    cn.commit()
    cn.close()


_init()


def _make_code(uid: str) -> str:
    """رمز قصير مقروء من معرّف المستخدم."""
    h = hashlib.sha256(str(uid).encode()).hexdigest()[:6].upper()
    return f"WX{h}"


def get_or_create_code(uid: str) -> str:
    cn = sqlite3.connect(DB)
    r = cn.execute("SELECT code FROM referrals WHERE owner_id=?", (str(uid),)).fetchone()
    if r:
        cn.close()
        return r[0]
    code = _make_code(uid)
    try:
        cn.execute("INSERT INTO referrals VALUES(?,?,?)",
                   (code, str(uid), int(time.time())))
        cn.commit()
    except Exception as e:
        log.debug("code %s: %s", uid, e)
    cn.close()
    return code


def register_referral(referred_id: str, code: str) -> bool:
    """يربط مستخدماً جديداً بمُحيله — يُستدعى عند التسجيل."""
    if not code:
        return False
    cn = sqlite3.connect(DB)
    r = cn.execute("SELECT owner_id FROM referrals WHERE code=?",
                   (str(code).strip().upper(),)).fetchone()
    if not r or str(r[0]) == str(referred_id):
        cn.close()
        return False
    try:
        cn.execute("INSERT OR IGNORE INTO referral_links VALUES(?,?,?,?)",
                   (str(referred_id), str(r[0]), code.upper(), int(time.time())))
        cn.commit()
        log.info("🎁 إحالة: %s → %s", code, str(referred_id)[:8])
        ok = True
    except Exception as e:
        log.debug("link: %s", e)
        ok = False
    cn.close()
    return ok


def record_commission(referred_id: str, amount_paid: float) -> None:
    """يُحتسب عند كل دفعة اشتراك — يُستدعى بعد تأكيد الدفع."""
    cn = sqlite3.connect(DB)
    r = cn.execute("SELECT referrer_id FROM referral_links WHERE referred_id=?",
                   (str(referred_id),)).fetchone()
    if not r:
        cn.close()
        return
    n = cn.execute("SELECT COUNT(*) FROM referral_earnings WHERE referred_id=?",
                   (str(referred_id),)).fetchone()[0]
    if n >= MAX_PAYOUTS:
        cn.close()
        return
    pct = PCT_FIRST if n == 0 else PCT_RENEW
    amt = round(float(amount_paid) * pct / 100.0, 2)
    cn.execute("INSERT INTO referral_earnings VALUES(?,?,?,?,?,?,?,?)",
               (str(uuid.uuid4()), str(r[0]), str(referred_id), amt, pct,
                n + 1, "pending", int(time.time())))
    cn.commit()
    cn.close()
    log.info("🎁 عمولة %.2f$ (%.0f%%) للمُحيل %s", amt, pct, str(r[0])[:8])


# ═══════════════════════ نقاط الـAPI ═══════════════════════

@router.get("/me")
async def my_referrals(user=Depends(get_current_user)):
    """رمزي · من سجّل · من اشترك · أرباحي."""
    uid = str(user["sub"])
    code = get_or_create_code(uid)
    cn = sqlite3.connect(DB)
    cn.row_factory = sqlite3.Row

    rows = cn.execute("""
        SELECT l.referred_id, l.created_at,
               u.username, u.email, u.tier,
               (SELECT COUNT(*) FROM referral_earnings e
                 WHERE e.referred_id = l.referred_id) AS payouts,
               (SELECT COALESCE(SUM(e.amount), 0) FROM referral_earnings e
                 WHERE e.referred_id = l.referred_id) AS earned
        FROM referral_links l
        LEFT JOIN users u ON u.id = l.referred_id
        WHERE l.referrer_id = ?
        ORDER BY l.created_at DESC
    """, (uid,)).fetchall()

    # 🔎 حالة كل مُحال: سجّل · في التجربة · مشترك · انتهت ولم يشترك
    now = int(time.time())
    people = []
    for r in rows:
        nm = (r["username"] or r["email"] or "")[:14]
        paid = (r["payouts"] or 0) > 0
        rid = r["referred_id"]

        tr = cn.execute("SELECT expires_at FROM trial_guard WHERE user_id=?",
                        (rid,)).fetchone()
        trial_left = 0
        if tr and tr[0]:
            trial_left = max(0, int((float(tr[0]) - now) / 86400))

        if paid:
            state = "subscribed"
        elif tr and float(tr[0] or 0) > now:
            state = "trial"
        elif tr:
            state = "trial_ended"
        else:
            state = "signed_up"

        people.append({
            "name": nm,
            "joined_at": r["created_at"],
            "state": state,
            "trial_days_left": trial_left,
            "paid": paid,
            "tier": r["tier"] or "free",
            "earned": round(r["earned"] or 0, 2),
        })

    tot = cn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM referral_earnings WHERE referrer_id=?",
        (uid,)).fetchone()[0] or 0
    wd = cn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM referral_withdrawals "
        "WHERE user_id=? AND status IN ('pending','paid')", (uid,)).fetchone()[0] or 0
    cn.close()

    return {
        "code": code,
        "signups": len(people),
        "trials": sum(1 for p in people if p["state"] == "trial"),
        "subscribers": sum(1 for p in people if p["paid"]),
        "total_earned": round(tot, 2),
        "withdrawn": round(wd, 2),
        "available": round(max(0, tot - wd), 2),
        "min_withdraw": MIN_WITHDRAW,
        "pct_first": PCT_FIRST,
        "pct_renew": PCT_RENEW,
        "people": people,
    }


@router.post("/withdraw")
async def withdraw(body: dict, user=Depends(get_current_user)):
    """طلب سحب — يُراجَع من الإدارة قبل الدفع."""
    uid = str(user["sub"])
    wallet = str(body.get("wallet") or "").strip()
    if len(wallet) < 20:
        raise HTTPException(400, "عنوان محفظة غير صالح")

    cn = sqlite3.connect(DB)
    tot = cn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM referral_earnings WHERE referrer_id=?",
        (uid,)).fetchone()[0] or 0
    wd = cn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM referral_withdrawals "
        "WHERE user_id=? AND status IN ('pending','paid')", (uid,)).fetchone()[0] or 0
    avail = tot - wd
    if avail < MIN_WITHDRAW:
        cn.close()
        raise HTTPException(400, f"الحدّ الأدنى للسحب {MIN_WITHDRAW:.0f}$")

    # 📋 البيانات مطلوبة عند السحب فقط — إنشاء الرابط يبقى بضغطة واحدة
    cn.row_factory = sqlite3.Row
    p = cn.execute("SELECT * FROM user_profiles WHERE user_id=?", (uid,)).fetchone()
    if p:
        k = p.keys()
        miss = [c for c in ("name", "phone", "country")
                if c not in k or not (p[c] or "").strip()]
    else:
        miss = ["name", "phone", "country"]
    if miss:
        cn.close()
        raise HTTPException(
            400, "أكمل بياناتك (الاسم · الهاتف · البلد) قبل طلب السحب")

    cn.execute("INSERT INTO referral_withdrawals VALUES(?,?,?,?,?,?,?)",
               (str(uuid.uuid4()), uid, round(avail, 2), wallet,
                "pending", int(time.time()), None))
    cn.commit()
    cn.close()
    log.info("🎁 طلب سحب %.2f$ من %s", avail, uid[:8])
    return {"success": True, "amount": round(avail, 2)}


@router.get("/profile")
async def get_profile(user=Depends(get_current_user)):
    """بيانات المُحيل — نحتاجها لإرسال أرباحه."""
    cn = sqlite3.connect(DB)
    cn.row_factory = sqlite3.Row
    r = cn.execute("SELECT * FROM user_profiles WHERE user_id=?",
                   (str(user["sub"]),)).fetchone()
    cn.close()
    if not r:
        return {"done": False}
    k = r.keys()
    g = lambda c: (r[c] if c in k else None) or ""
    done = all([g("name"), g("phone"), g("country"),
                g("usdt_wallet"), g("usdt_network")])
    return {
        "done": done,
        "name": g("name"), "email": g("email"), "phone": g("phone"),
        "country": g("country"), "birth_date": g("birth_date"),
        "usdt_wallet": g("usdt_wallet"), "usdt_network": g("usdt_network"),
    }


@router.post("/profile")
async def save_profile(body: dict, user=Depends(get_current_user)):
    """يحفظ البيانات — مطلوبة قبل إنشاء رابط الإحالة."""
    uid = str(user["sub"])
    req = ("name", "phone", "country", "usdt_wallet", "usdt_network")
    vals = {k: str(body.get(k) or "").strip() for k in
            req + ("email", "birth_date")}

    miss = [k for k in req if not vals[k]]
    if miss:
        raise HTTPException(400, "أكمل الحقول المطلوبة")
    if len(vals["usdt_wallet"]) < 20:
        raise HTTPException(400, "عنوان محفظة غير صالح")
    if vals["usdt_network"] not in ("TRC20", "BEP20", "ERC20", "SOL"):
        raise HTTPException(400, "شبكة غير مدعومة")

    cn = sqlite3.connect(DB)
    cn.execute("INSERT OR IGNORE INTO user_profiles(user_id) VALUES(?)", (uid,))
    cn.execute("""
        UPDATE user_profiles
           SET name=?, email=?, phone=?, country=?, birth_date=?,
               usdt_wallet=?, usdt_network=?, profile_done='1'
         WHERE user_id=?""",
        (vals["name"], vals["email"], vals["phone"], vals["country"],
         vals["birth_date"], vals["usdt_wallet"], vals["usdt_network"], uid))
    cn.commit()
    cn.close()
    log.info("🎁 حُفظت بيانات المُحيل %s", uid[:8])
    return {"success": True, "code": get_or_create_code(uid)}
