"""Real-time media-stream call loop.

The :class:`MediaStreamLoop` is the orchestrator that runs the voice
conversation for one call:

    Twilio WS -> STT (Deepgram) -> LLM (Groq) -> TTS (Deepgram) -> Twilio WS

It is decoupled from FastAPI: the WebSocket route in ``router.py``
plumbs the live socket, while this class handles event dispatch and the
per-turn pipeline. All providers are *injected*, so the loop is
unit-testable with fakes.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import time
from typing import Any, Awaitable, Callable, Protocol

from app.agent.chain import run_turn
from app.core.exceptions import AudioCodecError
from app.llm.base import LLMProvider
from app.stt.base import STTProvider
from app.tts.base import TTSProvider
from app.voice.session import CallSession

logger = logging.getLogger(__name__)

DEFAULT_GREETING = (
    "Hello, this is Harsh's personal assistant. How can I help you today?"
)
DEFAULT_INACTIVITY_SECONDS = 60
MAX_AUDIO_BYTES = 64 * 1024


def _twilio_transfer(call_sid: str, to_number: str) -> None:
    """Thin wrapper around :func:`app.telephony.twilio_provider.transfer_call`.

    Defined at module level so ``MediaStreamLoop`` can call it via
    ``asyncio.to_thread`` without importing Twilio eagerly at process
    start (avoids the dependency when the test suite runs without it).
    """
    from app.telephony.twilio_provider import transfer_call

    transfer_call(call_sid, to_number)


class Sender(Protocol):
    """Minimal interface to send a payload back to Twilio over the WS."""

    async def send(self, payload: dict[str, Any]) -> None: ...


class MediaStreamLoop:
    """Per-call orchestrator for the STT -> LLM -> TTS pipeline.

    The loop is event-driven: :meth:`handle_message` dispatches one Twilio
    Media Streams event at a time. Audio ``media`` events are forwarded
    to STT; ``stop`` events trigger session cleanup. The per-session
    turn lock serialises agent turns so overlapping STT finals cannot
    trigger a second LLM call mid-reply.
    """

    def __init__(
        self,
        *,
        call_sid: str,
        session: CallSession,
        stt: STTProvider,
        tts: TTSProvider,
        llm: LLMProvider,
        sender: Sender,
        personal_number: str = "",
        inactivity_seconds: int = DEFAULT_INACTIVITY_SECONDS,
        greeting: str = DEFAULT_GREETING,
    ) -> None:
        self.call_sid = call_sid
        self.session = session
        self.stt = stt
        self.tts = tts
        self.llm = llm
        self.sender = sender
        self.personal_number = personal_number
        self.inactivity_seconds = inactivity_seconds
        self.greeting = greeting
        self._started = False
        self._stopped = False
        self._last_activity = time.monotonic()
        self._stt_task: asyncio.Task[None] | None = None
        self._watchdog_task: asyncio.Task[None] | None = None
        self._stream_sid_value: str | None = None

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    async def handle_message(self, event: dict[str, Any]) -> None:
        """Dispatch one Twilio Media Streams event."""
        kind = event.get("event") or event.get("type")
        if kind in (None, "connected"):
            return
        if kind == "start":
            await self._on_start(event)
            return
        if kind == "media":
            await self._on_media(event)
            return
        if kind == "stop":
            await self._on_stop(event)
            return
        logger.debug("media_stream: ignoring event %r", kind)

    async def _on_start(self, event: dict[str, Any]) -> None:
        if self._started:
            return
        self._started = True
        start = event.get("start", {}) or {}
        caller = (
            start.get("from")
            or event.get("from")
            or self.session.caller_number
        )
        if caller and not self.session.caller_number:
            self.session.caller_number = caller
        self._stream_sid_value = start.get("streamSid")
        self._last_activity = time.monotonic()
        logger.info(
            "media_stream: call_sid=%s started streamSid=%s",
            self.call_sid,
            self._stream_sid_value,
        )
        try:
            await self.stt.connect()
        except Exception as exc:
            logger.exception("media_stream: STT connect failed: %s", exc)
            raise
        self._stt_task = asyncio.create_task(
            self._stt_consumer(), name=f"stt-{self.call_sid}"
        )
        self._watchdog_task = asyncio.create_task(
            self._watchdog(), name=f"watchdog-{self.call_sid}"
        )
        await self._speak(self.greeting)

    async def _on_media(self, event: dict[str, Any]) -> None:
        if not self._started:
            return
        payload_b64 = (event.get("media") or {}).get("payload", "")
        if not payload_b64:
            return
        try:
            chunk = base64.b64decode(payload_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise AudioCodecError("invalid base64 audio payload") from exc
        if len(chunk) > MAX_AUDIO_BYTES:
            logger.warning("media_stream: dropping oversized audio frame")
            return
        await self.stt.send_audio(chunk)
        self._last_activity = time.monotonic()

    async def _on_stop(self, _event: dict[str, Any]) -> None:
        if self._stopped:
            return
        self._stopped = True
        logger.info("media_stream: call_sid=%s stream stopped", self.call_sid)
        await self.shutdown()


    # ------------------------------------------------------------------
    # STT consumer
    # ------------------------------------------------------------------

    async def _stt_consumer(self) -> None:
        """Consume STT finals and trigger agent turns until the stream ends."""
        try:
            async for text in self.stt.transcript_stream():
                self._last_activity = time.monotonic()
                cleaned = text.strip()
                if not cleaned:
                    continue
                await self._process_final(cleaned)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("media_stream: STT consumer error: %s", exc)

    async def _watchdog(self) -> None:
        """End the call if no activity arrives for ``inactivity_seconds``.

        Polls once per second; when the loop has been idle for too long it
        triggers :meth:`shutdown`, which closes the STT connection and lets
        the WS layer clean up.
        """
        try:
            while not self._stopped:
                await asyncio.sleep(1.0)
                if self._stopped:
                    return
                idle = time.monotonic() - self._last_activity
                if idle >= self.inactivity_seconds:
                    logger.warning(
                        "media_stream: call_sid=%s idle for %.0fs, ending call",
                        self.call_sid,
                        idle,
                    )
                    await self._on_stop({"event": "stop"})
                    return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("media_stream: watchdog error: %s", exc)

    async def _process_final(self, user_text: str) -> None:
        """Run one agent turn for a final STT transcript."""
        with self.session.acquire_turn():
            try:
                result = await run_turn(self.session, user_text, self.llm)
            except Exception as exc:
                logger.exception("agent turn failed: %s", exc)
                await self._speak(
                    "Sorry, I had a small problem. Could you say that again?"
                )
                return

            if result.intent.value == "transfer":
                self.session.status = "transferred"
                if self.personal_number:
                    try:
                        await asyncio.to_thread(
                            _twilio_transfer,
                            self.call_sid,
                            self.personal_number,
                        )
                    except Exception as exc:
                        logger.exception(
                            "media_stream: transfer_call failed: %s", exc
                        )
                return
            if result.intent.value == "end":
                self.session.status = "completed"
                if result.response_text:
                    await self._speak(result.response_text)
                try:
                    await self.sender.send({"event": "stop"})
                except Exception:
                    pass
                return

            if result.response_text:
                await self._speak(result.response_text)

    # ------------------------------------------------------------------
    # TTS -> Twilio outbound
    # ------------------------------------------------------------------

    async def _speak(self, text: str) -> None:
        """Synthesize ``text`` and stream audio back to Twilio."""
        try:
            async for chunk in self.tts.synthesize(text):
                await self.sender.send(
                    {
                        "event": "media",
                        "streamSid": self._stream_sid_value,
                        "media": {"payload": base64.b64encode(chunk).decode("ascii")},
                    }
                )
        except Exception as exc:
            logger.exception("TTS playback failed: %s", exc)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Cancel tasks, close providers, and mark the session cleaned up."""
        for task in (self._stt_task, self._watchdog_task):
            if task is not None and not task.done():
                task.cancel()
        for task in (self._stt_task, self._watchdog_task):
            if task is not None:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        try:
            await self.stt.close()
        except Exception as exc:
            logger.debug("media_stream: STT close error: %s", exc)


WSMessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


def parse_twilio_event(raw: str | bytes) -> dict[str, Any]:
    """Parse a Twilio Media Streams text frame into a dict."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(event, dict):
        return {}
    return event
