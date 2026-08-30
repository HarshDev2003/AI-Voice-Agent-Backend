"""Abstract Large-Language-Model provider interface."""
from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Conversational LLM interface used by the agent chain."""

    @abstractmethod
    async def chat(self, messages: list[dict[str, Any]]) -> str:
        """Return the assistant text reply for a list of chat messages.

        ``messages`` follows the OpenAI chat format:
        ``[{"role": "system"|"user"|"assistant", "content": "..."}]``.
        """