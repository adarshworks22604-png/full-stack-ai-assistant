"""Server-Sent Events transport: encoding, heartbeats, and disconnect handling."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Callable

from fastapi import Request

from app.schemas.events import AnyEvent, RequestError

log = logging.getLogger(__name__)


class _Done:
    """Sentinel marking the end of the producer's events."""


_DONE = _Done()
SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",  # stop nginx-style proxies from buffering the stream
    "Connection": "keep-alive",
}


def encode_event(event: AnyEvent, event_id: int) -> bytes:
    """One SSE frame. JSON never contains raw newlines, so a single data line is safe."""
    name = event.type
    data = event.model_dump_json(exclude_none=True)
    return f"id: {event_id}\nevent: {name}\ndata: {data}\n\n".encode()


async def event_stream(
    request: Request,
    events: AsyncIterator[AnyEvent],
    *,
    heartbeat_seconds: float,
    request_id: str,
    on_close: Callable[[], None],
) -> AsyncIterator[bytes]:
    """Pump events through a queue so heartbeats can be sent while the producer is busy."""
    queue: asyncio.Queue[AnyEvent | _Done] = asyncio.Queue(maxsize=64)

    async def produce() -> None:
        try:
            async for event in events:
                await queue.put(event)
        except Exception:  # noqa: BLE001 - the coordinator already maps errors; this is a last resort
            log.exception("event producer crashed")
            await queue.put(
                RequestError(
                    request_id=request_id,
                    error_code="INTERNAL_ERROR",
                    message="Something went wrong on our side. Try again.",
                    retryable=True,
                )
            )
        finally:
            await queue.put(_DONE)

    task = asyncio.create_task(produce())
    event_id = 0
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
            except TimeoutError:
                if await request.is_disconnected():
                    break
                yield b": keep-alive\n\n"
                continue
            if isinstance(item, _Done):
                break
            event_id += 1
            yield encode_event(item, event_id)
    finally:
        # Client left or stream finished: stop any unfinished work and free the slot.
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
        with contextlib.suppress(Exception):
            await events.aclose()  # type: ignore[attr-defined]
        on_close()
