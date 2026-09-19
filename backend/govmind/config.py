from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration, loaded from env vars (or a Modal Secret)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5"

    # Database — Postgres in production (e.g. Neon/Supabase), SQLite locally
    database_url: str = "sqlite+aiosqlite:///./govmind.db"

    # WhatsApp Cloud API (Meta)
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "govmind-verify"
    whatsapp_app_secret: str = ""  # enables X-Hub-Signature-256 verification when set
    whatsapp_api_version: str = "v21.0"
    # Comma-separated numbers (E.164) that always receive DAO broadcasts
    whatsapp_broadcast_numbers: str = ""

    # Endless Chain
    endless_private_key: str = ""
    endless_network: str = "testnet"
    chain_helper_dir: Path = Path(__file__).resolve().parent.parent / "chain"

    # Server
    public_base_url: str = ""  # used for chart links; inferred from requests if empty
    chart_dir: Path = Path("./public/charts")
    scheduled_checks_enabled: bool = False

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        # Hosted Postgres providers hand out sync URLs; SQLAlchemy async needs asyncpg.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v

    @property
    def broadcast_numbers(self) -> list[str]:
        return [n.strip().lstrip("+") for n in self.whatsapp_broadcast_numbers.split(",") if n.strip()]

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(self.whatsapp_access_token and self.whatsapp_phone_number_id)

    @property
    def explorer_base(self) -> str:
        if self.endless_network == "mainnet":
            return "https://explorer.endless.link"
        return "https://explorer-test.endless.link"


@lru_cache
def get_settings() -> Settings:
    return Settings()
