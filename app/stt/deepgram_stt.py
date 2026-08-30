"""Deepgram streaming Speech-to-Text provider (Nova-3 Multilingual)."""
import json
import logging
import urllib.parse
from typing import Any, AsyncIterator

import websockets

from app.core.exceptions import DeepgramError
from app.stt.base import STTProvider

logger = logging.getLogger(__name__)

DEEPGRAM_LISTEN_URL = "wss://api.deepgram.com/v1/listen"


def build_listen_uri(
    model: str,
    encoding: str = "mulaw",
    sample_rate: int = 8000,
    interim_results: bool = True,
    endpointing_ms: int = 500,
    language: str | None = None,
) -> str:
    """Build the Deepgram Live streaming listen URL for the given options."""
    params: dict[str, str] = {
        "model": model,
        "encoding": encoding,
        "sample_rate": str(sample_rate),
        "interim_results": str(interim_results).lower(),
        "endpointing": str(endpointing_ms),
    }
    if language:
        params["language"] = language
    return f"{DEEPGRAM_LISTEN_URL}?{urllib.parse.urlencode(params)}"


def parse_live_message(data: str | bytes | dict[str, Any]) -> tuple[bool, str]:
    """Parse a Deepgram live message into ``(is_final, transcript)``.

    Non-result messages yield ``(False, "")``; interim results yield ``False``
    with their partial transcript; final results yield ``True`` with text.
    """
    if isinstance(data, dict):
        message: dict[str, Any] = data
    else:
        try:
            message = json.loads(data)
        except (TypeError, ValueError):
            return False, ""
    if message.get("type") != "Results":
        return False, ""
    alternatives = message.get("channel", {}).get("alternatives", [])
    transcript = (alternatives[0].get("transcript", "") if alternatives else "") or ""
    return bool(message.get("is_final", False)), transcript.strip()


class DeepgramSTT(STTProvider):
    """Streaming STT over Deepgram's live WebSocket endpoint."""

    def __init__(
        self,
        api_key: str,
        model: str = "nova-3",
        encoding: str = "mulaw",
        sample_rate: int = 8000,
        endpointing_ms: int = 500,
        ws_connect=None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._encoding = encoding
        self._sample_rate = sample_rate
        self._endpointing_ms = endpointing_ms
        # Injectable connect factory (used by tests / DI).
        self._ws_connect = ws_connect or websockets.connect
        self._ws = None

    async def connect(self) -> None:
        uri = build_listen_uri(
            model=self._model,
            encoding=self._encoding,
            sample_rate=self._sample_rate,
            endpointing_ms=self._endpointing_ms,
        )
        try:
            self._ws = await self._ws_connect(
                uri, additional_headers={"Authorization": f"Token {self._api_key}"}
            )
        except Exception as exc:
            raise DeepgramError(f"Failed to connect to Deepgram STT: {exc}") from exc

    async def send_audio(self, audio_chunk: bytes) -> None:
        self._require_connected()
        await self._ws.send(audio_chunk)

    async def transcript_stream(self) -> AsyncIterator[str]:
        self._require_connected()
        try:
            while True:
                data = await self._ws.recv()
                is_final, transcript = parse_live_message(data)
                if is_final and transcript:
                    logger.debug("STT final: %s", transcript)
                    yield transcript
        except Exception as exc:
            logger.debug("STT transcript stream ended: %s", exc)

    async def close(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            finally:
                self._ws = None

    def _require_connected(self) -> None:
        if self._ws is None:
            raise DeepgramError("Deepgram STT is not connected")


def build_stt_provider(settings) -> DeepgramSTT:
    """Build a Deepgram STT provider from application settings."""
    return DeepgramSTT(
        api_key=settings.DEEPGRAM_API_KEY,
        model=settings.DEEPGRAM_STT_MODEL,
    )