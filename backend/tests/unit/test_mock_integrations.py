import pytest

from app.integrations.base import UpstreamBadResponse, UpstreamRateLimited, UpstreamTimeout
from app.integrations.mock import MockBugTrackerClient, MockDocumentationSearchClient


async def test_known_and_unknown_bugs():
    c = MockBugTrackerClient()
    assert (await c.get_bug("BUG-4821")).product == "payments"
    assert await c.get_bug("BUG-9999") is None


@pytest.mark.parametrize(
    ("bug_id", "error"),
    [("BUG-5000", UpstreamTimeout), ("BUG-5001", UpstreamRateLimited), ("BUG-5002", UpstreamBadResponse)],
)
async def test_fault_injection_ids(bug_id, error):
    with pytest.raises(error):
        await MockBugTrackerClient().get_bug(bug_id)


async def test_docs_search_respects_product_access():
    c = MockDocumentationSearchClient()
    q = "invoice export drops rows"
    assert [d.source_id for d in await c.search(q, products=frozenset({"billing"}))] == ["DOC-003"]
    assert await c.search(q, products=frozenset({"payments"})) == []
    assert await c.search(q, products=frozenset()) == []
    assert [d.source_id for d in await c.search(q, products=frozenset({"*"}))] == ["DOC-003"]


async def test_docs_search_with_no_matches():
    assert await MockDocumentationSearchClient().search("zzz qqq", products=None) == []
