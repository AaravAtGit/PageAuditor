"""Application settings, read from environment variables (and a local .env file in dev)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://aeo:aeo@localhost:5432/aeo"
    redis_url: str = "redis://localhost:6379/0"

    # The google-genai SDK reads GEMINI_API_KEY from the environment itself;
    # we never hold the key in our own config object.
    llm_model: str = "gemini-3.8-flash"  # stable, free tier
    llm_thinking_level: str = "medium"  # low | medium | high
    llm_max_tokens: int = 16000

    # Page fetching
    fetch_timeout_seconds: float = 10.0
    fetch_max_bytes: int = 3 * 1024 * 1024  # stop reading after 3 MB
    fetch_max_redirects: int = 5

    # Redis-backed limits
    rate_limit_per_hour: int = 10
    cache_ttl_seconds: int = 24 * 60 * 60

    # Client IPs behind a reverse proxy: uvicorn's --proxy-headers flag rewrites
    # request.client from X-Forwarded-For, but only for proxies listed in the
    # FORWARDED_ALLOW_IPS env var, so clients can't spoof their IP.

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
