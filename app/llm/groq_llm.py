"""Groq chat-completions LLM provider, with retry-with-backoff."""
import asyncio
import logging
from typing import Any

from groq import AsyncGroq

from app.core.exceptions import GroqError
from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class GroqLLM(LLMProvider):
    """Async LLM provider calling Groq's chat completions API."""

    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-oss-120b",
        client: AsyncGroq | None = None,
        temperature: float = 0.3,
        max_retries: int = 3,
        base_delay: float = 0.5,
    ) -> None:
        self._api_key = api_key
        self._model = model
        # Injectable client (used by tests / DI).
        self._client = client or AsyncGroq(api_key=api_key)
        self._temperature = temperature
        self._max_retries = max_retries
        self._base_delay = base_delay

    async def chat(self, messages: list[dict[str, Any]]) -> str:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                completion = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=self._temperature,
                )
                content = completion.choices[0].message.content or ""
                return content
            except Exception as exc:  # transient API/network errors
                last_exc = exc
                logger.warning(
                    "Groq chat attempt %d/%d failed: %s",
                    attempt + 1,
                    self._max_retries,
                    exc,
                )
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._base_delay * (2**attempt))
        raise GroqError(
            f"Groq chat failed after {self._max_retries} attempts"
        ) from last_exc


def build_llm_provider(settings) -> GroqLLM:
    """Build a Groq LLM provider from application settings."""
    return GroqLLM(
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_MODEL,
    )