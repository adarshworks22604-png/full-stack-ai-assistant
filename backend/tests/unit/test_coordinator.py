import asyncio

import pytest

from app.core.admission import AdmissionController
from app.core.errors import AppError
from app.core.security import Principal
from app.schemas.chat import ChatRequest
from app.schemas.events import AssistantFinal, RequestError, RequestStarted
from app.services.coordinator import ChatCoordinator
from app.services.request_registry import RequestRegistry
from tests.conftest import make_settings

P = Principal(user_id="alice", products=frozenset({"payments"}))
REQ = ChatRequest(message="hi")
RID = "req_" + "a" * 32


class Scripted:
    def __init__(self, events=None, *, raises=None, sleep=0.0):
        self.events, self.raises, self.sleep = events or [], raises, sleep

    async def stream(self, principal, request_id, payload):
        for e in self.events:
            yield e
        if self.sleep:
            await asyncio.sleep(self.sleep)
        if self.raises:
            raise self.raises


def make(service, **settings):
    registry = RequestRegistry()
    admission = AdmissionController(rate_limit_per_minute=100, max_global=5, max_per_user=2)
    coord = ChatCoordinator(
        chat_service=service, registry=registry, admission=admission, settings=make_settings(**settings)
    )
    return coord, registry


async def run_all(coord, principal=P):
    slot = coord.admit(principal)
    return [e async for e in coord.run(principal, RID, REQ, slot)]


FINAL = AssistantFinal(request_id=RID, answer="ok", sources=[])


async def test_normal_run_ends_with_done_and_records_completion():
    coord, registry = make(Scripted([RequestStarted(request_id=RID), FINAL]))
    events = await run_all(coord)
    assert [e.type for e in events] == ["request.started", "assistant.final", "request.done"]
    assert registry.get_for_user(RID, "alice").status == "complete"
    assert coord.active_requests == 0


async def test_unexpected_exception_is_hidden_and_logged_not_returned():
    coord, registry = make(Scripted([RequestStarted(request_id=RID)], raises=RuntimeError("secret-token-123")))
    events = await run_all(coord)
    assert [e.type for e in events] == ["request.started", "request.error", "request.done"]
    assert "secret-token-123" not in events[1].model_dump_json()
    assert events[1].error_code == "INTERNAL_ERROR" and events[1].retryable
    assert registry.get_for_user(RID, "alice").status == "failed" and coord.active_requests == 0


async def test_deadline_produces_a_timeout_error_and_frees_the_slot():
    coord, registry = make(Scripted(sleep=2), request_timeout_seconds=0.05)
    events = await run_all(coord)
    assert events[0].type == "request.error" and events[0].error_code == "UPSTREAM_TIMEOUT"
    assert events[-1].type == "request.done"
    assert registry.get_for_user(RID, "alice").status == "failed" and coord.active_requests == 0


async def test_stream_without_a_terminal_event_is_an_error():
    coord, _ = make(Scripted([RequestStarted(request_id=RID)]))
    events = await run_all(coord)
    assert events[-2].type == "request.error" and events[-1].type == "request.done"


async def test_closing_early_marks_cancelled_and_releases():
    coord, registry = make(Scripted([RequestStarted(request_id=RID), FINAL]))
    slot = coord.admit(P)
    gen = coord.run(P, RID, REQ, slot)
    await gen.__anext__()
    await gen.aclose()
    assert registry.get_for_user(RID, "alice").status == "cancelled" and coord.active_requests == 0


async def test_complete_returns_the_final_answer():
    coord, _ = make(Scripted([RequestStarted(request_id=RID), FINAL]))
    result = await coord.complete(P, RID, REQ)
    assert result.answer == "ok" and result.request_id == RID


async def test_complete_maps_error_events_to_http_errors():
    err = RequestError(request_id=RID, error_code="UPSTREAM_TIMEOUT", message="slow", retryable=True)
    coord, _ = make(Scripted([RequestStarted(request_id=RID), err]))
    with pytest.raises(AppError) as exc:
        await coord.complete(P, RID, REQ)
    assert exc.value.status_code == 504 and exc.value.code == "UPSTREAM_TIMEOUT" and exc.value.retryable
