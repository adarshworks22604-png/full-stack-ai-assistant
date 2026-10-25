import pytest

from app.core.admission import AdmissionController
from app.core.errors import RateLimitedError, ServerBusyError


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(clock=None, rate=3, glob=10, per_user=2):
    return AdmissionController(
        rate_limit_per_minute=rate, max_global=glob, max_per_user=per_user, clock=clock or Clock()
    )


def test_rate_limit_blocks_then_recovers_as_the_window_slides():
    clock = Clock()
    c = make(clock, rate=2, per_user=10)
    for _ in range(2):
        c.admit("u").release()
    with pytest.raises(RateLimitedError) as exc:
        c.admit("u")
    assert int(exc.value.headers["Retry-After"]) >= 1 and exc.value.retryable
    clock.now += 61
    c.admit("u").release()


def test_rate_limit_is_per_user():
    c = make(rate=1, per_user=10)
    c.admit("a").release()
    c.admit("b").release()
    with pytest.raises(RateLimitedError):
        c.admit("a")


def test_per_user_concurrency_limit_and_release_frees_a_slot():
    c = make(rate=100, per_user=2)
    a1, _a2 = c.admit("u"), c.admit("u")
    with pytest.raises(RateLimitedError):
        c.admit("u")
    a1.release()
    c.admit("u")


def test_global_limit_returns_server_busy():
    c = make(rate=100, glob=2, per_user=5)
    c.admit("a")
    c.admit("b")
    with pytest.raises(ServerBusyError) as exc:
        c.admit("c")
    assert exc.value.status_code == 503 and exc.value.retryable


def test_release_is_idempotent():
    c = make(rate=100)
    slot = c.admit("u")
    slot.release()
    slot.release()
    slot.release()
    assert c.active_total == 0
    c.admit("u")
    assert c.active_total == 1


def test_rejected_requests_do_not_consume_slots():
    c = make(rate=100, per_user=1)
    c.admit("u")
    for _ in range(5):
        with pytest.raises(RateLimitedError):
            c.admit("u")
    assert c.active_total == 1
