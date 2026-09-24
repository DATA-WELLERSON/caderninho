from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5433/caderninho"
    sentry_dsn: str | None = None
    # A Vercel injeta VERCEL_ENV (production/preview/development) em tempo de execução.
    environment: str = Field("local", validation_alias=AliasChoices("VERCEL_ENV", "ENVIRONMENT"))
    # O deploy do CI passa SENTRY_RELEASE=<sha do commit>.
    release: str | None = Field(
        None, validation_alias=AliasChoices("SENTRY_RELEASE", "VERCEL_GIT_COMMIT_SHA")
    )
    enable_debug_routes: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
