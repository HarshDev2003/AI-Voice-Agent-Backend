import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.calls.router import router as calls_router
from app.core.config import get_settings
from app.core.health import router as health_router
from app.core.logging import setup_logging
from app.voice.router import router as voice_router
from app.webhooks.router import TwilioSignatureError, router as webhooks_router

logger = logging.getLogger(__name__)

# OpenAPI tag groups, matching the planned module layout (docs/Ai-Voice-MVP.md §10).
TAGS_METADATA = [
    {
        "name": "health",
        "description": "Service health check.",
    },
    {
        "name": "webhooks",
        "description": "Twilio call webhooks — receive forwarded calls, dispatch real-time "
        "voice handling, and trigger the post-call pipeline.",
    },
    {
        "name": "calls",
        "description": "Post-call records — list calls and retrieve a single call with "
        "its transcript and summary. Implemented in Phase 6.",
    },
]


def create_app() -> FastAPI:
    setup_logging()
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description=(
            "**AI Call Interceptor MVP** — receives forwarded calls via Twilio, holds a "
            "real-time voice conversation (Deepgram STT → Groq LLM → Deepgram TTS), "
            "optionally transfers the call to the human, and saves the transcript + "
            "summary to Supabase after the call ends.\n\n"
            "**Stack:** FastAPI · Twilio · Deepgram · Groq · Supabase."
        ),
        summary="AI Call Interceptor — MVP backend",
        openapi_tags=TAGS_METADATA,
        # Toggle interactive docs in non-production.
        docs_url=("/docs" if settings.APP_ENV != "production" else None),
        redoc_url=("/redoc" if settings.APP_ENV != "production" else None),
    )

    # CORS: allow the configured frontend origins only.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Webhook signature failures → 403.
    @app.exception_handler(TwilioSignatureError)
    async def _twilio_signature_error_handler(_: Request, exc: TwilioSignatureError):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    app.include_router(health_router)
    app.include_router(webhooks_router)
    app.include_router(voice_router)
    app.include_router(calls_router)

    # Persistence for call records. The status webhook and the calls
    # router read this from app.state; tests can override it.
    from app.calls.repository import build_calls_repository

    app.state.calls_repository = build_calls_repository(settings)

    logger.info("Starting %s (%s)", settings.APP_NAME, settings.APP_ENV)
    return app


app = create_app()
