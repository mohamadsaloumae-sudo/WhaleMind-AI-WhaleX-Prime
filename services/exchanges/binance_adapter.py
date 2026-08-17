"""⚡ باينانس — المرجع (لا استثناءات)."""
from .base import ExchangeAdapter


class BinanceAdapter(ExchangeAdapter):
    id = "binance"
    name_ar = "باينانس"
