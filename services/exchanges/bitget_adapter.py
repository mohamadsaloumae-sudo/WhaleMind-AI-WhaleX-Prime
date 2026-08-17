"""⚡ بيتجت — تحتاج passphrase."""
from .base import ExchangeAdapter


class BitgetAdapter(ExchangeAdapter):
    id = "bitget"
    name_ar = "بيتجت"
    needs_passphrase = True
