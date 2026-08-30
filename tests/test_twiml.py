from app.telephony.twiml_builder import build_empty_response, build_incoming_twiml


def test_incoming_twiml_contains_stream_with_call_url(monkeypatch):
    monkeypatch.setenv("SERVER_BASE_URL", "https://example.ngrok.io")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        twiml = build_incoming_twiml("CA123456")
    finally:
        get_settings.cache_clear()

    xml = twiml.to_xml()
    assert "<Response>" in xml
    assert "<Connect>" in xml
    assert "wss://example.ngrok.io/ws/media-stream/CA123456" in xml


def test_incoming_twiml_removes_trailing_slash(monkeypatch):
    monkeypatch.setenv("SERVER_BASE_URL", "https://example.ngrok.io/")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        twiml = build_incoming_twiml("CA1")
    finally:
        get_settings.cache_clear()

    xml = twiml.to_xml()
    assert "wss://example.ngrok.io/ws/media-stream/CA1" in xml


def test_empty_response_is_valid_twiml():
    xml = build_empty_response().to_xml()
    assert "<Response" in xml