from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Jarvis"
    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = Field(
        ...,
        alias="DATABASE_URL",
        description="PostgreSQL connection URL",
    )
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    model_config = SettingsConfigDict(extra="ignore", env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()