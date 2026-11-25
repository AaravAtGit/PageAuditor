from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    llm_model: str = "gemini-3.5-flash-lite"
    rate_limit_per_hour: int = 10
    cache_ttl_seconds: int = 24 * 60 * 60
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
