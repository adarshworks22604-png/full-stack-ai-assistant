# Integrations (bug tracker + documentation search)

Both are accessed only through typed interfaces in `backend/app/integrations/base.py`:
`BugTrackerClient.get_bug(id)` and `DocumentationSearchClient.search(query, products, limit)`.

| Mode | Setting | Implementation |
|---|---|---|
| Mock (default) | `USE_MOCK_INTEGRATIONS=true` | Synthetic JSON in `app/integrations/mock_data/` |
| Real | `USE_MOCK_INTEGRATIONS=false` + URLs/tokens | `HttpBugTrackerClient`, `HttpDocumentationSearchClient` |

Mock fault injection (for testing failure paths): `BUG-5000` times out, `BUG-5001` is rate limited, `BUG-5002` returns
malformed data. `BUG-7000` belongs to product `billing` (use it to test authorization).

## HTTP client guarantees (`ResilientHttpClient`)
- Base URL comes from server config only. Paths are built from IDs that passed a strict pattern, and are URL-quoted.
- Redirects are **not** followed (a redirect could carry the credential to another host). Config requires `https://`.
- Timeouts: connect 3 s, read 8 s, write 5 s, pool 3 s (configurable).
- Retries: at most 2 (configurable), only for timeouts, connection errors, 429, 502, 503, 504. Exponential backoff with
  full jitter, capped at 2 s; `Retry-After` is honoured but capped at 5 s. 401/403/404/other statuses are never retried.
- Concurrency: one semaphore (default 10) shared by both APIs.
- Response size capped at 1 MB. Unapproved fields in upstream data are dropped by the pydantic models.
- Our service credential being rejected (401/403) is logged as a server problem and shown to users as "unavailable".

## ASSUMED upstream contracts (confirm against the real APIs before using real mode)
```
GET {BUG_API_BASE_URL}/bugs/{id}
  200 -> {"id","title","status","affected_version?","resolution?","product", ...ignored extras}
  404 -> bug does not exist
GET {DOCS_API_BASE_URL}/search?q=<text>&limit=<n>
  200 -> {"results":[{"source_id","title","uri?","product","version?","updated_at?","excerpt"}]}
```
Both use `Authorization: Bearer <service token>`. If the real APIs differ, only `http_adapters.py` changes.
Open questions: how bug/doc visibility maps to our `product` model; whether the docs API can filter by product server
side (we filter again regardless); the real bug ID format (`BUG_ID_PATTERN`).
