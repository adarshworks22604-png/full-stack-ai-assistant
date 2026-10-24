# Architecture

```
Outlook task pane (React + TS + Office.js)
   └─ HTTPS POST /api/v1/chat/stream  (SSE response)
        └─ FastAPI: authN/authZ, validation, request ID
             ├─ Orchestrator (explicit tool loop, iteration + time limits)
             │    ├─ LLM provider adapter
             │    └─ Tool registry (allowlist)
             │         ├─ search_documentation → docs client
             │         └─ get_bug_details      → bug tracker client
             └─ RAG / evidence assembly → citation validation
```

## Request lifecycle
1. Task pane reads minimal email context via Office.js adapter.
2. Backend authenticates, validates, generates request ID, emits `request.started`.
3. Deterministic regex extracts candidate bug IDs.
4. Independent read-only lookups run concurrently; `tool.status` / `evidence.ready` events stream.
5. LLM synthesizes from evidence only; cited source IDs are verified against retrieved evidence.
6. `assistant.final` replaces the preliminary answer; `request.done` closes the stream.

## Principles
- Preliminary answers are labelled and never claim root cause before evidence confirms it.
- The LLM suggests tool calls; application code enforces authorization.
- Email, docs and bug text are untrusted data. MVP is read-only.
- Mocks and synthetic data until the core workflow works. No Redis/queue until needed.
