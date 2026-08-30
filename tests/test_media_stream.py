"""Tests for the media-stream orchestrator.

These drive :class:`MediaStreamLoop` with fakes for STT, TTS, LLM and
the Twilio sender, so the entire STT -> LLM -> TTS pipeline is
exercised offline.
"""
import asyncio
import base64
from typing import AsyncIterator

import pytest

from app.core.exceptions import AudioCodecError
from app.llm.base import LLMProvider
from app.stt.base import STTProvider
from app.tts.base import TTSProvider
from app.voice.media_stream import MediaStreamLoop, parse_twilio_event
from app.voice.session import CallSession


class FakeSTT(STTProvider):
    def __init__(self, finals: list[str]) -> None:
        self._finals = list(finals)
        self.sent: list[bytes] = []
        self.connected = False
        self.closed = False

    async def connect(self) -> None:
        self.connected = True

    async def send_audio(self, audio_chunk: bytes) -> None:
        self.sent.append(audio_chunk)

    async def transcript_stream(self) -> AsyncIterator[str]:
        for f in self._finals:
            yield f
        await asyncio.Event().wait()  # block until cancelled

    async def close(self) -> None:
        self.closed = True


class FakeTTS(TTSProvider):
    def __init__(self, audio: bytes = b"audio-bytes") -> None:
        self._audio = audio
        self.calls: list[str] = []

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        self.calls.append(text)
        yield self._audio


class FakeLLM(LLMProvider):
    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self._i = 0
        self.calls = 0

    async def chat(self, messages):
        self.calls += 1
        reply = self._replies[self._i]
        self._i += 1
        return reply



def make_loop(
    *,
    finals: list[str],
    replies: list[str],
    greeting: str = "Hi!",
):
    stt = FakeSTT(finals)
    tts = FakeTTS()
    llm = FakeLLM(replies)
    sender = CapturingSender()
    session = CallSession(call_sid="CA-test", caller_number="+91xxxxxxxxxx")
    loop = MediaStreamLoop(
        call_sid="CA-test",
        session=session,
        stt=stt,
        tts=tts,
        llm=llm,
        sender=sender,
        greeting=greeting,
    )
    return loop, stt, tts, llm, sender, session


async def _drain(loop: MediaStreamLoop, tts: FakeTTS, expected: int) -> None:
    """Let pending tasks run until ``tts`` has produced ``expected`` calls.

    Polls the event loop a few times with a short sleep, but exits early
    once the expected number of TTS calls has been observed.
    """
    for _ in range(200):
        if len(tts.calls) >= expected:
            # Give one more yield so any pending _speak awaits complete.
            await asyncio.sleep(0)
            return
        await asyncio.sleep(0)



async def test_start_opens_stt_and_sends_greeting():
    loop, stt, tts, llm, sender, _ = make_loop(
        finals=[], replies=[], greeting="Hello!"
    )
    await loop.handle_message(
        {"event": "start", "start": {"streamSid": "MZabc"}}
    )
    await _drain(loop, tts, expected=1)
    assert stt.connected is True
    assert tts.calls and tts.calls[0] == "Hello!"
    media = [m for m in sender.sent if m.get("event") == "media"]
    assert media, "no media frames sent"
    assert media[0]["streamSid"] == "MZabc"
    assert base64.b64decode(media[0]["media"]["payload"]) == b"audio-bytes"
    await loop.shutdown()


async def test_audio_is_forwarded_to_stt():
    loop, stt, tts, llm, sender, _ = make_loop(finals=[], replies=[])
    await loop.handle_message({"event": "start", "start": {"streamSid": "MZ1"}})
    payload = base64.b64encode(b"\x01\x02\x03").decode("ascii")
    await loop.handle_message(
        {"event": "media", "media": {"payload": payload}}
    )
    assert stt.sent == [b"\x01\x02\x03"]
    await loop.shutdown()


