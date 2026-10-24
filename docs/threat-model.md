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
