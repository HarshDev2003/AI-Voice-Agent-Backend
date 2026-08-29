from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from the .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Simple Auth API"
    ENVIRONMENT: str = "development"

    # Accept both MONGODB_URL (spec) and MONGODB_URI (existing .env)
    MONGODB_URL: str | None = None
    MONGODB_URI: str | None = None
    MONGODB_DATABASE: str = "auth_db"

    JWT_SECRET_KEY: str = "change-this-secret-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: str = ""  # comma-separated list; falls back to FRONTEND_URL

    @property
    def cors_origins(self) -> list[str]:
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.FRONTEND_URL and self.FRONTEND_URL not in origins:
            origins.append(self.FRONTEND_URL)
        return origins

    @property
    def mongodb_url(self) -> str:
        url = self.MONGODB_URL or self.MONGODB_URI
        if not url:
            raise RuntimeError("MONGODB_URL (or MONGODB_URI) is not configured in the environment")
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
