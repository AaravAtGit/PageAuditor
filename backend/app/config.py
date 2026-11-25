"""Settings, read from environment variables (or a local .env file)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://aeo:aeo@localhost:5432/aeo"
    redis_url: str = "redis://localhost:6379/0"
    llm_model: str = "gemini-3.8-flash"  # GEMINI_API_KEY is read by the SDK itself
    rate_limit_per_hour: int = 10
    cache_ttl_seconds: int = 24 * 60 * 60
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
