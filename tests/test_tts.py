import asyncio

import pytest

from app.core.exceptions import DeepgramError
from app.tts.deepgram_tts import DeepgramTTS, build_speak_uri


class FakeResponse:
    def __init__(self, status_code=200, chunks=(b"audio1", b"audio2"), body=b"err"):
        self.status_code = status_code
        self._chunks = list(chunks)
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk

    async def aread(self):
        return self._body


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls: list = []

    def stream(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


def test_build_speak_uri():
    uri = build_speak_uri("aura-asteria-en")
    assert uri.startswith("https://api.deepgram.com/v1/speak?")
    assert "model=aura-asteria-en" in uri
    assert "encoding=mulaw" in uri
    assert "sample_rate=8000" in uri


def test_synthesize_streams_audio_bytes():
    fake = FakeClient(FakeResponse(200))
    tts = DeepgramTTS(api_key="test-key", http_client=fake)

    async def run():
        collected = []
        async for chunk in tts.synthesize("Hi there"):
            collected.append(chunk)
        return collected

    collected = asyncio.run(run())
    assert collected == [b"audio1", b"audio2"]

    method, url, kwargs = fake.calls[0]
    assert method == "POST"
    assert "encoding=mulaw" in url
    assert kwargs["headers"]["Authorization"] == "Token test-key"
    assert kwargs["json"] == {"text": "Hi there"}


def test_synthesize_raises_deepgram_error_on_bad_status():
    fake = FakeClient(FakeResponse(status_code=500, body=b"oops"))
    tts = DeepgramTTS(api_key="test-key", http_client=fake)

    async def run():
        async for _ in tts.synthesize("Hi"):
            pass

    with pytest.raises(DeepgramError):
        asyncio.run(run())