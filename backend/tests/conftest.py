import time
from collections.abc import Callable
from typing import Any

import httpx
import jwt

from app.api.container import build_container
from app.core.config import Settings
from app.core.security import DEV_AUDIENCE, DEV_ISSUER
from app.main import FastAPI, create_app

SECRET = "unit-test-secret-0123456789-abcdefghijklmnop"


def make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "app_env": "local",
        "auth_mode": "dev",
        "dev_jwt_secret": SECRET,
        "mock_step_delay_seconds": 0,
        "rate_limit_per_minute": 1000,
        "log_level": "WARNING",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def make_token(
    sub: str = "user-1",
    products: list[str] | None = None,
    *,
    secret: str = SECRET,
    exp_in: int = 3600,
    aud: str = DEV_AUDIENCE,
    iss: str = DEV_ISSUER,
    extra: dict[str, Any] | None = None,
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": sub,
        "iss": iss,
        "aud": aud,
        "iat": now,
        "exp": now + exp_in,
        "products": ["payments", "web-portal"] if products is None else products,
    }
    claims.update(extra or {})
    return jwt.encode(claims, secret, algorithm="HS256")


def auth(token: str | None = None, **kwargs: Any) -> dict[str, str]:
    return {"Authorization": f"Bearer {token or make_token(**kwargs)}"}


def build_app(settings: Settings | None = None, **container_kwargs: Any) -> FastAPI:
    settings = settings or make_settings()
    return create_app(settings, container=build_container(settings, **container_kwargs))


def make_client(app: FastAPI) -> httpx.AsyncClient:
    # raise_app_exceptions=False lets tests see the 500 response a real server would send.
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def parse_sse(text: str) -> list[dict[str, Any]]:
    import json

    events = []
    for block in text.strip().split("\n\n"):
        if not block.strip() or block.startswith(":"):
            continue
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append({"id": int(fields["id"]), "event": fields["event"], "data": json.loads(fields["data"])})
    return events


Factory = Callable[..., httpx.AsyncClient]
