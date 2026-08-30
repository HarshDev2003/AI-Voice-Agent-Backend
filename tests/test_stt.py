import asyncio
import json

from app.stt.deepgram_stt import DeepgramSTT, build_listen_uri, parse_live_message


class FakeWebsocket:
    def __init__(self, messages):
        self._messages = list(messages)
        self.sent: list = []
        self.closed = False

    async def send(self, chunk: bytes):
        self.sent.append(chunk)

    async def recv(self):
        if self._messages:
            return self._messages.pop(0)
        raise RuntimeError("connection ended")

    async def close(self):
        self.closed = True


def test_build_listen_uri_has_required_params():
    uri = build_listen_uri("nova-3")
    assert uri.startswith("wss://api.deepgram.com/v1/listen?")
    assert "model=nova-3" in uri
    assert "encoding=mulaw" in uri
    assert "sample_rate=8000" in uri
    assert "interim_results=true" in uri
    assert "endpointing=500" in uri


def test_build_listen_uri_allows_language():
    uri = build_listen_uri("nova-3", language="hi")
    assert "language=hi" in uri


def test_parse_live_message_final_and_text():
    msg = json.dumps(
        {
            "type": "Results",
            "is_final": True,
            "channel": {"alternatives": [{"transcript": "Hello there"}]},
        }
    )
    is_final, text = parse_live_message(msg)
    assert is_final is True
    assert text == "Hello there"


def test_parse_live_message_interim_is_not_final():
    msg = {
        "type": "Results",
        "is_final": False,
        "channel": {"alternatives": [{"transcript": "Hel"}]},
    }
    is_final, text = parse_live_message(msg)
    assert is_final is False
    assert text == "Hel"


def test_parse_live_message_ignores_metadata_and_empty():
    assert parse_live_message({"type": "Metadata"}) == (False, "")
    assert parse_live_message("not json") == (False, "")
    msg = {"type": "Results", "is_final": True, "channel": {"alternatives": [{"transcript": "  "}]}}
    assert parse_live_message(msg) == (True, "")


def test_stt_connect_send_and_yield_final_transcripts():
    messages = [
        json.dumps(
            {
                "type": "Results",
                "is_final": True,
                "channel": {"alternatives": [{"transcript": "hi"}]},
            }
        ),
        json.dumps(
            {
                "type": "Results",
                "is_final": True,
                "channel": {"alternatives": [{"transcript": "there"}]},
            }
        ),
    ]
    ws = FakeWebsocket(messages)
    seen_extra_headers = {}

    async def connector(uri, additional_headers):
        seen_extra_headers["uri"] = uri
        seen_extra_headers["auth"] = additional_headers.get("Authorization")
        return ws

    stt = DeepgramSTT(api_key="test-key", ws_connect=connector)

    async def run():
        await stt.connect()
        await stt.send_audio(b"\x00\x01")
        finals = []
        async for text in stt.transcript_stream():
            finals.append(text)
        await stt.close()
        return finals

    finals = asyncio.run(run())
    assert finals == ["hi", "there"]
    assert ws.sent == [b"\x00\x01"]
    assert ws.closed is True
    assert seen_extra_headers["auth"] == "Token test-key"
    assert "encoding=mulaw" in seen_extra_headers["uri"]