import asyncio
from types import SimpleNamespace

import pytest

from app.core.exceptions import GroqError
from app.llm.groq_llm import GroqLLM


def groq_response(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class FakeClient:
    """Minimal fake AsyncGroq exposing chat.completions.create."""

    def __init__(self, responses):
        self.completions = self._Completions(responses)
        self.chat = SimpleNamespace(completions=self.completions)

    class _Completions:
        def __init__(self, responses):
            self._responses = list(responses)
            self._i = 0
            self.calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            response = self._responses[self._i]
            self._i += 1
            if isinstance(response, Exception):
                raise response
            return response


def test_chat_returns_content():
    client = FakeClient([groq_response("Hello!")])
    llm = GroqLLM(api_key="test-key", client=client)
    result = asyncio.run(llm.chat([{"role": "user", "content": "hi"}]))
    assert result == "Hello!"
    assert client.completions.calls == 1


def test_chat_retries_then_succeeds():
    client = FakeClient([RuntimeError("boom"), groq_response("recovered")])
    llm = GroqLLM(api_key="test-key", client=client, max_retries=3, base_delay=0)
    result = asyncio.run(llm.chat([{"role": "user", "content": "hi"}]))
    assert result == "recovered"
    assert client.completions.calls == 2


def test_chat_raises_after_max_retries():
    client = FakeClient(
        [RuntimeError("a"), RuntimeError("b"), RuntimeError("c")]
    )
    llm = GroqLLM(api_key="test-key", client=client, max_retries=3, base_delay=0)
    with pytest.raises(GroqError):
        asyncio.run(llm.chat([{"role": "user", "content": "hi"}]))
    assert client.completions.calls == 3