from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Keys that must be set when running in production; validated at startup.
_REQUIRED_PRODUCTION_KEYS = (
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
    "YOUR_PERSONAL_NUMBER",
    "DEEPGRAM_API_KEY",
    "GROQ_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SERVER_BASE_URL",
)


class Settings(BaseSettings):
    """Application configuration, loaded from the environment / `.env`.

    Covers every variable in docs/Ai-Voice-MVP.md section 8. Secrets default
    to empty so the app and tests boot without keys in development; production
    validation fails fast with a clear message when required keys are missing.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    APP_ENV: str = "development"
    APP_NAME: str = "AI Voice Agent API"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    SERVER_BASE_URL: str = ""  # public URL for Twilio webhooks (e.g. ngrok)

    # --- CORS ---
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: str = ""  # comma-separated; falls back to FRONTEND_URL

    # --- Twilio ---
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    YOUR_PERSONAL_NUMBER: str = ""

    # --- Deepgram ---
    DEEPGRAM_API_KEY: str = ""
    DEEPGRAM_STT_MODEL: str = "nova-3"
    DEEPGRAM_TTS_MODEL: str = "aura-asteria-en"

    # --- Groq ---
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    # --- Supabase ---
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        if self.APP_ENV == "production":
            missing = [key for key in _REQUIRED_PRODUCTION_KEYS if not getattr(self, key)]
            if missing:
                raise ValueError(
                    "Missing required environment variables in production: "
                    + ", ".join(missing)
                )
        return self

    @property
    def cors_origins(self) -> list[str]:
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.FRONTEND_URL and self.FRONTEND_URL not in origins:
            origins.append(self.FRONTEND_URL)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
