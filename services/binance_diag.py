"""🔑 تشخيص ربط المشترك — نعرف خطأه من لوحتنا بدل سؤاله.

المشكلة: مشتركون يربطون المفتاح ثم يقولون "لا يتداول"، ولا نعرف أين
الخلل — أفي الصلاحيات؟ أم قائمة العناوين؟ أم الرصيد؟ أم إعداداته؟

وباينانس تُتيح قراءة ذلك كلّه:
  GET /sapi/v1/account/apiRestrictions → صلاحيات المفتاح
  futures_account_balance              → رصيد الفيوتشر
"""
import logging

log = logging.getLogger("binance_diag")

SERVER_IP = "178.105.49.200"


def diagnose(user_id: str) -> dict:
    """يفحص ربط مشترك ويُعيد تقريراً بما ينقصه."""
    out = {
        "ok": False, "key_valid": False,
        "spot_enabled": None, "futures_enabled": None,
        "withdraw_enabled": None, "ip_restricted": None,
        "futures_balance": None, "spot_balance": None,
        "auto_trade_on": None,
        "problems": [], "advice": [], "error": None,
    }
    try:
        import sqlite3
        from services.binance_trader import decrypt

        c = sqlite3.connect("/opt/whalex/db/whalex.db")
        c.row_factory = sqlite3.Row
        r = c.execute("SELECT * FROM user_binance_credentials WHERE user_id=?",
                      (user_id,)).fetchone()
        c.close()
        if not r:
            out["error"] = "لم يربط مفتاحاً بعد"
            out["problems"].append("لا مفتاح مربوط")
            out["advice"].append("اطلب منه ربط مفتاح API من صفحة الإعدادات")
            return out

        d = dict(r)
        # 🎯 المشترك قد يريد السبوت وحده — فلا نحكم بالفيوتشر فقط.
        #    مقيس 12 سبتمبر: مشترك spot_auto_enabled=1 و auto_trade=0
        #    ولوحتنا تقول "التداول الآليّ مطفأ" وهو مفعّل للسبوت،
        #    وتطلب صلاحية فيوتشر لا يريدها اصلا.
        out["futures_auto_on"] = bool(d.get("auto_trade_enabled"))
        out["spot_auto_on"] = bool(d.get("spot_auto_enabled"))
        out["auto_trade_on"] = out["futures_auto_on"] or out["spot_auto_on"]
        out["wants_futures"] = out["futures_auto_on"]
        out["exchange"] = d.get("exchange") or "binance"
        out["account_type"] = d.get("account_type") or "futures"
        out["trade_amount"] = d.get("trade_amount_usdt")
        out["leverage"] = d.get("leverage")
        out["allowed_grades"] = d.get("allowed_grades")
        out["disabled_reason"] = d.get("disabled_reason")

        if (d.get("exchange") or "binance") != "binance":
            out["error"] = "منصّة غير باينانس — التشخيص لباينانس فقط"
            return out

        key = decrypt(d["api_key_encrypted"])
        sec = decrypt(d["api_secret_encrypted"])
        if not key or not sec:
            out["problems"].append("المفتاح المخزَّن تالف")
            return out

        from binance.client import Client
        cl = Client(key, sec)

        try:
            perm = cl._request_margin_api("get", "account/apiRestrictions",
                                          True, data={})
            out["key_valid"] = True
            out["spot_enabled"] = bool(perm.get("enableSpotAndMarginTrading"))
            out["futures_enabled"] = bool(perm.get("enableFutures"))
            out["withdraw_enabled"] = bool(perm.get("enableWithdrawals"))
            out["ip_restricted"] = bool(perm.get("ipRestrict"))
        except Exception as e:
            msg = str(e)
            out["error"] = msg[:120]
            if "Invalid API-key" in msg or "-2015" in msg:
                out["problems"].append("المفتاح مرفوض — أو الخادم غير مسموح")
                out["advice"].append(
                    "أضف " + SERVER_IP + " إلى العناوين المسموحة في مفتاح API")
            elif "signature" in msg.lower():
                out["problems"].append("السرّ (Secret) خاطئ")
                out["advice"].append("اطلب منه إعادة نسخ الـSecret كاملاً")
            else:
                out["problems"].append("فشل الاتصال بباينانس")
            return out

        # 🔬 التجربة الفعلية تُصحّح الحقل المُعلَن — مقيس 8 سبتمبر:
        #    أربعة مشتركين enableFutures=False والفيوتشر يعمل عندهم،
        #    فحُجبوا ظلماً عن التداول ووصلتهم رسالة خاطئة.
        try:
            for b in cl.futures_account_balance():
                if b.get("asset") == "USDT":
                    out["futures_balance"] = float(b.get("balance") or 0)
                    break
            # 🧪 قراءة الرصيد تنجح بصلاحية القراءة وحدها — فلا تُثبت
            #    صلاحية التداول. مقيس 12 سبتمبر: مشترك enableFutures=False
            #    ورصيده 147.71$ يُقرأ، ولوحتنا تقول "تداول فيوتشر ✓"
            #    بينما تغيير الرافعة يفشل بـ-2015. فكنّا نطمئنه كذبا.
            #    الاختبار الصحيح: ضبط الرافعة على قيمتها الحالية —
            #    اثر صفر ويحتاج صلاحية تداول.
            try:
                _lv_now = 0
                for _p in cl.futures_position_information(symbol="BTCUSDT"):
                    _lv_now = int(float(_p.get("leverage") or 0))
                    break
                cl.futures_change_leverage(symbol="BTCUSDT",
                                           leverage=_lv_now or 5)
                out["futures_enabled"] = True
            except Exception as _te:
                if "-2015" in str(_te) or "-4046" in str(_te):
                    if "-4046" in str(_te):
                        out["futures_enabled"] = True   # لا تغيير مطلوب
                    else:
                        out["futures_enabled"] = False
                        if out.get("wants_futures"):
                            out["problems"].append(
                                "صلاحية العقود الآجلة غير مفعّلة في المفتاح")
                            out["advice"].append(
                                "اطلب منه تفعيل «تمكين العقود الآجلة» في مفتاح API")
                else:
                    log.debug("fut perm test %s: %s", user_id[:8], str(_te)[:70])
        except Exception as e:
            if "-2015" in str(e):
                out["futures_enabled"] = False
                out["problems"].append("الفيوتشر غير مفعّل على هذا المفتاح")

        try:
            for b in cl.get_account().get("balances", []):
                if b.get("asset") == "USDT":
                    out["spot_balance"] = float(b.get("free") or 0)
                    break
        except Exception:
            pass

        if out["futures_enabled"] is False:
            out["problems"].append("صلاحية الفيوتشر غير مفعّلة")
            out["advice"].append(
                "باينانس ← API Management ← عدّل المفتاح ← فعّل Enable Futures")
        if out["ip_restricted"] is False:
            out["problems"].append("لا قائمة عناوين — المفتاح مكشوف")
            out["advice"].append(
                "فعّل Restrict access to trusted IPs وأضف " + SERVER_IP)
        if out["withdraw_enabled"]:
            out["problems"].append("صلاحية السحب مفعّلة — خطر أمنيّ")
            out["advice"].append("اطلب منه إلغاء Enable Withdrawals فوراً")
        # لا نشتكي من رصيد فيوتشر لمن يتداول السبوت وحده
        if (out.get("wants_futures")
                and out["futures_balance"] is not None
                and out["futures_balance"] < 10):
            out["problems"].append(
                "رصيد الفيوتشر ضئيل (%.2f$)" % out["futures_balance"])
            out["advice"].append(
                "يحوّل USDT من المحفظة الفورية إلى محفظة الفيوتشر")
        if out.get("spot_auto_on") and (out["spot_balance"] or 0) < 50:
            out["problems"].append(
                "رصيد السبوت دون 50$ (%.2f$)" % (out["spot_balance"] or 0))
            out["advice"].append("الحدّ الأدنى للصفقة في السبوت 50$")
        if not out["auto_trade_on"]:
            out["problems"].append("التداول الآليّ مُطفأ في إعداداته")
            out["advice"].append("اطلب منه تفعيل التداول الآليّ من الإعدادات")
        if d.get("disabled_reason"):
            out["problems"].append("مُعطَّل: " + str(d["disabled_reason"])[:50])

        out["ok"] = not out["problems"]
        return out

    except Exception as e:
        log.error("diagnose %s: %s", user_id, e)
        out["error"] = str(e)[:120]
        return out
