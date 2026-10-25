"""Async HTTP client for internal APIs: fixed base URL, timeouts, bounded retries, size cap.

Callers pass validated path segments only; the base URL comes from server config, so neither
the user nor the model can point requests at an arbitrary host (SSRF).
"""

import asyncio
import json
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.integrations.base import (
    UpstreamBadResponse,
    UpstreamRateLimited,
    UpstreamTimeout,
    UpstreamUnauthorized,
    UpstreamUnavailable,
)

log = logging.getLogger(__name__)
_RETRY_STATUSES = {502, 503, 504}
_MAX_RETRY_AFTER = 5.0


class ResilientHttpClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        name: str,
        max_retries: int,
        backoff_base: float,
        backoff_max: float,
        max_response_bytes: int,
        limiter: asyncio.Semaphore,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self._client = client
        self._name = name
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._max_bytes = max_response_bytes
        self._limiter = limiter
        self._sleep = sleep
        self._jitter = jitter

    @classmethod
    def create(
        cls,
        *,
        name: str,
        base_url: str,
        token: str,
        connect: float,
        read: float,
        write: float,
        pool: float,
        limiter: asyncio.Semaphore,
        max_retries: int,
        backoff_base: float,
        backoff_max: float,
        max_response_bytes: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> "ResilientHttpClient":
        client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=httpx.Timeout(connect=connect, read=read, write=write, pool=pool),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            follow_redirects=False,  # a redirect could send the credential to another host
            transport=transport,
        )
        return cls(
            client,
            name=name,
            max_retries=max_retries,
            backoff_base=backoff_base,
            backoff_max=backoff_max,
            max_response_bytes=max_response_bytes,
            limiter=limiter,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _delay(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return min(retry_after, _MAX_RETRY_AFTER)
        ceiling = min(self._backoff_max, self._backoff_base * (2**attempt))
        return self._jitter(0, ceiling)  # full jitter

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any | None:
        """GET and parse JSON. Returns None on 404. Raises an UpstreamError subclass otherwise."""
        attempt = 0
        while True:
            retry_after: float | None = None
            try:
                async with self._limiter:
                    return await self._once(path, params)
            except UpstreamRateLimited as exc:
                error: Exception = exc
                retry_after = exc.retry_after
            except (UpstreamUnavailable, UpstreamTimeout) as exc:
                error = exc
            if attempt >= self._max_retries:
                raise error
            await self._sleep(self._delay(attempt, retry_after))
            attempt += 1

    async def _once(self, path: str, params: dict[str, Any] | None) -> Any | None:
        try:
            async with self._client.stream("GET", path, params=params) as response:
                status = response.status_code
                if status == 404:
                    return None
                if status in (401, 403):
                    log.error("%s rejected our credential (HTTP %s)", self._name, status)
                    raise UpstreamUnauthorized(f"{self._name} rejected credentials")
                if status == 429:
                    raise UpstreamRateLimited(
                        f"{self._name} rate limited", _parse_retry_after(response.headers.get("retry-after"))
                    )
                if status in _RETRY_STATUSES:
                    raise UpstreamUnavailable(f"{self._name} unavailable (HTTP {status})")
                if status != 200:
                    raise UpstreamBadResponse(f"{self._name} returned unexpected HTTP {status}")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self._max_bytes:
                        raise UpstreamBadResponse(f"{self._name} response too large")
        except httpx.TimeoutException:
            raise UpstreamTimeout(f"{self._name} timed out") from None
        except httpx.TransportError:
            raise UpstreamUnavailable(f"{self._name} connection failed") from None
        try:
            return json.loads(bytes(body))
        except ValueError:
            raise UpstreamBadResponse(f"{self._name} returned invalid JSON") from None


def _parse_retry_after(value: str | None) -> float | None:
    try:
        return max(0.0, float(value)) if value is not None else None
    except ValueError:
        return None
