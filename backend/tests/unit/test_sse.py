import asyncio
import json

from app.api.sse import encode_event, event_stream
from app.schemas.events import AssistantDelta, RequestDone


class FakeRequest:
    def __init__(self, disconnected=False):
        self.disconnected = disconnected

    async def is_disconnected(self):
        return self.disconnected


def test_frame_format_and_json_safety():
    frame = encode_event(AssistantDelta(request_id="r", text="line1\nline2\r\n data: injected"), 7).decode()
    lines = frame.split("\n")
    assert lines[0] == "id: 7" and lines[1] == "event: assistant.delta"
    assert frame.endswith("\n\n")
    # exactly one data line: newlines inside the text are JSON-escaped, so frames cannot be forged
    assert sum(1 for line in lines if line.startswith("data: ")) == 1
    assert json.loads(lines[2][6:])["text"] == "line1\nline2\r\n data: injected"


async def collect(gen):
    return [chunk async for chunk in gen]


async def test_stream_sends_events_with_increasing_ids_and_calls_on_close_once():
    closed = []

    async def events():
        yield AssistantDelta(request_id="r", text="a")
        yield RequestDone(request_id="r")

    chunks = await collect(
        event_stream(FakeRequest(), events(), heartbeat_seconds=5, request_id="r", on_close=lambda: closed.append(1))
    )
    assert [c.split(b"\n")[0] for c in chunks] == [b"id: 1", b"id: 2"]
    assert closed == [1]


async def test_heartbeat_comments_are_sent_while_the_producer_is_slow():
    async def events():
        await asyncio.sleep(0.12)
        yield RequestDone(request_id="r")

    chunks = await collect(
        event_stream(FakeRequest(), events(), heartbeat_seconds=0.03, request_id="r", on_close=lambda: None)
    )
    assert chunks.count(b": keep-alive\n\n") >= 2 and chunks[-1].startswith(b"id: 1")


async def test_disconnect_stops_the_producer_and_releases():
    closed, cancelled = [], []

    async def events():
        try:
            await asyncio.sleep(10)
            yield RequestDone(request_id="r")
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    chunks = await collect(
        event_stream(
            FakeRequest(disconnected=True),
            events(),
            heartbeat_seconds=0.02,
            request_id="r",
            on_close=lambda: closed.append(1),
        )
    )
    assert chunks == [] and closed == [1] and cancelled == [True]


async def test_producer_crash_becomes_a_safe_error_event():
    async def events():
        raise RuntimeError("secret-token-123")
        yield  # pragma: no cover

    chunks = await collect(
        event_stream(FakeRequest(), events(), heartbeat_seconds=5, request_id="r", on_close=lambda: None)
    )
    text = b"".join(chunks).decode()
    assert "request.error" in text and "INTERNAL_ERROR" in text and "secret-token-123" not in text
