# Outlook Engineering AI Assistant

An AI assistant embedded in Microsoft Outlook (task pane) that helps engineers triage bug emails.
It detects bug IDs in the open email, queries a bug-tracker API and a documentation search API,
and returns a source-grounded answer. A preliminary answer appears fast; verified evidence updates it live.

> **Status:** Stage 3 of 10 (FastAPI backend with mock responses). See [Roadmap](#roadmap).
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
### Backend (Stage 3)
Python 3.11+ required.
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env                  # macOS/Linux: cp .env.example .env
# put a random 32+ character value in DEV_JWT_SECRET inside .env:
python -c "import secrets; print(secrets.token_urlsafe(48))"
pytest                                  # 188 tests
ruff check . ; mypy app                 # lint + strict types
uvicorn app.main:get_app --factory --reload --no-access-log
```
- Interactive docs (local only): http://127.0.0.1:8000/docs. Click **Authorize** and paste a dev token.
- Make a dev token: `python ..\scripts\make_dev_token.py --user alice --products payments web-portal`
- With the server running, in a second terminal: `python ..\scripts\smoke_test.py` (real HTTP, 11 checks).
- Everything uses **mock integrations and synthetic data** until `USE_MOCK_INTEGRATIONS=false` (see [docs/integrations.md](docs/integrations.md)).

### Frontend (Stage 2)
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev        # http://localhost:3000 (HTTPS if dev certs are installed)
npm test           # unit + component tests
npm run typecheck && npm run lint && npm run build
```
In a normal browser the app uses **synthetic sample emails** and a **mock assistant**, so you can try the full
UI (preliminary answer, progress, sources, errors, Stop/Retry) with no backend. To use it inside Outlook, see
[docs/outlook-addin.md](docs/outlook-addin.md). 

## Roadmap
- [x] Stage 1 — Repository and setup
- [x] Stage 2 — Outlook frontend (mock email data)
- [x] Stage 3 — FastAPI backend (typed endpoints, health, mocks)
- [ ] Stage 4 — Frontend/backend integration
- [ ] Stage 5 — LLM integration
- [ ] Stage 6 — Tool orchestration (bug ID extraction, bug + docs tools)
- [ ] Stage 7 — RAG and citation validation
- [ ] Stage 8 — SSE and async progressive updates
- [ ] Stage 9 — Security and testing
- [ ] Stage 10 — Docker, CI/CD, release

## Known limitations
- MVP is read-only (no sending email or modifying bugs). Real internal APIs are replaced by mocks.
- The "assistant" is a mock until Stages 5-6 (no LLM yet).
- Rate limits, request status and feedback live in process memory (single process only, see ADR 0003).
- Entra ID validation is unit-tested with local keys, not against a real tenant (see ADR 0002).

## License
MIT
