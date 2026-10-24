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
| tool.status | tool, status, safe summary | Show progress |
| evidence.ready | source ids/titles, safe metadata | Show evidence chips |
| assistant.final | answer, sources, request_id | Replace preliminary answer |
| request.error | error_code, retryable | Show error + retry |
| request.done | request_id | Stop indicators |

Never include stack traces, credentials, raw internal responses or unredacted email in events.

## Evidence model
`source_id, source_type ("bug"|"documentation"), title, uri?, excerpt, metadata{product, version, status, updated_at}`
