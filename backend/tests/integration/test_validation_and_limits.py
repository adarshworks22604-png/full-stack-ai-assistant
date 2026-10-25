import pytest

from tests.conftest import auth, build_app, make_client, make_settings

URL = "/api/v1/chat"


@pytest.fixture
def app():
    return build_app()


@pytest.fixture
def small_app():
    return build_app(make_settings(max_request_body_bytes=4096))


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": ""},
        {"message": "   \n\t "},
        {"message": 123},
        {"message": None},
        {"message": "x" * 8001},
        {"message": "hi", "user_id": "admin"},  # identity can never come from the body
        {"message": "hi", "conversation_id": "bad id!"},
        {"message": "hi", "email_context": {"subject": "s"}},
        {"message": "hi", "email_context": {"subject": "s" * 501, "body_text": ""}},
        {"message": "hi", "email_context": {"subject": "s", "body_text": "b" * 8001}},
        {"message": "hi", "email_context": {"subject": "s", "body_text": "ok", "extra": 1}},
        {"message": "hi", "email_context": "not an object"},
    ],
)
async def test_invalid_bodies_are_rejected_with_422(app, payload):
    async with make_client(app) as c:
        r = await c.post(URL, headers=auth(), json=payload)
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "INVALID_REQUEST" and error["retryable"] is False and error["details"]


async def test_validation_errors_never_echo_submitted_values(app):
    secret = "TOPSECRET-EMAIL-BODY-xyz"
    async with make_client(app) as c:
        r = await c.post(
            URL,
            headers=auth(),
            json={"message": "hi", "email_context": {"subject": "s", "body_text": secret, "extra": secret}},
        )
        r2 = await c.post(URL, headers=auth(), json={"message": 12345678901})
    assert r.status_code == 422 and secret not in r.text
    assert "12345678901" not in r2.text


async def test_boundary_values_are_accepted(app):
    async with make_client(app) as c:
        r = await c.post(
            URL,
            headers=auth(),
            json={"message": "m" * 8000, "email_context": {"subject": "s" * 500, "body_text": "b" * 8000}},
        )
    assert r.status_code == 200


@pytest.mark.parametrize("content", [b"{not json", b"", b"[]", b'"string"'])
async def test_malformed_json_is_rejected_cleanly(app, content):
    async with make_client(app) as c:
        r = await c.post(URL, headers={**auth(), "Content-Type": "application/json"}, content=content)
    assert r.status_code == 422 and "Traceback" not in r.text


async def test_wrong_content_type_is_rejected(app):
    async with make_client(app) as c:
        r = await c.post(URL, headers={**auth(), "Content-Type": "text/plain"}, content=b'{"message": "hi"}')
    assert r.status_code == 422


async def test_oversized_body_with_content_length_gets_413(small_app):
    async with make_client(small_app) as c:
        r = await c.post(URL, headers=auth(), json={"message": "x" * 5000})
    assert r.status_code == 413
    assert (
        r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
        and r.json()["error"]["request_id"] == r.headers["x-request-id"]
    )


async def test_oversized_chunked_body_without_content_length_gets_413(small_app):
    async def chunks():
        for _ in range(10):
            yield b"x" * 1000

    async with make_client(small_app) as c:
        r = await c.post(URL, headers={**auth(), "Content-Type": "application/json"}, content=chunks())
    assert r.status_code == 413


async def test_small_chunked_body_is_replayed_to_the_app(small_app):
    async def chunks():
        yield b'{"message": '
        yield b'"What is BUG-4821?"}'

    async with make_client(small_app) as c:
        r = await c.post(URL, headers={**auth(), "Content-Type": "application/json"}, content=chunks())
    assert r.status_code == 200 and "BUG-4821" in r.json()["answer"]


async def test_oversized_body_is_rejected_before_authentication_work(small_app):
    async with make_client(small_app) as c:
        r = await c.post(URL, json={"message": "x" * 5000})  # no token at all
    assert r.status_code == 413
