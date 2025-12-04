from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    app_env: str = "dev"
    app_port: int = 8000
    app_timezone: str = Field(default="UTC", alias="APP_TIMEZONE")
    enable_scheduler: bool = Field(default=True, alias="ENABLE_SCHEDULER")
    enable_ingestors: bool = Field(default=True, alias="ENABLE_INGESTORS")

    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")
    sqlite_db_path: str = str(PROJECT_ROOT / "data" / "whales.db")

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_name: str = "whales"

    ethereum_rpc_http_url: str | None = None
    ethereum_rpc_ws_url: str | None = None

    bitcoin_api_base_url: str = "https://mempool.space/api"

    hyperliquid_info_url: str = "https://api.hyperliquid.xyz/info"
    hyperliquid_max_rps: float = Field(default=3.0, alias="HYPERLIQUID_MAX_RPS")
    hyperliquid_private_key: str | None = Field(default=None, alias="HYPERLIQUID_PRIVATE_KEY")
    hyperliquid_address: str | None = Field(default=None, alias="HYPERLIQUID_ADDRESS")
    hyperliquid_slippage_pct: float = Field(default=1.0, alias="HYPERLIQUID_SLIPPAGE_PCT")

    coingecko_api_base_url: str = "https://api.coingecko.com/api/v3"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @computed_field
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override

        sqlite_path = Path(self.sqlite_db_path).resolve()
        return f"sqlite:///{sqlite_path}"

    @computed_field
    @property
    def tzinfo(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.app_timezone)
        except Exception:
            return ZoneInfo("UTC")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
