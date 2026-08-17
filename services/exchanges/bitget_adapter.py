"""⚡ بيتجت — تحتاج passphrase."""
from .base import ExchangeAdapter


class BitgetAdapter(ExchangeAdapter):
    id = "bitget"
    name_ar = "بيتجت"
    name_en = "Bitget"
    needs_passphrase = True
