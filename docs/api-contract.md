# API contract (draft, finalized in Stage 3)

| Endpoint | Purpose |
|---|---|
| GET /health/live | Process is up |
| GET /health/ready | Ready to serve |
| POST /api/v1/chat/stream | Start request, stream SSE events |
| POST /api/v1/feedback | Optional feedback (minimal metadata) |
| GET /api/v1/requests/{request_id} | Optional status/recovery |

## Request
```json
{
  "message": "What is the likely cause and fix?",
  "email_context": { "subject": "Payment service error BUG-4821", "body_text": "minimum required excerpt" },
  "conversation_id": null
}
```
Limits (set in code): message length, email-context length, per-user rate limit, tool allowlist.
Request IDs are generated server-side. User identity comes from validated tokens, never the request body.

## SSE events
| Event | Payload | UI behavior |
|---|---|---|
| request.started | request_id, status | Create response card |
| assistant.delta | request_id, text | Append partial (preliminary) text |
| tool.status | request_id, tool, status (running/done/failed), summary | Show progress |
| evidence.ready | source ids/titles, safe metadata | Show evidence chips |
| assistant.final | request_id, answer, sources, limitations? | Replace preliminary answer; show limitations |
| request.error | request_id, error_code, message (safe, user-facing), retryable | Show error; offer retry only if retryable |
| request.done | request_id | Stop indicators |

Never include stack traces, credentials, raw internal responses or unredacted email in events.

## Evidence model
`source_id, source_type ("bug"|"documentation"), title, uri?, excerpt, metadata{product, version, status, updated_at}`

## Frontend handling rules (implemented in Stage 2)
- Events for a different `request_id` are ignored; events before `request.started` are ignored.
- `assistant.final` ends the request. A later `request.done` is a no-op.
- `request.done` with no `assistant.final`, or the stream closing early, is a retryable failure.
- Error codes: RATE_LIMITED, UPSTREAM_TIMEOUT, LLM_UNAVAILABLE, UNAUTHORIZED, INVALID_REQUEST, INTERNAL_ERROR
  (server) and STREAM_DISCONNECTED, STREAM_ENDED_EARLY (client-detected).
- Source links render only for http(s) URLs; answers render as plain text, never HTML.
