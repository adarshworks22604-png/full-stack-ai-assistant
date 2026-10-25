import pytest
from pydantic import ValidationError

from app.schemas.chat import ChatRequest
from app.schemas.events import AssistantFinal, RequestDone


def test_control_characters_are_removed_but_newlines_kept():
    req = ChatRequest.model_validate(
        {"message": "a\x00b\x07c", "email_context": {"subject": "s\x1f", "body_text": "line1\nline2\x7f"}}
    )
    assert req.message == "abc"
    assert req.email_context.subject == "s" and req.email_context.body_text == "line1\nline2"


def test_message_that_is_only_control_characters_is_rejected():
    with pytest.raises(ValidationError):
        ChatRequest.model_validate({"message": "\x00\x01"})


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        ChatRequest.model_validate({"message": "hi", "user_id": "admin"})


def test_event_serialization_drops_none_fields_and_keeps_type():
    final = AssistantFinal(request_id="r", answer="a", sources=[])
    assert final.model_dump(exclude_none=True)["type"] == "assistant.final"
    assert RequestDone(request_id="r").model_dump() == {"type": "request.done", "request_id": "r"}
