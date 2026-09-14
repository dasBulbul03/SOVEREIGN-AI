# Day 1 Build Record

Date: 2026-09-06  
Hardware: MacBook Air, Apple M1, 8 GB unified memory  
Status: completed and locally verified

## Implemented

- Turborepo with npm workspaces for frontend and Python backend orchestration.
- Next.js/TypeScript UI with Dashboard, Models, and Workbench screens.
- FastAPI/Pydantic API with structured errors and CORS limited to the local frontend.
- SQLAlchemy model registry and Alembic initial migration for workspaces, models, and model health.
- PostgreSQL and Qdrant private data network through Docker Compose.
- Provider-neutral model contract with an Ollama adapter.
- Local readiness, model listing, model health-check, and temporary inference endpoints.
- Native Ollama with Apple Metal, cloud features disabled, one parallel request, one loaded model, and two-minute keep-alive.
- Locked npm and uv dependency graphs, ARM64 container builds, tests, lint, type checks, and production build.

## Installed local models

| Model | Role | Observed registry health |
|---|---|---|
| `qwen3:1.7b` | general text/reasoning | ready |
| `qwen2.5-coder:1.5b` | coding | ready |
| `nomic-embed-text` | embeddings | ready |

## Verification evidence

- `npm run check`: six Turbo tasks succeeded.
- Backend: 3 tests passed; Ruff and strict mypy passed.
- Frontend: 1 test passed; ESLint and TypeScript passed.
- `npm run build`: backend compile and Next.js production build passed.
- Docker Compose: frontend/API running; PostgreSQL and Qdrant healthy.
- API readiness: PostgreSQL, Qdrant, and Ollama all reported ready.
- Alembic migration applied and three model records returned from PostgreSQL.
- Direct API inference returned the exact requested text from `qwen3:1.7b` in 6.7 seconds.
- Playwright rendered all three screens, observed three models, submitted a Workbench prompt, received the exact expected response, and reported zero console errors/warnings after the favicon fix.

## Machine-specific setup handled

- Colima uses the existing 2 CPU / 4 GiB profile.
- The removed Docker Desktop installation left a broken buildx link and root-owned historical state. Homebrew buildx was installed, the broken link was replaced with the valid plugin, and project commands use ignored `.docker-local` build state.
- Host Python is 3.14; `uv` installed and locked a project-local CPython 3.12.12 environment.

## Known limitations carried forward

- The temporary inference endpoint lets the caller choose a model for Day 1 diagnostics; later task APIs and routing will own selection.
- Full application-runtime egress blocking is not yet implemented. Current evidence is local-only configured providers plus Ollama cloud disabled; network isolation/probes remain Day 6 work.
- Node 22.12 successfully builds/tests the app, but a transitive lint package recommends Node 22.13 or later. Upgrade the host Node minor version when convenient.
- Workspaces exist only at schema level. File storage, knowledge ingestion, routing, tasks, agents, audit, artifacts, and sandboxing start in later milestones.

## Day 2 entry criteria

All Day 1 critical criteria are met. Day 2 can begin with opaque-ID file storage and validation, followed by normalized PDF extraction, local embeddings, versioned Qdrant ingestion, and cited search.
