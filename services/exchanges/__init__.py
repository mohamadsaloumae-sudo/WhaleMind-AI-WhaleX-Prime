"""🔌 سجلّ المنصّات — نقطة الوصول الوحيدة

إضافة منصّة جديدة:
  1. ملف xxx_adapter.py يرث ExchangeAdapter
  2. سطر واحد في REGISTRY
  لا تعديل على أي ملف آخر.
"""
from .base import ExchangeAdapter
from .binance_adapter import BinanceAdapter
from .bybit_adapter import BybitAdapter
from .mexc_adapter import MexcAdapter
from .bingx_adapter import BingxAdapter
from .bitget_adapter import BitgetAdapter
from .gate_adapter import GateAdapter
from .okx_adapter import OkxAdapter

REGISTRY = {
    a.id: a() for a in (
        BinanceAdapter, BybitAdapter, MexcAdapter, BingxAdapter,
        BitgetAdapter, GateAdapter, OkxAdapter,
    )
}

DEFAULT = "binance"


def get(exchange: str) -> ExchangeAdapter:
    """مُهايئ المنصّة — باينانس افتراضياً."""
    return REGISTRY.get((exchange or DEFAULT).lower(), REGISTRY[DEFAULT])


def list_exchanges() -> list:
    """للواجهة: قائمة المنصّات بخصائصها."""
    return [{
        "id": a.id,
        "name": a.name_ar,
        "needs_passphrase": a.needs_passphrase,
        "spot": a.supports_spot,
        "futures": a.supports_futures,
    } for a in REGISTRY.values()]
