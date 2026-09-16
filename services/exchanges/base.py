"""🔌 الواجهة الأساسية للمنصّات — العقد الذي تلتزم به كل منصّة

الفلسفة: كل منصّة ملف مستقلّ يرث هذه الواجهة ويُعيد تعريف ما يختلف فيه فقط.
  • إضافة منصّة جديدة = ملف واحد جديد · صفر تعديل على القائم
  • عطل في منصّة لا يمسّ غيرها
  • الاختبار لكل منصّة على حدة

القاعدة تفعل 95% عبر CCXT، والمُهايئ يغطّي الاستثناءات.
"""
from abc import ABC
import logging

log = logging.getLogger("exchange")


class ExchangeAdapter(ABC):
    id: str = ""
    name_ar: str = ""
    name_en: str = ""      # 🌐 أوضح في الإشارات
    needs_passphrase: bool = False
    supports_spot: bool = True
    supports_futures: bool = True
    futures_suffix: bool = True

    def symbol(self, sym: str, futures: bool = True) -> str:
        """BTCUSDT → BTC/USDT:USDT (فيوتشر) أو BTC/USDT (سبوت)."""
        s = (sym or "").upper().replace("/", "").replace(":USDT", "")
        for q in ("USDT", "USDC", "BUSD"):
            if s.endswith(q):
                base = s[: -len(q)]
                if futures and self.futures_suffix:
                    return f"{base}/{q}:{q}"
                return f"{base}/{q}"
        return sym

    def _options(self, futures: bool) -> dict:
        return {"defaultType": "swap" if futures else "spot"}

    supports_testnet: bool = True   # 📊 مقيس: 6 من 7 تدعمها (مكسي لا)

    def client(self, key: str, secret: str, passphrase: str = "",
               futures: bool = True, testnet: bool = False):
        import ccxt
        # 🔑 لا نُمرّر مفتاحاً فارغاً — باينانس ترفضه بـAuthenticationError
        #    حتى لقراءة الشموع العامّة، فكانت 333 عملة تُرجع "بلا داتا".
        #    مقيس: بلا apiKey تعمل، ومعه فارغاً تفشل. والستّ الأخرى تعمل بالحالتين.
        cfg = {
            "enableRateLimit": True, "timeout": 20000,
            "options": self._options(futures),
        }
        if key:
            cfg["apiKey"] = key
        if secret:
            cfg["secret"] = secret
        if self.needs_passphrase and passphrase:
            cfg["password"] = passphrase
        c = getattr(ccxt, self.id)(cfg)
        # 🧪 الوضع التجريبي — مال وهمي، تنفيذ حقيقي
        if testnet and self.supports_testnet:
            try:
                c.set_sandbox_mode(True)
                log.info("🧪 %s: وضع تجريبي", self.name_ar)
            except Exception as e:
                log.warning("🧪 %s لا يدعم التجريبي: %s", self.name_ar, e)
        return c

    def set_leverage(self, c, sym: str, lev: float, futures: bool = True) -> bool:
        if not futures:
            return True
        try:
            c.set_leverage(int(lev), self.symbol(sym, True))
            return True
        except Exception as e:
            log.debug("%s رافعة %s: %s", self.id, sym, e)
            return False

    def open(self, c, sym: str, side: str, usdt: float,
             lev: float = 1.0, futures: bool = True,
             sig_px: float = 0.0, max_slip: float = 0.6) -> dict:
        s = self.symbol(sym, futures)
        try:
            if futures:
                self.set_leverage(c, sym, lev, futures)
            px = float((c.fetch_ticker(s) or {}).get("last") or 0)
            if px <= 0:
                return {"ok": False, "error": "سعر غير متاح"}
            # 🎯 حارس الانزلاق — كان يضع الحدّ عند السعر الحيّ وقت
            #    التنفيذ لا سعر الاشارة، فيدخل المشترك اعلى.
            #    مقيس 15 سبتمبر: ASTRUSDT +2.63% و POLYXUSDT +1.87%.
            try:
                _sp = float(sig_px or 0)
            except Exception:
                _sp = 0.0
            if _sp > 0:
                _slip = (px - _sp) / _sp * 100.0
                _bad = _slip > max_slip if side.upper() in ("LONG", "BUY") \
                    else -_slip > max_slip
                if _bad:
                    return {"ok": False,
                            "error": "السعر هرب %.2f%%" % abs(_slip)}
                if side.upper() in ("LONG", "BUY"):
                    px = min(px, _sp)
                else:
                    px = max(px, _sp)
            qty = float(c.amount_to_precision(
                s, (usdt * (lev if futures else 1.0)) / px))
            # 🎯 حدّ اولاً — لا انزلاق. والسعر من هذه المنصّة لا من باينانس.
            if not _os.path.exists(EXCH_LIMIT_OFF):
                _o, _why, _fill = _limit_entry(
                    c, s, self._side(side), qty,
                    float(c.price_to_precision(s, px)),
                    self._open_params(futures), self.name_ar)
                if not _o:
                    return {"ok": False, "error": _why or "limit not filled"}
                return {"ok": True, "id": str(_o.get("id", "")),
                        "qty": qty, "price": _fill or px}
            o = c.create_order(s, "market", self._side(side), qty,
                               None, self._open_params(futures))
            log.info("🔌 %s فتح %s %s qty=%s", self.name_ar, s, side, qty)
            return {"ok": True, "id": str(o.get("id", "")), "qty": qty, "price": px}
        except Exception as e:
            log.error("🔌 %s فتح %s: %s", self.name_ar, s, e)
            return {"ok": False, "error": str(e)}

    def _side(self, side: str) -> str:
        return "buy" if (side or "").upper() in ("LONG", "BUY") else "sell"

    def _open_params(self, futures: bool) -> dict:
        return {}

    def close(self, c, sym: str, futures: bool = True, qty: float = 0.0) -> dict:
        s = self.symbol(sym, futures)
        try:
            if futures:
                amt = self._position_amount(c, s)
                if abs(amt) <= 0:
                    return {"ok": False, "error": "لا مركز مفتوح"}
                side = "sell" if amt > 0 else "buy"
                # 🎯 حدّ قصير ثمّ ارتداد للسوق — الخروج مضمون دائماً.
                o = None
                if not _os.path.exists(EXCH_LIMIT_OFF):
                    o, _m = _limit_exit(c, s, side, abs(amt),
                                        self._close_params(), self.name_ar)
                if not o:
                    o = c.create_order(s, "market", side, abs(amt),
                                       None, self._close_params())
            else:
                # 🛡️ السبوت: نبيع ما اشتراه البوت فقط — لا رصيد المشترك.
                #    مقيس 14 سبتمبر: البوت اشترى 1628.6 BANK بـ50$ وباع
                #    3876.2 BANK بـ120.94$ — أي باع 2247 عملة يملكها
                #    المشترك قبلنا (~70$). والسبب ان free كان الرصيد كله.
                base = s.split("/")[0]
                free = float((c.fetch_balance().get(base) or {}).get("free") or 0)
                if free <= 0:
                    return {"ok": False, "error": "لا رصيد"}
                want = float(qty or 0)
                amt = min(want, free) if want > 0 else free
                if want > 0 and free < want * 0.97:
                    log.warning("🛡️ %s %s: الرصيد %.6f دون المشترى %.6f",
                                self.name_ar, s, free, want)
                if amt <= 0:
                    return {"ok": False, "error": "كمّية صفر"}
                o = c.create_order(s, "market", "sell",
                                   float(c.amount_to_precision(s, amt)))
            try:
                c.cancel_all_orders(s)
            except Exception:
                pass
            log.info("🔌🔴 %s أغلق %s", self.name_ar, s)
            return {"ok": True, "id": str(o.get("id", ""))}
        except Exception as e:
            log.error("🔌 %s إغلاق %s: %s", self.name_ar, s, e)
            return {"ok": False, "error": str(e)}

    def ensure_oneway(self, c) -> dict:
        """🎯 يضبط الحساب على وضع الاتّجاه الواحد.

        مقيس 16 سبتمبر: ثلاثة حسابات على وضع الاتّجاهين (Hedge)،
        فكل أوامرنا تُرفض بـ-4061 "جانب المركز لا يطابق الاعداد".
        ابوبكر رصيده 100.98$ وصفر صفقات، و55 محاولة فاشلة في 48 ساعة.

        نظامنا يفتح مركزا واحدا للعملة ويغلقه بأمر معاكس — وهذا هو
        وضع الاتّجاه الواحد بالضبط. فنضبط الحساب عليه بدل تعقيد الكود.

        والتبديل يفشل ان كان هناك مركز مفتوح (-4068)، فنفحص اولا.
        """
        try:
            if hasattr(c, "fapiPrivateGetPositionSideDual"):
                m = c.fapiPrivateGetPositionSideDual()
                dual = str(m.get("dualSidePosition", "")).lower() == "true"
            else:
                m = c.fetch_position_mode() if hasattr(c, "fetch_position_mode") else {}
                dual = bool(m.get("hedged") or m.get("dualSidePosition"))
            if not dual:
                return {"ok": True, "changed": False, "why": "اتّجاه واحد سلفاً"}
            pos = [p for p in (c.fetch_positions() or [])
                   if abs(float(p.get("contracts") or 0)) > 0]
            if pos:
                return {"ok": False, "changed": False,
                        "why": "%d مركز مفتوح — نؤجّل" % len(pos)}
            if hasattr(c, "fapiPrivatePostPositionSideDual"):
                c.fapiPrivatePostPositionSideDual({"dualSidePosition": "false"})
            else:
                c.set_position_mode(False)
            log.warning("🎯 %s: ضُبط على وضع الاتّجاه الواحد", self.name_ar)
            return {"ok": True, "changed": True, "why": "بُدّل"}
        except Exception as e:
            msg = str(e)[:70]
            if "-4059" in msg or "No need to change" in msg:
                return {"ok": True, "changed": False, "why": "اتّجاه واحد سلفاً"}
            log.debug("ensure_oneway %s: %s", self.name_ar, msg)
            return {"ok": False, "changed": False, "why": msg}

    def settle(self, c, sym: str, t0: int, t1: int,
               futures: bool = False) -> dict:
        """💰 التنفيذ الحقيقي من المنصّة — لا تقدير.

        مقيس 14 سبتمبر على السبوت: التقدير (spend × pnl_pct) يخطئ في
        كل صفقة — POWR قدّرنا -0.38$ والحقيقة -2.08$، و ARK قدّرنا
        +1.07$ والحقيقة -0.22$ (عكس الاشارة). فلا يرى الانزلاق ولا
        رسوم الشراء ولا التعبئة الجزئية.

        ccxt يوفّر fetch_my_trades بواجهة موحّدة لكل المنصّات، فالدالّة
        هنا تعمل للسبع جميعا — باينانس وبايبت ومكسي وأوكي إكس وبيتجت
        وجيت وبينج إكس — بلا كود خاص لكل واحدة.

        الفيوتشر: الصافي = مجموع realizedPnl − الرسوم
        السبوت  : الصافي = البيع − الشراء − الرسوم
        """
        try:
            s_ = self.symbol(sym, futures)
            tr = c.fetch_my_trades(s_, since=max(0, (t0 - 120)) * 1000,
                                   limit=100)
            tr = [t for t in tr
                  if t.get("timestamp") and t["timestamp"] / 1000 <= t1 + 300]
            if not tr:
                return {"ok": False, "error": "لا تنفيذ"}

            fee = 0.0
            for t in tr:
                f = t.get("fee") or {}
                cst = float(f.get("cost") or 0)
                cur = (f.get("currency") or "").upper()
                if cur in ("USDT", "USDC", "BUSD"):
                    fee += cst
                elif cst > 0:
                    # رسوم بعملة اخرى — نقدّرها من قيمة الصفقة
                    fee += float(t.get("cost") or 0) * 0.001

            if futures:
                pnl = 0.0
                for t in tr:
                    inf = t.get("info") or {}
                    for k in ("realizedPnl", "realisedPnl", "closedPnl",
                              "realized_pnl", "pnl"):
                        if inf.get(k) not in (None, ""):
                            try:
                                pnl += float(inf[k])
                            except Exception:
                                pass
                            break
                return {"ok": True, "buy": 0.0, "sell": 0.0,
                        "fee": round(fee, 6), "net": round(pnl - fee, 6),
                        "n": len(tr)}

            buy = sum(float(t.get("cost") or 0) for t in tr
                      if str(t.get("side", "")).lower() == "buy")
            sell = sum(float(t.get("cost") or 0) for t in tr
                       if str(t.get("side", "")).lower() == "sell")
            return {"ok": True, "buy": round(buy, 6), "sell": round(sell, 6),
                    "fee": round(fee, 6), "net": round(sell - buy - fee, 6),
                    "n": len(tr)}
        except Exception as e:
            log.debug("settle %s %s: %s", self.name_ar, sym, str(e)[:70])
            return {"ok": False, "error": str(e)[:70]}

    def _position_amount(self, c, s: str) -> float:
        for p in (c.fetch_positions([s]) or []):
            n = float(p.get("contracts") or 0)
            if abs(n) > 0:
                return n if p.get("side") == "long" else -n
        return 0.0

    def _close_params(self) -> dict:
        return {"reduceOnly": True}

    def test(self, key: str, secret: str, passphrase: str = "",
             testnet: bool = False) -> dict:
        try:
            c = self.client(key, secret, passphrase, futures=True, testnet=testnet)
            b = c.fetch_balance()
            return {"ok": True, "usdt": float((b.get("USDT") or {}).get("free") or 0),
                    "exchange": self.name_ar}
        except Exception as e:
            return {"ok": False, "error": str(e)[:150]}


