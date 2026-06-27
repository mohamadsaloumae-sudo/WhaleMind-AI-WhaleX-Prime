"""التحقّق من مدفوعات USDT-TRC20 عبر TronGrid"""
import os, requests, logging

log = logging.getLogger("tron_verify")

# عقد USDT الرسميّ على TRON (TRC20)
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
TRON_API = "https://api.trongrid.io"


def _hex_to_base58(hex_addr: str) -> str:
    """يحوّل عنوان TRON من hex (0x...) إلى base58 (T...)"""
    import base58, hashlib
    if not hex_addr:
        return ""
    h = hex_addr.lower().replace("0x", "")
    # TRON يستخدم بادئة 41 قبل العنوان
    if len(h) == 40:
        h = "41" + h
    try:
        raw = bytes.fromhex(h)
        checksum = hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
        return base58.b58encode(raw + checksum).decode()
    except Exception:
        return ""


def verify_usdt_payment(tx_hash: str, min_amount: float):
    """
    تتحقّق من معاملة USDT-TRC20.
    ترجع: {"ok": bool, "amount": float, "reason": str}
    """
    key = os.getenv("TRONGRID_API_KEY", "")
    wallet = os.getenv("WALLET_ADDRESS", "")
    if not wallet:
        return {"ok": False, "amount": 0, "reason": "محفظة الاستقبال غير مهيّأة"}

    headers = {"TRON-PRO-API-KEY": key} if key else {}

    # نجلب معلومات المعاملة
    try:
        r = requests.get(
            TRON_API + "/v1/transactions/" + tx_hash + "/events",
            headers=headers, timeout=15
        )
    except Exception as e:
        log.warning("TronGrid خطأ: %s", e)
        return {"ok": False, "amount": 0, "reason": "تعذّر الاتصال بشبكة TRON"}

    if r.status_code != 200:
        return {"ok": False, "amount": 0, "reason": "المعاملة غير موجودة"}

    data = r.json().get("data", [])
    if not data:
        return {"ok": False, "amount": 0, "reason": "لا توجد تحويلات في هذه المعاملة"}

    # نبحث عن تحويل USDT لمحفظتنا
    for ev in data:
        # نتحقّق أنّه حدث Transfer من عقد USDT
        if ev.get("contract_address") != USDT_CONTRACT:
            continue
        if ev.get("event_name") != "Transfer":
            continue
        result = ev.get("result", {})
        to_addr_raw = result.get("to", "")
        to_addr = _hex_to_base58(to_addr_raw) if to_addr_raw.startswith("0x") else to_addr_raw
        value = result.get("value", "0")

        # العنوان قد يكون hex — نقارن بعد التطبيع لاحقاً، الآن نقارن مباشرة
        amount = int(value) / 1_000_000  # USDT له 6 أرقام عشرية

        # نتحقّق أنّ المستقبِل محفظتنا (TronGrid يرجع base58 عادة)
        if to_addr == wallet:
            if amount >= min_amount:
                return {"ok": True, "amount": amount, "reason": "تمّ التحقّق"}
            else:
                return {"ok": False, "amount": amount,
                        "reason": "المبلغ %.2f أقل من المطلوب %.2f" % (amount, min_amount)}

    return {"ok": False, "amount": 0, "reason": "لا يوجد تحويل USDT لمحفظتنا في هذه المعاملة"}
