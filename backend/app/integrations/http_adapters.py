"""Adapters from internal REST APIs to our approved models.

ASSUMED upstream contracts (confirm against the real APIs; see docs/integrations.md):
  GET {BUG_API}/bugs/{id}        -> JSON object with the BugRecord fields (extra fields ignored)
  GET {DOCS_API}/search?q=&limit=&product=  -> {"results": [ ...DocPassage fields... ]}
"""

import logging
import re
from urllib.parse import quote

from pydantic import ValidationError

from app.integrations.base import UpstreamBadResponse
from app.integrations.http_client import ResilientHttpClient
from app.integrations.models import BUG_ID_RE, BugRecord, DocPassage

log = logging.getLogger(__name__)
_BUG_ID = re.compile(BUG_ID_RE)


class HttpBugTrackerClient:
    def __init__(self, http: ResilientHttpClient) -> None:
        self._http = http

    async def get_bug(self, bug_id: str) -> BugRecord | None:
        if not _BUG_ID.fullmatch(bug_id):  # never build a URL from unvalidated input
            return None
        data = await self._http.get_json(f"/bugs/{quote(bug_id, safe='')}")
        if data is None:
            return None
        try:
            record = BugRecord.model_validate(data)
        except ValidationError:
            raise UpstreamBadResponse("bug tracker returned an unexpected shape") from None
        if record.id != bug_id:
            raise UpstreamBadResponse("bug tracker returned a different record")
        return record


class HttpDocumentationSearchClient:
    def __init__(self, http: ResilientHttpClient) -> None:
        self._http = http

    async def search(self, query: str, *, products: frozenset[str] | None, limit: int = 3) -> list[DocPassage]:
        if products is not None and not products:
            return []
        params: dict[str, str | int] = {"q": query[:300], "limit": limit}
        data = await self._http.get_json("/search", params)
        if data is None:
            return []
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise UpstreamBadResponse("documentation search returned an unexpected shape")
        passages: list[DocPassage] = []
        for item in data["results"][: limit * 3]:
            try:
                passage = DocPassage.model_validate(item)
            except ValidationError:
                log.warning("dropped a malformed documentation result")
                continue
            # Enforce access here as well; never trust the upstream to have filtered.
            if products is None or "*" in products or passage.product in products:
                passages.append(passage)
        return passages[:limit]
