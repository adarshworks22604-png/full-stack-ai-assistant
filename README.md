# Outlook Engineering AI Assistant

An AI assistant embedded in Microsoft Outlook (task pane) that helps engineers triage bug emails.
It detects bug IDs in the open email, queries a bug-tracker API and a documentation search API,
and returns a source-grounded answer. A preliminary answer appears fast; verified evidence updates it live.

> **Status:** Stage 1 of 10 (repository and setup). See [Roadmap](#roadmap).
> All data in this repo is synthetic. Do not paste production secrets or real email into it.

## Architecture
Outlook + React/TypeScript (Office.js) → FastAPI → AI agent → tools / RAG → response (SSE).
Details: [docs/architecture.md](docs/architecture.md). API: [docs/api-contract.md](docs/api-contract.md). Threats: [docs/threat-model.md](docs/threat-model.md).

## Stack
React + TypeScript + Vite + Fluent UI + Office.js · Python + FastAPI + Pydantic + HTTPX · one LLM provider adapter · SSE · Docker · GitHub Actions.

## Repository layout
```
frontend/   Outlook task pane (manifest, components, Office.js adapter)
backend/    FastAPI app (api, schemas, services, agent, integrations, rag, core)
docs/       architecture, API contract, threat model, ADRs
scripts/    helper scripts
```

## Environment variables
Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env.local`.
`VITE_*` values are public; secrets live only in the backend.

## Running locally
Filled in as stages complete (frontend in Stage 2, backend in Stage 3, Docker in Stage 10).

## Roadmap
- [x] Stage 1 — Repository and setup
- [ ] Stage 2 — Outlook frontend (mock email data)
- [ ] Stage 3 — FastAPI backend (typed endpoints, health, mocks)
- [ ] Stage 4 — Frontend/backend integration
- [ ] Stage 5 — LLM integration
- [ ] Stage 6 — Tool orchestration (bug ID extraction, bug + docs tools)
- [ ] Stage 7 — RAG and citation validation
- [ ] Stage 8 — SSE and async progressive updates
- [ ] Stage 9 — Security and testing
- [ ] Stage 10 — Docker, CI/CD, release

## Known limitations
MVP is read-only (no sending email or modifying bugs). Real internal APIs are replaced by mocks.

## License
MIT
