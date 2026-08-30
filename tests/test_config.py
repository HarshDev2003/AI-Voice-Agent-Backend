import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from app.core.config import _REQUIRED_PRODUCTION_KEYS, Settings


def test_settings_loads_defaults():
    settings = Settings()
    assert settings.APP_ENV == "development"
    assert settings.DEEPGRAM_STT_MODEL == "nova-3"
    assert settings.GROQ_MODEL == "openai/gpt-oss-120b"
    assert "http://localhost:5173" in settings.cors_origins


def test_production_missing_keys_fail_fast(monkeypatch: pytest.MonkeyPatch):
    """Production must reject startup when required keys are missing.

    We construct a fresh ``Settings`` subclass that does not load `.env`, and
    clear any real secrets from the environment, so the test exercises the
    production-fail-fast path in isolation from the developer's `.env`.
    """
    # Clear any production secrets that may live in the developer's `.env`
    # or shell environment, so we actually exercise the missing-keys branch.
    for key in _REQUIRED_PRODUCTION_KEYS:
        monkeypatch.delenv(key, raising=False)

    class _IsolatedSettings(Settings):
        model_config = SettingsConfigDict(env_file=None, extra="ignore")

    with pytest.raises(ValidationError) as exc_info:
        _IsolatedSettings(APP_ENV="production")
    message = str(exc_info.value)
    assert "TWILIO_ACCOUNT_SID" in message
    assert "Missing required environment variables in production" in message
    # All required keys should be reported missing.
    for key in _REQUIRED_PRODUCTION_KEYS:
        assert key in message

