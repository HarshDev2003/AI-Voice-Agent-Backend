"""Twilio telephony provider.

Wraps the Twilio REST API (transfer/end call) and the request-signature
verifier used by the webhook security dependency.
"""
import logging

from twilio.base.exceptions import TwilioRestException
from twilio.request_validator import RequestValidator
from twilio.rest import Client

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def verify_twilio_signature(
    url: str,
    signature: str | None,
    params: dict[str, str] | None = None,
) -> bool:
    """Validate an ``X-Twilio-Signature`` against our auth token.

    Twilio's RequestValidator applies the standard HMAC-SHA1 scheme over the
    URL + body params. Returns ``False`` when missing/mismatched.
    """
    settings = get_settings()
    if not signature:
        return False
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    return validator.validate(url, params or {}, signature)


def _client() -> Client:
    """Create a Twilio REST client from settings (lazy)."""
    settings = get_settings()
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def transfer_call(call_sid: str, to_number: str) -> None:
    """Transfer/redirect an active call to another number."""
    try:
        _client().calls(call_sid).update(twiml=f"<Response><Dial>{to_number}</Dial></Response>")
    except TwilioRestException as exc:
        logger.error("Twilio transfer failed for %s: %s", call_sid, exc)
        raise


def end_call(call_sid: str) -> None:
    """Hang up an active call."""
    try:
        _client().calls(call_sid).update(status="completed")
    except TwilioRestException as exc:
        logger.error("Twilio end_call failed for %s: %s", call_sid, exc)
        raise