# ═══════════════════════════════════════════════════════════════
# 🎯 أوامر الحدّ للمنصّات الست — نفس معيار باينانس
# ═══════════════════════════════════════════════════════════════
# الاشارة تأتي من باينانس، لكن السعر والمستويات من المنصّة نفسها
# لحظة التنفيذ — فالوقف والاهداف صحيحة لا مأخوذة من سوق آخر.
# الاطفاء: touch /opt/whalex/db/exch_limit.off
import os as _os
import time as _tm

EXCH_LIMIT_OFF = "/opt/whalex/db/exch_limit.off"
ENTRY_WAIT = 30.0
ENTRY_POLL = 1.5
FLEE_PCT = 3.0
EXIT_WAIT = 8.0
EXIT_POLL = 0.5


def _limit_entry(c, s, side_ccxt, qty, px, params, name_ar):
    """دخول بحدّ. يُعيد (order أو None، السبب، سعر التعبئة)."""
    try:
        o = c.create_order(s, "limit", side_ccxt, qty, px, params)
    except Exception as e:
        # 🎯 وضع الاتّجاهين يرفض أوامرنا بـ-4061 — نضبط ونُعيد فورا
        #    بدل انتظار الحارس الدوري. مقيس 16 سبتمبر: ابوبكر رصيده
        #    100.98$ وصفر صفقات بسبب هذا، و55 محاولة فاشلة في 48 ساعة.
        if "-4061" in str(e) or "position side does not match" in str(e).lower():
            try:
                pos = [p for p in (c.fetch_positions() or [])
                       if abs(float(p.get("contracts") or 0)) > 0]
                if not pos:
                    if hasattr(c, "fapiPrivatePostPositionSideDual"):
                        c.fapiPrivatePostPositionSideDual({"dualSidePosition": "false"})
                    else:
                        c.set_position_mode(False)
                    log.warning("🎯 %s: ضُبط على الاتّجاه الواحد — نُعيد المحاولة",
                                name_ar)
                    o = c.create_order(s, "limit", side_ccxt, qty, px, params)
                    oid = o.get("id")
                    t0 = _tm.time()
                    while (_tm.time() - t0) < ENTRY_WAIT:
                        _tm.sleep(ENTRY_POLL)
                        try:
                            st = c.fetch_order(oid, s)
                        except Exception:
                            continue
                        if str(st.get("status")) == "closed":
                            return st, "", float(st.get("average") or px)
                    try:
                        c.cancel_order(oid, s)
                    except Exception:
                        pass
                    return None, "timeout no fill", 0.0
            except Exception as _me:
                log.debug("🎯 %s ضبط الوضع: %s", name_ar, str(_me)[:60])
        log.warning("🔌 %s حدّ %s: %s", name_ar, s, e)
        return None, f"limit failed: {e}", 0.0
    oid = o.get("id")
    t0 = _tm.time()
    while (_tm.time() - t0) < ENTRY_WAIT:
        _tm.sleep(ENTRY_POLL)
        try:
            od = c.fetch_order(oid, s)
        except Exception:
            continue
        st = (od.get("status") or "").lower()
        filled = float(od.get("filled") or 0)
        if st == "closed" or filled >= qty * 0.99:
            fill = float(od.get("average") or od.get("price") or px)
            log.info("🔌🎯 %s حدّ امتلأ %s @%.8g (%.0fث)",
                     name_ar, s, fill, _tm.time() - t0)
            return od, "", fill
        if st in ("canceled", "expired", "rejected"):
            return (od if filled > 0 else None), f"cancelled ({st})", 0.0
        try:
            live = float((c.fetch_ticker(s) or {}).get("last") or 0)
        except Exception:
            continue
        if live <= 0:
            continue
        drift = ((live - px) if side_ccxt == "buy" else (px - live)) / px * 100
        if drift > FLEE_PCT:
            try:
                c.cancel_order(oid, s)
            except Exception:
                pass
            if filled > 0:
                od = c.fetch_order(oid, s)
                return od, "", float(od.get("average") or px)
            log.info("🔌🚫 %s الغاء %s — هرب %.2f%%", name_ar, s, drift)
            return None, f"price fled {drift:.2f}%", 0.0
    try:
        c.cancel_order(oid, s)
        od = c.fetch_order(oid, s)
        if float(od.get("filled") or 0) > 0:
            return od, "", float(od.get("average") or px)
    except Exception:
        pass
    log.info("🔌🚫 %s الغاء %s — مهلة", name_ar, s)
    return None, "timeout no fill", 0.0


