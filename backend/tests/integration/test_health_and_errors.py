import re

import pytest

from app.integrations.base import UpstreamTimeout
from tests.conftest import auth, build_app, make_client, make_settings, make_token

REQ_ID = re.compile(r"^req_[0-9a-f]{32}$")


async def test_health_endpoints_need_no_auth_and_reveal_nothing():
    async with make_client(build_app()) as c:
        live = await c.get("/health/live")
        ready = await c.get("/health/ready")
    assert live.status_code == 200 and live.json() == {"status": "ok"}
    assert ready.status_code == 200 and ready.json() == {"status": "ready"}


async def test_api_docs_are_only_available_locally():
    settings = make_settings(
        app_env="staging", auth_mode="entra", dev_jwt_secret=None, entra_tenant_id="t", entra_audience="a"
    )
    async with make_client(build_app(settings)) as c:
        assert (await c.get("/docs")).status_code == 404
        assert (await c.get("/openapi.json")).status_code == 404
        assert (await c.get("/health/live")).status_code == 200
    async with make_client(build_app()) as c:
        assert (await c.get("/openapi.json")).status_code == 200


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/v1/chat"),
        ("POST", "/api/v1/chat/stream"),
        ("POST", "/api/v1/feedback"),
        ("GET", "/api/v1/requests/req_" + "a" * 32),
    ],
)
async def test_every_protected_endpoint_requires_a_valid_token(method, path):
    async with make_client(build_app()) as c:
        for headers in (
            {},
            {"Authorization": "Bearer nonsense"},
            {"Authorization": "Basic abc"},
            auth(exp_in=-100),
            auth(secret="z" * 40),
            auth(aud="other"),
        ):
            r = await c.request(method, path, headers=headers, json={"message": "hi"})
            assert r.status_code == 401, (path, headers)
            assert r.headers["www-authenticate"] == "Bearer"
            assert r.json()["error"]["code"] == "UNAUTHORIZED"


async def test_error_format_is_consistent_and_ties_to_the_request_id_header():
    async with make_client(build_app()) as c:
        r = await c.post("/api/v1/chat", json={"message": "hi"})
    body = r.json()["error"]
    assert set(body) == {"code", "message", "retryable", "request_id"}
    assert body["request_id"] == r.headers["x-request-id"] and REQ_ID.match(body["request_id"])


async def test_client_supplied_request_ids_are_ignored():
    async with make_client(build_app()) as c:
        r = await c.get("/health/live", headers={"X-Request-ID": "attacker-chosen"})
    assert r.headers["x-request-id"] != "attacker-chosen" and REQ_ID.match(r.headers["x-request-id"])


async def test_each_request_gets_a_distinct_id():
    async with make_client(build_app()) as c:
        ids = {(await c.get("/health/live")).headers["x-request-id"] for _ in range(5)}
    assert len(ids) == 5


async def test_unknown_routes_and_wrong_methods_use_the_same_format():
    async with make_client(build_app()) as c:
        nf = await c.get("/nope")
        bad = await c.get("/api/v1/chat")
    assert nf.status_code == 404 and nf.json()["error"]["code"] == "NOT_FOUND"
    assert bad.status_code == 405 and bad.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


async def test_unhandled_exceptions_return_a_generic_500_without_internals():
    app = build_app()

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret-token-123 at /srv/internal/db.py")

    async with make_client(app) as c:
        r = await c.get("/boom")
    assert r.status_code == 500
    text = r.text
    assert "secret-token-123" not in text and "Traceback" not in text and "/srv/" not in text
    assert (
        r.json()["error"]["code"] == "INTERNAL_ERROR" and r.json()["error"]["request_id"] == r.headers["x-request-id"]
    )


async def test_security_headers_are_present():
    async with make_client(build_app()) as c:
        r = await c.get("/health/live")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store" and r.headers["referrer-policy"] == "no-referrer"


async def test_cors_allows_only_configured_origins():
    async with make_client(build_app()) as c:
        ok = await c.get("/health/live", headers={"Origin": "https://localhost:3000"})
        evil = await c.get("/health/live", headers={"Origin": "https://evil.example"})
        preflight = await c.options(
            "/api/v1/chat/stream",
            headers={
                "Origin": "https://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        bad_preflight = await c.options(
            "/api/v1/chat/stream",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
        )
    assert ok.headers["access-control-allow-origin"] == "https://localhost:3000"
    assert "x-request-id" in ok.headers["access-control-expose-headers"].lower()
    assert "access-control-allow-origin" not in evil.headers
    assert preflight.status_code == 200 and "authorization" in preflight.headers["access-control-allow-headers"].lower()
    assert bad_preflight.status_code == 400


async def test_readiness_fails_closed_when_a_dependency_is_missing():
    app = build_app()
    app.state.container.verifier = None
    async with make_client(app) as c:
        r = await c.get("/health/ready")
    assert r.status_code == 503 and r.json() == {"status": "not_ready"}
    assert (await make_client(app).get("/health/live")).status_code == 200


async def test_token_is_never_echoed_in_responses():
    token = make_token(exp_in=-100)
    async with make_client(build_app()) as c:
        r = await c.post("/api/v1/chat", headers=auth(token), json={"message": "hi"})
    assert token not in r.text and r.status_code == 401


class _SlowDocs:
    async def search(self, *a, **k):
        raise UpstreamTimeout("x")


async def test_upstream_failures_never_surface_as_stack_traces():
    app = build_app(docs=_SlowDocs())
    async with make_client(app) as c:
        r = await c.post("/api/v1/chat", headers=auth(), json={"message": "status of BUG-4821?"})
    assert r.status_code == 200 and "Traceback" not in r.text
