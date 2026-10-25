from app.services.request_registry import RequestRegistry


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_only_the_owner_can_see_a_request():
    r = RequestRegistry()
    r.create("req_a", "alice")
    assert r.get_for_user("req_a", "alice").status == "running"
    assert r.get_for_user("req_a", "bob") is None
    assert r.get_for_user("req_missing", "alice") is None


def test_status_updates():
    r = RequestRegistry()
    r.create("req_a", "alice")
    r.update("req_a", "complete")
    r.update("req_unknown", "failed")  # no error
    assert r.get_for_user("req_a", "alice").status == "complete"


def test_entries_expire():
    clock = Clock()
    r = RequestRegistry(ttl_seconds=10, clock=clock)
    r.create("req_a", "alice")
    clock.now = 11
    assert r.get_for_user("req_a", "alice") is None


def test_size_is_bounded():
    r = RequestRegistry(max_items=3)
    for i in range(10):
        r.create(f"req_{i}", "u")
    assert r.get_for_user("req_0", "u") is None
    assert r.get_for_user("req_9", "u") is not None
