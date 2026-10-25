# Threat model (initial)

| Risk | Control |
|---|---|
| Leaked secrets | `.env.example` only; secret scanning; rotate on exposure |
| Unauthorized internal data | Backend authN/authZ on every tool call; permission-filtered retrieval |
| Excess Outlook access | Minimum manifest permissions, documented |
| Email privacy | Send minimal excerpt; no raw email in logs/DB by default |
| Prompt injection | Untrusted-data boundaries, tool allowlist, argument validation, read-only MVP |
| SSRF | Server-side fixed API base URLs; no model/user-chosen URLs |
| Data exfiltration | Limited context, field allowlists, size caps |
| Cross-origin abuse | Restricted CORS, HTTPS |
| Cost/abuse | Rate limits, input/output caps, timeouts |
| Unsafe logs | Request IDs + redacted metadata only |

## Controls implemented in Stage 3 (and the tests that prove them)
| Risk | Control in code | Test |
|---|---|---|
| Forged identity | Identity only from a validated token; unknown body fields rejected | test_security, "user_id" 422 case |
| Weak token validation | Signature, issuer, audience, expiry required; fixed algorithm lists (no `none`/HS256 on Entra) | test_security |
| Cross-product data access | Product check in code on every bug; docs filtered before and after the upstream call | test_chat (authorization), test_http_adapters |
| Existence leaks | Other users' requests and inaccessible bugs look like "not found" | test_requests_and_feedback, test_chat |
| SSRF / credential theft | Fixed https base URL, validated path segments, no redirects | test_http_adapters, test_http_client |
| Oversized input | Field limits, body limit incl. chunked uploads | test_validation_and_limits |
| Abuse / cost | Rate limit, per-user and global concurrency, request deadline, retry caps | test_admission, test_chat, test_coordinator |
| Info leakage in errors | One error shape; no tracebacks, values or secrets; 500s carry only the request ID | test_health_and_errors |
| Secrets in logs | Redaction filter; bodies and tokens never logged | test_logging |
| Config mistakes | Fail fast; error text names settings, never values | test_config |
| Hanging work | Cancel on client disconnect, slot always released | test_sse, test_coordinator |
Not yet covered: LLM prompt injection (no LLM yet, Stage 5/6/9), live Entra validation, multi-process limits.
