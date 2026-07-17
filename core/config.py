from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    secret_key: str = Field(default="whalex-secret-2026", alias="SECRET_KEY")
    cors_origins: List[str] = ["*"]
    gas_fee_pct: float = 0.01
    database_url: str = Field(default="sqlite:////opt/whalex/db/whalex.db", alias="DATABASE_URL")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_channel_futures: str = Field(default="", alias="TELEGRAM_CHANNEL_FUTURES")
    telegram_channel_spot: str = Field(default="", alias="TELEGRAM_CHANNEL_SPOT")
    telegram_channel_meme: str = Field(default="", alias="TELEGRAM_CHANNEL_MEME")
    telegram_admin_chat_id: str = Field(default="", alias="TELEGRAM_ADMIN_CHAT_ID")
    telegram_spot_channel_id: str = Field(default="-1003936494458", alias="TELEGRAM_SPOT_CHANNEL_ID")
    telegram_mini_app_url: str = Field(default="", alias="TELEGRAM_MINI_APP_URL")
    binance_api_key: str = Field(default="", alias="BINANCE_API_KEY")
    binance_secret: str = Field(default="", alias="BINANCE_SECRET_KEY")
    bybit_api_key: str = Field(default="", alias="BYBIT_API_KEY")
    bybit_secret: str = Field(default="", alias="BYBIT_SECRET_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    subscription_price: float = 50.0
    wallet_address: str = Field(default="", alias="WALLET_ADDRESS")

    model_config = {
        "env_file": "/opt/whalex/.env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "populate_by_name": True,
        "extra": "ignore",
    }

@lru_cache
def get_settings() -> Settings:
    return Settings()
