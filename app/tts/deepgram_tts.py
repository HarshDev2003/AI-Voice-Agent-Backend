"""Deepgram Aura streaming Text-to-Speech provider."""
import logging
import urllib.parse
from typing import AsyncIterator

import httpx

from app.core.exceptions import DeepgramError
from app.tts.base import TTSProvider

logger = logging.getLogger(__name__)

DEEPGRAM_SPEAK_URL = "https://api.deepgram.com/v1/speak"

# Shared async client for connection pooling across calls.
_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
    return _http_client


def build_speak_uri(
    model: str,
    encoding: str = "mulaw",
    sample_rate: int = 8000,
) -> str:
    """Build the Deepgram /v1/speak URL requesting Twilio-compatible audio."""
    params = {
        "model": model,
        "encoding": encoding,
        "sample_rate": str(sample_rate),
    }
    return f"{DEEPGRAM_SPEAK_URL}?{urllib.parse.urlencode(params)}"


class DeepgramTTS(TTSProvider):
    """Streaming TTS via Deepgram Aura (REST, streamed response)."""

    def __init__(
        self,
        api_key: str,
        model: str = "aura-asteria-en",
        encoding: str = "mulaw",
        sample_rate: int = 8000,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._encoding = encoding
        self._sample_rate = sample_rate
        self._http_client = http_client  # injected for tests / shared instance

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        url = build_speak_uri(self._model, self._encoding, self._sample_rate)
        headers = {
            # Deepgram accepts both "Token" and "Bearer" schemes; "Token" is
            # used here to match the STT provider (verified working).
            "Authorization": f"Token {self._api_key}",
        }
        client = self._http_client if self._http_client is not None else get_http_client()
        try:
            async with client.stream(
                "POST", url, json={"text": text}, headers=headers
            ) as response:
                if response.status_code != 200:
                    body = (await response.aread())[:200]
                    raise DeepgramError(
                        f"Deepgram TTS failed ({response.status_code}): {body!r}"
                    )
                async for chunk in response.aiter_bytes():
                    yield chunk
        except DeepgramError:
            raise
        except Exception as exc:
            raise DeepgramError(f"Deepgram TTS request error: {exc}") from exc


def build_tts_provider(settings) -> DeepgramTTS:
    """Build a Deepgram TTS provider from application settings."""
    return DeepgramTTS(
        api_key=settings.DEEPGRAM_API_KEY,
        model=settings.DEEPGRAM_TTS_MODEL,
    )