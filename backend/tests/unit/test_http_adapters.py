import asyncio

import httpx
import pytest

from app.integrations.base import UpstreamBadResponse
from app.integrations.http_adapters import HttpBugTrackerClient, HttpDocumentationSearchClient
from app.integrations.http_client import ResilientHttpClient

BUG = {
    "id": "BUG-4821",
    "title": "Payment timeouts",
    "status": "Resolved",
    "product": "payments",
    "internal_notes": "customer ACME is angry",
    "reporter_email": "x@corp.example",
}
DOC = {"source_id": "D1", "title": "Doc", "product": "payments", "excerpt": "e", "uri": "https://example.invalid/d"}


def build(handler):
    requests: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    http = ResilientHttpClient(
        httpx.AsyncClient(base_url="https://api.invalid", transport=httpx.MockTransport(wrapped)),
        name="t",
        max_retries=0,
        backoff_base=0,
        backoff_max=0,
        max_response_bytes=100_000,
        limiter=asyncio.Semaphore(5),
    )
    return http, requests


async def test_bug_fields_are_allowlisted():
    http, reqs = build(lambda r: httpx.Response(200, json=BUG))
    bug = await HttpBugTrackerClient(http).get_bug("BUG-4821")
    assert bug.id == "BUG-4821"
    dumped = bug.model_dump()
    assert "internal_notes" not in dumped and "reporter_email" not in dumped
    assert reqs[0].url.path == "/bugs/BUG-4821"


@pytest.mark.parametrize("bad_id", ["../admin", "BUG-1/../../x", "BUG-1?x=1", "bug-1", "", "BUG-", "BUG-1 OR 1=1"])
async def test_unvalidated_ids_never_reach_the_network(bad_id):
    http, reqs = build(lambda r: httpx.Response(200, json=BUG))
    assert await HttpBugTrackerClient(http).get_bug(bad_id) is None
    assert reqs == []


async def test_missing_bug_is_none():
    http, _ = build(lambda r: httpx.Response(404))
    assert await HttpBugTrackerClient(http).get_bug("BUG-1") is None


@pytest.mark.parametrize("payload", [{"unexpected": True}, [], "text", {**BUG, "id": "BUG-9"}])
async def test_wrong_shape_or_wrong_record_is_a_bad_response(payload):
    http, _ = build(lambda r: httpx.Response(200, json=payload))
    with pytest.raises(UpstreamBadResponse):
        await HttpBugTrackerClient(http).get_bug("BUG-4821")


async def test_docs_results_are_filtered_by_product_even_if_upstream_did_not():
    results = [DOC, {**DOC, "source_id": "D2", "product": "billing"}]
    http, reqs = build(lambda r: httpx.Response(200, json={"results": results}))
    found = await HttpDocumentationSearchClient(http).search("timeouts", products=frozenset({"payments"}))
    assert [d.source_id for d in found] == ["D1"]
    assert reqs[0].url.params["q"] == "timeouts"


async def test_docs_wildcard_and_none_filters():
    results = [DOC, {**DOC, "source_id": "D2", "product": "billing"}]
    http, _ = build(lambda r: httpx.Response(200, json={"results": results}))
    client = HttpDocumentationSearchClient(http)
    assert len(await client.search("q", products=frozenset({"*"}))) == 2
    assert len(await client.search("q", products=None)) == 2


async def test_docs_search_with_no_access_makes_no_request():
    http, reqs = build(lambda r: httpx.Response(200, json={"results": [DOC]}))
    assert await HttpDocumentationSearchClient(http).search("q", products=frozenset()) == []
    assert reqs == []


async def test_malformed_items_are_dropped_but_others_kept():
    http, _ = build(lambda r: httpx.Response(200, json={"results": [{"nope": 1}, DOC]}))
    found = await HttpDocumentationSearchClient(http).search("q", products=frozenset({"payments"}))
    assert [d.source_id for d in found] == ["D1"]


@pytest.mark.parametrize("payload", [{"results": "x"}, {"other": []}, [DOC]])
async def test_docs_wrong_shape_is_a_bad_response(payload):
    http, _ = build(lambda r: httpx.Response(200, json=payload))
    with pytest.raises(UpstreamBadResponse):
        await HttpDocumentationSearchClient(http).search("q", products=None)
