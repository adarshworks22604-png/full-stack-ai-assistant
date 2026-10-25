"""Mock integrations backed by synthetic JSON. Used locally and in tests; never real data.

Special bug IDs simulate upstream faults so failure paths can be exercised end to end:
  BUG-5000 -> timeout, BUG-5001 -> rate limited, BUG-5002 -> malformed response.
"""

import json
import re
from pathlib import Path

from app.integrations.base import UpstreamBadResponse, UpstreamRateLimited, UpstreamTimeout
from app.integrations.models import BugRecord, DocPassage

DATA_DIR = Path(__file__).parent / "mock_data"
_STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "on",
    "in",
    "to",
    "and",
    "or",
    "is",
    "are",
    "for",
    "with",
    "under",
    "over",
    "from",
}


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in _STOPWORDS}


class MockBugTrackerClient:
    def __init__(self) -> None:
        records = json.loads((DATA_DIR / "bugs.json").read_text(encoding="utf-8"))
        self._bugs = {r["id"]: BugRecord.model_validate(r) for r in records}

    async def get_bug(self, bug_id: str) -> BugRecord | None:
        if bug_id == "BUG-5000":
            raise UpstreamTimeout("mock bug tracker timeout")
        if bug_id == "BUG-5001":
            raise UpstreamRateLimited("mock bug tracker rate limited")
        if bug_id == "BUG-5002":
            raise UpstreamBadResponse("mock bug tracker returned malformed data")
        return self._bugs.get(bug_id)


class MockDocumentationSearchClient:
    def __init__(self) -> None:
        records = json.loads((DATA_DIR / "docs.json").read_text(encoding="utf-8"))
        self._docs = [DocPassage.model_validate(r) for r in records]

    async def search(self, query: str, *, products: frozenset[str] | None, limit: int = 3) -> list[DocPassage]:
        wanted = _tokens(query)
        scored: list[tuple[int, DocPassage]] = []
        for doc in self._docs:
            if products is not None and "*" not in products and doc.product not in products:
                continue
            score = len(wanted & _tokens(doc.title + " " + doc.excerpt))
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda pair: (-pair[0], pair[1].source_id))
        return [doc for _, doc in scored[:limit]]
