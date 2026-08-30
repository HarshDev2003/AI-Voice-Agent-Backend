"""Abstract Text-to-Speech provider interface."""
from abc import ABC, abstractmethod
from typing import AsyncIterator


class TTSProvider(ABC):
    """Synthesized speech interface.

    ``synthesize`` streams audio bytes (Twilio-compatible mu-law 8 kHz) for the
    given text. It is an async generator so audio can be played/framed as it
    becomes available instead of buffering the full response.
    """

    @abstractmethod
    def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """Yield the synthesized audio for ``text`` as a byte stream."""