"""TwiML builder for the AI Voice Agent MVP.

Builds the TwiML returned by ``POST /webhooks/twilio/incoming``: a greeting
followed by a bidirectional Media Stream connection to our WebSocket endpoint.
"""
from twilio.twiml.voice_response import VoiceResponse

from app.core.config import get_settings


def build_incoming_twiml(call_sid: str, welcome_message: str = "") -> VoiceResponse:
    """Return TwiML that greets the caller and opens a Media Stream.

    Parameters
    ----------
    call_sid:
        The Twilio CallSid; used to build the target WebSocket URL.
    welcome_message:
        Optional greeting spoken by Twilio via ``<Say>`` before the stream starts.
    """
    settings = get_settings()
    base = settings.SERVER_BASE_URL.rstrip("/")
    # Media Streams need a ws/wss URL; derive it from the public base URL.
    if base.startswith("https://"):
        ws_base = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        ws_base = "ws://" + base[len("http://"):]
    else:
        ws_base = base
    ws_url = f"{ws_base}/ws/media-stream/{call_sid}"

    response = VoiceResponse()
    if welcome_message:
        response.say(welcome_message)

    # Bidirectional stream: <Connect><Stream url=.../>
    connect = response.connect()
    connect.stream(url=ws_url)
    return response


def build_empty_response() -> VoiceResponse:
    """Return an empty TwiML document (used for status callbacks)."""
    return VoiceResponse()