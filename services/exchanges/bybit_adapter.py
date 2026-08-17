"""⚡ باي بيت — الوضع أحادي الاتجاه يمنع تعارض long/short."""
from .base import ExchangeAdapter


class BybitAdapter(ExchangeAdapter):
    id = "bybit"
    name_ar = "باي بيت"
    name_en = "Bybit"

    def _open_params(self, futures: bool) -> dict:
        return {"positionIdx": 0} if futures else {}
