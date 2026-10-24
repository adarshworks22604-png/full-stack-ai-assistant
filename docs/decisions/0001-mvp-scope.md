# ADR 0001: MVP scope
**Context:** Many tempting technologies (agent swarms, multiple vector DBs, Redis).
**Options:** Build broad vs. build a narrow end-to-end flow.
**Decision:** One LLM provider, two tools (bugs, docs), SSE, mocks first, read-only. LangGraph/Redis/own vector index only if justified.
**Consequences:** Faster to a demonstrable, secure workflow; extra infra deferred.
