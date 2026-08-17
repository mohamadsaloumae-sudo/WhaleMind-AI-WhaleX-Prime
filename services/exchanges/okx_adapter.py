"""⚡ أوكي إكس — passphrase + وضع cross الآمن."""
from .base import ExchangeAdapter


class OkxAdapter(ExchangeAdapter):
    id = "okx"
    name_ar = "أوكي إكس"
    needs_passphrase = True

    def _open_params(self, futures: bool) -> dict:
        return {"tdMode": "cross"} if futures else {}
