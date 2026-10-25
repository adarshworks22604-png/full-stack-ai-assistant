# ADR 0003: In-memory limits, registry and feedback
**Context:** We need rate limits, concurrency limits, request status and feedback, but guide rule: no Redis/DB until needed.
**Decision:** Per-user sliding-window rate limit, per-user and global concurrency caps, a bounded 1-hour request registry,
and a bounded feedback list, all in process memory.
**Consequences:** Correct for one process. With several workers/instances, limits are per-process and records are lost on
restart. Move to Redis/PostgreSQL when we scale out or need durable feedback (revisit in Stage 10).