async def test_full_turn_runs_stt_to_tts():
    loop, stt, tts, llm, sender, session = make_loop(
        finals=["Hello there"],
        replies=["Hi! How can I help?"],
    )
    await loop.handle_message({"event": "start", "start": {"streamSid": "MZ2"}})
    await _drain(loop, tts, expected=2)
    assert "Hi! How can I help?" in tts.calls
    assert llm.calls == 1
    assert [t.role for t in session.history] == ["user", "assistant"]
    assert session.history[0].text == "Hello there"
    assert session.history[1].text == "Hi! How can I help?"
    await loop.shutdown()


async def test_transfer_intent_sends_no_further_tts():
    loop, stt, tts, llm, sender, session = make_loop(
        finals=["Connect me to Harsh please"],
        replies=["Please hold. [TRANSFER]"],
    )
    await loop.handle_message({"event": "start", "start": {"streamSid": "MZ3"}})
    await _drain(loop, tts, expected=1)
    assert tts.calls == [loop.greeting]
    assert session.status == "transferred"
    await loop.shutdown()


async def test_end_intent_sends_stop_frame():
    loop, stt, tts, llm, sender, session = make_loop(
        finals=["Goodbye, thanks"],
        replies=["Bye! [END_CALL]"],
    )
    await loop.handle_message({"event": "start", "start": {"streamSid": "MZ4"}})
    await _drain(loop, tts, expected=2)
    assert "Bye!" in tts.calls
    assert any(m.get("event") == "stop" for m in sender.sent)
    assert session.status == "completed"
    await loop.shutdown()


async def test_stop_event_shuts_loop_down():
    loop, stt, tts, llm, sender, _ = make_loop(finals=[], replies=[])
    await loop.handle_message({"event": "start", "start": {"streamSid": "MZ5"}})
    await loop.handle_message({"event": "stop"})
    assert loop._stopped is True
    assert stt.closed is True


async def test_invalid_base64_raises_audio_codec_error():
    loop, stt, tts, llm, sender, _ = make_loop(finals=[], replies=[])
async def test_watchdog_ends_call_after_inactivity():
    loop, stt, tts, llm, sender, _ = make_loop(finals=[], replies=[])
    loop.inactivity_seconds = 0  # fire as soon as the watchdog wakes
    await loop.handle_message({"event": "start", "start": {"streamSid": "MZ7"}})
    # Give the watchdog at least one tick to fire (it sleeps 1.0 s by default).
    for _ in range(40):
        await asyncio.sleep(0.05)
        if loop._stopped:
            break
    assert loop._stopped is True
    assert stt.closed is True


async def test_transfer_calls_twilio_with_personal_number(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_transfer(call_sid: str, to_number: str) -> None:
        calls.append((call_sid, to_number))

    monkeypatch.setattr("app.voice.media_stream._twilio_transfer", fake_transfer)

    loop, stt, tts, llm, sender, session = make_loop(
        finals=["Please connect me to Harsh"],
        replies=["Hold on, transferring. [TRANSFER]"],
    )
    loop.personal_number = "+91xxxxxxxxxx"
    await loop.handle_message({"event": "start", "start": {"streamSid": "MZ8"}})
    await _drain(loop, tts, expected=1)  # only the greeting — transfer is silent
    assert calls == [("CA-test", "+91xxxxxxxxxx")]
    assert session.status == "transferred"
    await loop.shutdown()


    await loop.handle_message({"event": "start", "start": {"streamSid": "MZ6"}})
    with pytest.raises(AudioCodecError):
        await loop.handle_message(
            {"event": "media", "media": {"payload": "!!!not-base64!!!"}}
        )
    await loop.shutdown()


def test_parse_twilio_event_handles_bytes_and_garbage():
    assert parse_twilio_event('{"event": "start"}') == {"event": "start"}
    assert parse_twilio_event(b'{"event": "stop"}') == {"event": "stop"}
    assert parse_twilio_event("not json") == {}
    assert parse_twilio_event("[1, 2]") == {}

class CapturingSender:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, payload: dict) -> None:
        self.sent.append(payload)
