"""Abstract Speech-to-Text provider interface."""
from abc import ABC, abstractmethod
from typing import AsyncIterator


class STTProvider(ABC):
    """Live speech-to-text streaming interface.

    Implementations open a streaming connection, accept raw audio chunks, and
    expose an async iterator of *final* transcripts as they are recognized.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Open the upstream STT connection."""

    @abstractmethod
    async def send_audio(self, audio_chunk: bytes) -> None:
        """Forward a raw audio chunk (e.g. mu-law 8 kHz from Twilio)."""

    @abstractmethod
    def transcript_stream(self) -> AsyncIterator[str]:
        """Yield recognized final transcripts until the connection ends."""

    @abstractmethod
    async def close(self) -> None:
        """Close the upstream connection and release resources."""