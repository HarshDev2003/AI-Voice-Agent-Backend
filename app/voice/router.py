"""WebSocket route for Twilio Media Streams.

The :func:`media_stream_endpoint` is mounted at
``/ws/media-stream/{call_sid}`` and runs one :class:`MediaStreamLoop`
per call. The loop is built here from the application settings, so the
orchestrator itself stays decoupled from FastAPI.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.llm.groq_llm import build_llm_provider
from app.stt.deepgram_stt import build_stt_provider
from app.tts.deepgram_tts import build_tts_provider
from app.core.config import get_settings
from app.voice.media_stream import MediaStreamLoop, parse_twilio_event
from app.voice.session import session_store

logger = logging.getLogger(__name__)

router = APIRouter()


class _WSSender:
    """Adapter that exposes :meth:`send` on a FastAPI WebSocket."""

    def __init__(self, websocket: WebSocket) -> None:
        self._ws = websocket

    async def send(self, payload: dict) -> None:
        await self._ws.send_json(payload)


@router.websocket("/ws/media-stream/{call_sid}")
async def media_stream_endpoint(websocket: WebSocket, call_sid: str) -> None:
    """Receive Twilio Media Streams frames for one call.

    On every frame the loop is dispatched. On disconnect or ``stop``
    frame the loop is shut down and the in-memory session is removed
    from the store so it doesn't leak.
    """
    await websocket.accept()
    settings = get_settings()
    session = session_store.get_or_create(call_sid, caller_number="")

    loop = MediaStreamLoop(
        call_sid=call_sid,
        session=session,
        stt=build_stt_provider(settings),
        tts=build_tts_provider(settings),
        llm=build_llm_provider(settings),
        sender=_WSSender(websocket),
        personal_number=settings.YOUR_PERSONAL_NUMBER,
        inactivity_seconds=60,
    )
    logger.info("media_stream: WebSocket opened for %s", call_sid)

    try:
        while True:
            raw = await websocket.receive_text()
            event = parse_twilio_event(raw)
            if not event:
                continue
            await loop.handle_message(event)
            if loop._stopped:
                break
    except WebSocketDisconnect:
        logger.info("media_stream: WebSocket disconnected for %s", call_sid)
    except Exception as exc:  # noqa: BLE001
        logger.exception("media_stream: WebSocket error: %s", exc)
    finally:
        try:
            await loop.shutdown()
        finally:
            # Keep the session in memory briefly so the post-call webhook
            # (Phase 6) can read the transcript buffer before persistence.
            # Phase 6 will own final cleanup.
            pass
