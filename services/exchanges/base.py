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
        cfg = {
            "apiKey": key, "secret": secret,
            "enableRateLimit": True, "timeout": 20000,
            "options": self._options(futures),
        }
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
             lev: float = 1.0, futures: bool = True) -> dict:
        s = self.symbol(sym, futures)
        try:
            if futures:
                self.set_leverage(c, sym, lev, futures)
            px = float((c.fetch_ticker(s) or {}).get("last") or 0)
            if px <= 0:
                return {"ok": False, "error": "سعر غير متاح"}
            qty = float(c.amount_to_precision(
                s, (usdt * (lev if futures else 1.0)) / px))
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

    def close(self, c, sym: str, futures: bool = True) -> dict:
        s = self.symbol(sym, futures)
        try:
            if futures:
                amt = self._position_amount(c, s)
                if abs(amt) <= 0:
                    return {"ok": False, "error": "لا مركز مفتوح"}
                side = "sell" if amt > 0 else "buy"
                o = c.create_order(s, "market", side, abs(amt),
                                   None, self._close_params())
            else:
                base = s.split("/")[0]
                free = float((c.fetch_balance().get(base) or {}).get("free") or 0)
                if free <= 0:
                    return {"ok": False, "error": "لا رصيد"}
                o = c.create_order(s, "market", "sell",
                                   float(c.amount_to_precision(s, free)))
            try:
                c.cancel_all_orders(s)
            except Exception:
                pass
            log.info("🔌🔴 %s أغلق %s", self.name_ar, s)
            return {"ok": True, "id": str(o.get("id", ""))}
        except Exception as e:
            log.error("🔌 %s إغلاق %s: %s", self.name_ar, s, e)
            return {"ok": False, "error": str(e)}

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
