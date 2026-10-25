import pytest

from tests.conftest import auth, build_app, make_client

STREAM = "/api/v1/chat/stream"


async def run(c, sub="alice", message="status?", subject="BUG-4821"):
    r = await c.post(
        STREAM, headers=auth(sub=sub), json={"message": message, "email_context": {"subject": subject, "body_text": ""}}
    )
    return r.headers["x-request-id"]


async def test_owner_can_read_request_status():
    async with make_client(build_app()) as c:
        rid = await run(c)
        ok = await c.get(f"/api/v1/requests/{rid}", headers=auth(sub="alice"))
        failed_id = await run(c, message="simulate error")
        failed = await c.get(f"/api/v1/requests/{failed_id}", headers=auth(sub="alice"))
    assert ok.status_code == 200 and ok.json()["status"] == "complete" and ok.json()["request_id"] == rid
    assert failed.json()["status"] == "failed"


async def test_other_users_and_unknown_ids_look_identical():
    async with make_client(build_app()) as c:
        rid = await run(c, sub="alice")
        other = await c.get(f"/api/v1/requests/{rid}", headers=auth(sub="mallory"))
        unknown = await c.get("/api/v1/requests/req_" + "0" * 32, headers=auth(sub="alice"))
    assert other.status_code == unknown.status_code == 404
    assert other.json()["error"]["code"] == unknown.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize("bad", ["abc", "req_short", "REQ_" + "a" * 32, "req_" + "g" * 32, "../admin"])
async def test_malformed_request_ids_are_rejected(bad):
    async with make_client(build_app()) as c:
        r = await c.get(f"/api/v1/requests/{bad}", headers=auth())
    assert r.status_code in (404, 422)


async def test_feedback_is_recorded_with_minimal_metadata():
    app = build_app()
    async with make_client(app) as c:
        rid = await run(c)
        r = await c.post(
            "/api/v1/feedback",
            headers=auth(sub="alice"),
            json={"request_id": rid, "rating": "down", "reason": "incorrect"},
        )
    assert r.status_code == 200 and r.json() == {"status": "recorded"}
    (record,) = app.state.container.feedback.all()
    assert (record.request_id, record.user_id, record.rating, record.reason) == (rid, "alice", "down", "incorrect")
    assert set(vars(record)) == {"request_id", "user_id", "rating", "reason", "created_at"}  # no email or answer text


async def test_feedback_for_someone_elses_request_is_not_found():
    app = build_app()
    async with make_client(app) as c:
        rid = await run(c, sub="alice")
        r = await c.post("/api/v1/feedback", headers=auth(sub="mallory"), json={"request_id": rid, "rating": "up"})
    assert r.status_code == 404 and app.state.container.feedback.all() == []


@pytest.mark.parametrize(
    "extra",
    [
        {"rating": "great"},
        {"reason": "free text with email body"},
        {"comment": "my email said..."},
        {"request_id": "nope"},
        {"rating": None},
    ],
)
async def test_feedback_validation(extra):
    async with make_client(build_app()) as c:
        rid = await run(c)
        payload = {"request_id": rid, "rating": "up", **extra}
        r = await c.post("/api/v1/feedback", headers=auth(), json=payload)
    assert r.status_code == 422
