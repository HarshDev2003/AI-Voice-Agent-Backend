"""Typed exceptions for AI provider failures.

Used by the STT / TTS / LLM providers so callers can react deterministically
to external-service failures without importing provider internals.
"""


class ProviderError(Exception):
    """Base error for failures from an external AI provider."""


class DeepgramError(ProviderError):
    """Deepgram STT/TTS call failed."""


class GroqError(ProviderError):
    """Groq LLM call failed after exhausting retries."""


class AudioCodecError(Exception):
    """Audio payload could not be decoded (e.g. invalid base64 from Twilio)."""


class CallNotFoundError(Exception):
    """A webhook was received for an unknown / untracked call."""
