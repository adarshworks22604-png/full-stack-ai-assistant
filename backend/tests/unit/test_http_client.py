import asyncio

import httpx
import pytest

from app.integrations.base import (
    UpstreamBadResponse,
    UpstreamRateLimited,
    UpstreamTimeout,
    UpstreamUnauthorized,
    UpstreamUnavailable,
)
from app.integrations.http_client import ResilientHttpClient


class Harness:
    def __init__(self, handler, *, retries=2, max_bytes=10_000, concurrency=10):
        self.calls = 0
        self.sleeps: list[float] = []

        async def counted(request: httpx.Request):
            self.calls += 1
            result = handler(request, self.calls)
            if isinstance(result, Exception):
                raise result
            return result

        async def fake_sleep(delay: float):
            self.sleeps.append(delay)

        self.client = ResilientHttpClient(
            httpx.AsyncClient(base_url="https://api.invalid", transport=httpx.MockTransport(counted)),
            name="test api",
            max_retries=retries,
            backoff_base=0.2,
            backoff_max=2.0,
            max_response_bytes=max_bytes,
            limiter=asyncio.Semaphore(concurrency),
            sleep=fake_sleep,
            jitter=lambda _lo, hi: hi,  # deterministic: always the ceiling
        )


def ok(_req, _n):
    return httpx.Response(200, json={"a": 1})


async def test_success_returns_parsed_json():
    h = Harness(ok)
    assert await h.client.get_json("/x") == {"a": 1}
    assert h.calls == 1 and h.sleeps == []


async def test_retries_503_then_succeeds_with_exponential_backoff():
    h = Harness(lambda r, n: httpx.Response(503) if n < 3 else httpx.Response(200, json={"ok": True}), retries=3)
    assert await h.client.get_json("/x") == {"ok": True}
    assert h.calls == 3 and h.sleeps == [0.2, 0.4]


async def test_gives_up_after_bounded_retries():
    h = Harness(lambda r, n: httpx.Response(503), retries=2)
    with pytest.raises(UpstreamUnavailable):
        await h.client.get_json("/x")
    assert h.calls == 3  # first try + 2 retries, never unbounded


async def test_backoff_is_capped():
    h = Harness(lambda r, n: httpx.Response(503), retries=5)
    with pytest.raises(UpstreamUnavailable):
        await h.client.get_json("/x")
    assert max(h.sleeps) <= 2.0


async def test_429_honours_retry_after_but_caps_it():
    h = Harness(
        lambda r, n: httpx.Response(429, headers={"Retry-After": "2"}) if n == 1 else httpx.Response(200, json=1)
    )
    assert await h.client.get_json("/x") == 1
    assert h.sleeps == [2.0]
    h2 = Harness(lambda r, n: httpx.Response(429, headers={"Retry-After": "9999"}), retries=1)
    with pytest.raises(UpstreamRateLimited):
        await h2.client.get_json("/x")
    assert h2.sleeps == [5.0]


async def test_timeouts_are_retried_then_reported_as_timeout():
    h = Harness(lambda r, n: httpx.ReadTimeout("slow"), retries=1)
    with pytest.raises(UpstreamTimeout):
        await h.client.get_json("/x")
    assert h.calls == 2


async def test_connection_errors_become_unavailable():
    h = Harness(lambda r, n: httpx.ConnectError("refused"), retries=1)
    with pytest.raises(UpstreamUnavailable):
        await h.client.get_json("/x")
    assert h.calls == 2


@pytest.mark.parametrize("status", [401, 403])
async def test_credential_rejection_is_not_retried(status):
    h = Harness(lambda r, n: httpx.Response(status))
    with pytest.raises(UpstreamUnauthorized):
        await h.client.get_json("/x")
    assert h.calls == 1


async def test_404_returns_none_without_retry():
    h = Harness(lambda r, n: httpx.Response(404))
    assert await h.client.get_json("/x") is None and h.calls == 1


@pytest.mark.parametrize("status", [400, 418, 500, 302])
async def test_other_statuses_are_bad_responses_and_not_retried(status):
    h = Harness(lambda r, n: httpx.Response(status))
    with pytest.raises(UpstreamBadResponse):
        await h.client.get_json("/x")
    assert h.calls == 1  # a redirect is never followed either


async def test_invalid_json_is_a_bad_response():
    h = Harness(lambda r, n: httpx.Response(200, content=b"<html>not json"))
    with pytest.raises(UpstreamBadResponse):
        await h.client.get_json("/x")


async def test_oversized_response_is_rejected():
    h = Harness(lambda r, n: httpx.Response(200, content=b'{"a":"' + b"x" * 5000 + b'"}'), max_bytes=1000)
    with pytest.raises(UpstreamBadResponse):
        await h.client.get_json("/x")


async def test_concurrency_is_limited():
    active = 0
    peak = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(200, json={})

    client = ResilientHttpClient(
        httpx.AsyncClient(base_url="https://api.invalid", transport=httpx.MockTransport(handler)),
        name="t",
        max_retries=0,
        backoff_base=0,
        backoff_max=0,
        max_response_bytes=1000,
        limiter=asyncio.Semaphore(2),
    )
    await asyncio.gather(*(client.get_json("/x") for _ in range(8)))
    assert peak <= 2


async def test_create_sets_fixed_base_url_and_credential_header():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    client = ResilientHttpClient.create(
        name="t",
        base_url="https://bugs.internal",
        token="svc-token",
        connect=1,
        read=1,
        write=1,
        pool=1,
        limiter=asyncio.Semaphore(1),
        max_retries=0,
        backoff_base=0,
        backoff_max=0,
        max_response_bytes=1000,
        transport=httpx.MockTransport(handler),
    )
    await client.get_json("/bugs/BUG-1")
    await client.aclose()
    assert seen[0].url.host == "bugs.internal"
    assert seen[0].headers["authorization"] == "Bearer svc-token"
