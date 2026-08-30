"""Tests for agent.intent: token detection and response cleaning."""
from app.agent.intent import (
    END_TOKEN,
    TRANSFER_TOKEN,
    Intent,
    clean_response,
    detect_intent,
)


def test_detect_intent_chat_when_no_token():
    assert detect_intent("Hello, how can I help you?") is Intent.CHAT


def test_detect_intent_transfer_when_token_present():
    assert detect_intent("Sure, transferring you now. [TRANSFER]") is Intent.TRANSFER


def test_detect_intent_end_when_end_token_present():
    assert detect_intent("Goodbye! [END_CALL]") is Intent.END


def test_detect_intent_transfer_wins_when_both_present():
    # The check order in detect_intent prioritises transfer.
    text = f"Hold on {TRANSFER_TOKEN} {END_TOKEN}"
    assert detect_intent(text) is Intent.TRANSFER


def test_clean_response_strips_tokens():
    text = f"Connecting you now. {TRANSFER_TOKEN}"
    assert clean_response(text) == "Connecting you now."


def test_clean_response_strips_both_tokens():
    text = f"Thanks. {TRANSFER_TOKEN} {END_TOKEN}"
    assert clean_response(text) == "Thanks."


def test_clean_response_handles_no_token():
    assert clean_response("Just a normal reply.") == "Just a normal reply."


def test_clean_response_trims_whitespace():
    text = f"  bye {END_TOKEN}  "
    assert clean_response(text) == "bye"
