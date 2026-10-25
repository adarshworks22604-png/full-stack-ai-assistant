# API contract (v1, implemented in Stage 3)

Interactive docs exist **locally only**: `http://127.0.0.1:8000/docs` (disabled outside `APP_ENV=local`).

## Endpoints
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | /health/live | none | Process is running. Body: `{"status":"ok"}` |
| GET | /health/ready | none | Ready to serve. `{"status":"ready"}` or 503 `{"status":"not_ready"}` |
| POST | /api/v1/chat/stream | Bearer | Start a request, stream progress as SSE |
| POST | /api/v1/chat | Bearer | Same work, returns only the final answer as JSON |
| GET | /api/v1/requests/{request_id} | Bearer | Status of **your own** request |
| POST | /api/v1/feedback | Bearer | Rating for **your own** request |

Health responses contain no dependency details.

## Authentication
`Authorization: Bearer <token>`. Identity comes only from the validated token, never from the body
(unknown body fields are rejected, so a client cannot even send a `user_id`).
- Local: HS256 dev token (`scripts/make_dev_token.py`). Refused by config unless `APP_ENV=local`.
- Production: Microsoft Entra ID access token (RS256, signature + issuer + audience + expiry + tenant checked).
- Every failure returns the same generic 401, with `WWW-Authenticate: Bearer`.

Authorization is by **product**. A token carries the products a user may see (`products` claim locally, mapped from
Entra groups in production; `"*"` means all). A bug or document in another product behaves exactly like one that
does not exist.

## Request (chat)
```json
{
  "message": "What is the likely cause and fix?",
  "email_context": { "subject": "Payment service error BUG-4821", "body_text": "minimum required excerpt" },
  "conversation_id": null
}
```
| Field | Rule |
|---|---|
| message | required, 1–8000 chars after trimming |
| email_context | optional; `subject` ≤ 500, `body_text` ≤ 8000 |
| conversation_id | optional; `[A-Za-z0-9_-]{1,64}` (reserved, unused until later stages) |
| anything else | rejected (422) |
Control characters are stripped. Request bodies over 64 KB (configurable) get 413, including chunked uploads.

## Request IDs
The server generates `req_<32 hex>` for every request. It is returned in the `X-Request-ID` header, in every error
body, and as `request_id` in every SSE event and `/chat` response. A client-sent `X-Request-ID` is ignored.

## Errors (every non-2xx response)
```json
{ "error": { "code": "RATE_LIMITED", "message": "Too many requests...", "retryable": true,
             "request_id": "req_...", "details": [{"field": "message", "message": "..."}] } }
```
`details` appears only for 422. Submitted values are never echoed. No stack traces, hostnames or credentials, ever.

| HTTP | code | When |
|---|---|---|
| 401 | UNAUTHORIZED | Missing/invalid/expired token |
| 404 | NOT_FOUND | Unknown route, or a request that is not yours |
| 405 | METHOD_NOT_ALLOWED | Wrong method |
| 413 | PAYLOAD_TOO_LARGE | Body over the limit |
| 422 | INVALID_REQUEST | Validation failed |
| 429 | RATE_LIMITED | Per-user rate or concurrency limit; `Retry-After` header |
| 500 | INTERNAL_ERROR | Unexpected failure |
| 503 | SERVER_BUSY / LLM_UNAVAILABLE | Global concurrency limit; `Retry-After` header |
| 504 | UPSTREAM_TIMEOUT | `/chat` only: a data source or the deadline timed out |

## SSE stream (`POST /api/v1/chat/stream`)
Admission errors (401, 413, 422, 429, 503) are normal JSON responses **before** streaming starts. After that, the
response is `200 text/event-stream` and failures arrive as `request.error` events. Frame format:
```
id: 3
event: tool.status
data: {"type":"tool.status","request_id":"req_...","tool":"get_bug_details","status":"running","summary":"Checking BUG-4821"}

```
Comment lines (`: keep-alive`) are sent every 15 s of silence. Headers: `Cache-Control: no-cache, no-transform`,
`X-Accel-Buffering: no`.

| Event | Fields | Frontend behaviour |
|---|---|---|
| request.started | request_id, status | Create the response card |
| assistant.delta | request_id, text | Append to the **preliminary** answer |
| tool.status | request_id, tool, status (running/done/failed), summary | Show progress |
| evidence.ready | request_id, sources[] | Show "found so far" |
| assistant.final | request_id, answer, sources[], limitations[] | Replace the preliminary answer |
| request.error | request_id, error_code, message, retryable | Show error; retry only if retryable |
| request.done | request_id | Always last |

Guarantees: `request.started` is first; `request.done` is always last, after `assistant.final` **or**
`request.error`; `id` increases by 1 per event; one terminal event per request.
`error_code` values in events: RATE_LIMITED, UPSTREAM_TIMEOUT, LLM_UNAVAILABLE, UNAUTHORIZED, INVALID_REQUEST, INTERNAL_ERROR.

Source: `{ "source_id", "source_type": "bug"|"documentation", "title", "uri"? }`.

## Status and feedback
- `GET /api/v1/requests/{id}` → `{request_id, status: running|complete|failed|cancelled, created_at}`.
  Other users' IDs and unknown IDs both return 404 (no existence leak). Records are kept in memory for 1 hour.
- `POST /api/v1/feedback` → `{request_id, rating: "up"|"down", reason?: incorrect|not_helpful|missing_sources|other}`.
  Fixed values only, so feedback cannot carry email text.

## Frontend handling rules (implemented in Stage 2)
- Events for a different `request_id`, or before `request.started`, are ignored.
- `assistant.final` ends the request; a later `request.done` is a no-op.
- `request.done` with no final answer, or the stream closing early, is a retryable failure.
- Source links render only for http(s) URLs; answers render as plain text, never HTML.

## Known gaps to close in Stage 4
- The frontend `ErrorCode` type lacks the HTTP-level codes (FORBIDDEN, PAYLOAD_TOO_LARGE, SERVER_BUSY, ...); Stage 4 adds them.
- The browser sends the token with `fetch` (EventSource cannot send headers), so the SSE client is a `fetch` stream reader.