def _limit_exit(c, s, side_ccxt, amt, params, name_ar):
    """خروج بحدّ ثمّ ارتداد للسوق. يُعيد (order أو None، الطريقة)."""
    try:
        live = float((c.fetch_ticker(s) or {}).get("last") or 0)
        if live <= 0:
            return None, "no price"
        o = c.create_order(s, "limit", side_ccxt, amt, live, params)
    except Exception as e:
        log.debug("🔌 %s حدّ خروج %s: %s", name_ar, s, e)
        return None, "limit-failed"
    oid = o.get("id")
    t0 = _tm.time()
    while (_tm.time() - t0) < EXIT_WAIT:
        _tm.sleep(EXIT_POLL)
        try:
            od = c.fetch_order(oid, s)
        except Exception:
            continue
        st = (od.get("status") or "").lower()
        if st == "closed" or float(od.get("filled") or 0) >= amt * 0.99:
            log.info("🔌🎯 %s خروج بحدّ %s (%.1fث)", name_ar, s, _tm.time() - t0)
            return od, "limit"
        if st in ("canceled", "expired", "rejected"):
            break
    try:
        c.cancel_order(oid, s)
    except Exception:
        pass
    log.info("🔌 %s خروج مهلة %s → سوق", name_ar, s)
    return None, "timeout"
