"""Twilio webhook router.

Handles inbound call setup and call-status callbacks. Both endpoints are
protected by Twilio request-signature validation.
"""
import asyncio
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.telephony.twilio_provider import verify_twilio_signature
from app.telephony.twiml_builder import build_empty_response, build_incoming_twiml

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/twilio", tags=["webhooks"])


class TwilioSignatureError(Exception):
    """Raised when a Twilio request fails signature validation."""


async def load_webhook_params(request: Request) -> dict[str, str]:
    """Reconstruct the parameters Twilio signs: query params + form body.

    The form body is consumed here (once) and cached on ``request.state`` so
    the endpoint handler can reuse it without reading the request stream again.
    """
    params = {key: value for key, value in request.query_params.items()}
    form: dict[str, str] = {}
    try:
        raw_form = await request.form()
        for key in raw_form:
            form[key] = str(raw_form[key])
    except Exception:
        logger.warning("Could not read form body for Twilio webhook")
    params.update(form)
    request.state.twilio_form = form
    return params


async def verify_twilio_request(request: Request) -> None:
    """Dependency: reject requests whose ``X-Twilio-Signature`` is invalid."""
    signature = request.headers.get("X-Twilio-Signature")
    params = await load_webhook_params(request)
    if not verify_twilio_signature(str(request.url), signature=signature, params=params):
        raise TwilioSignatureError("Invalid or missing Twilio signature")


@router.post("/incoming", dependencies=[Depends(verify_twilio_request)])
async def twilio_incoming(request: Request) -> Response:
    """Receive a forwarded call. Return TwiML that connects a Media Stream."""
    call_sid = request.state.twilio_form.get("CallSid", "")
    twiml = build_incoming_twiml(call_sid)
    logger.info("Incoming call for %s", call_sid)
    return Response(content=twiml.to_xml(), media_type="application/xml")


@router.post("/status", dependencies=[Depends(verify_twilio_request)])
async def twilio_status(request: Request) -> Response:
    """Receive call-status callbacks (completed/failed) → trigger post-call pipeline."""
    form = request.state.twilio_form
    call_sid = form.get("CallSid", "")
    call_status = form.get("CallStatus", "")
    logger.info(
        "Call status event for %s: %s",
        call_sid,
        call_status,
    )

    # Twilio status callbacks must respond fast. Run the post-call
    # pipeline in the background and return the empty TwiML immediately.
    repo = getattr(request.app.state, "calls_repository", None)
    if repo is not None and call_sid:
        from app.calls.post_call import run_post_call
        from app.llm.groq_llm import build_llm_provider
        from app.core.config import get_settings

        settings = get_settings()
        llm = build_llm_provider(settings)
        asyncio.create_task(
            run_post_call(
                call_sid,
                call_status=call_status,
                repository=repo,
                llm=llm,
            )
        )
    return Response(content=build_empty_response().to_xml(), media_type="application/xml")