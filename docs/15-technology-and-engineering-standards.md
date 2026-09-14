# Technology and Engineering Standards

## Selected stack

Versions must be pinned during Day 1 after compatibility checks; this plan avoids inventing version numbers before the repository exists.

| Area | Choice | Reason | Boundary/alternative |
|---|---|---|---|
| Web UI | Next.js, React, TypeScript | fast typed product UI and routing | keep business logic server-side |
| Styling/components | Tailwind CSS, shadcn/ui | coherent accessible shell quickly | reuse primitives; avoid one-off styles |
| Server state | TanStack Query | caching, polling and mutation lifecycle | SSE reconciles with queries |
| Local UI state | Zustand only where needed | small workbench interaction state | do not duplicate server state |
| Flow visualization | React Flow, should-priority | understandable run visualization | trace list remains primary |
| Charts | Recharts, should-priority | dashboard metrics | only for real measurements |
| API | Python 3.12, FastAPI, Pydantic | async typed contracts and AI ecosystem | OpenAPI generated from contracts |
| Persistence | SQLAlchemy, Alembic, PostgreSQL | durable workflow/audit state and migrations | repositories hide ORM from services |
| Vector search | Qdrant | local metadata-filtered vector retrieval | accessed through vector index protocol |
| Model serving | Ollama | fastest local prototype path | provider protocol supports later vLLM/TGI/llama.cpp |
| PDF/images | PyMuPDF, Pillow | local extraction/rendering | enforce parser/resource limits |
| OCR | Tesseract or PaddleOCR after benchmark | offline OCR | decide against actual demo scans |
| Office artifacts | python-docx, openpyxl | controlled valid DOCX/XLSX generation | template-driven structured specs |
| Sandbox | Docker/OCI runner | strong practical prototype isolation | production should isolate runner host/runtime |
| Orchestration | Docker Compose | reproducible single-host deployment | Kubernetes explicitly deferred |
| Testing | pytest, HTTP integration tooling, Playwright for E2E | layered automation | select JS unit runner with scaffold |
| Quality | Ruff, mypy/pyright; ESLint, Prettier, TypeScript strict | consistent automated feedback | exact config committed once scaffolded |

## Dependency policy

- Prefer mature libraries with compatible licenses and active maintenance.
- Lock direct/transitive dependencies and pin container image digests for the demo release.
- Remove unused cloud AI SDKs and telemetry that could make outbound requests.
- Test license terms for every chosen open-weight model and dataset.
- Generate an SBOM if time permits; production requires one.
- No runtime package/model download. Installation/preload is a separate controlled operation.

## Target repository structure

```text
frontend/
├── app/                    routes and layouts
├── components/             shared presentation primitives
├── features/               workspace, tasks, models, knowledge, sovereignty
├── lib/                    API client, contracts, formatting
└── tests/
backend/
├── app/                    modules defined in 06-low-level-design.md
├── alembic/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   └── evaluation/
└── pyproject.toml
sandbox/
├── Dockerfile
├── runner/
└── tests/
docker/
demo-data/
scripts/
docs/
docker-compose.yml
.env.example
README.md
```

## Backend standards

- Type every public function and boundary model; use strict Pydantic request/action schemas.
- Keep routes thin: authorize/map, call a service, map result.
- Encapsulate transactions in application services; do not commit from repositories unpredictably.
- Use UTC-aware times and injected clock/ID providers in logic requiring deterministic tests.
- Raise domain error codes and translate once at the API/worker boundary.
- Never use `shell=True`, interpolate model output into a command, or accept a raw filesystem path from a model/client.
- Bound all model/tool/file output before persistence or prompt reuse.
- Write migrations forward; do not edit a migration already used by another environment.

## Frontend standards

- Generate or share types from the OpenAPI contract; avoid hand-maintained duplicate shapes.
- Treat task/run state from the backend as authoritative.
- Use semantic HTML, labels, keyboard navigation, visible focus and status text/icons.
- Build loading, empty, degraded, error and success states with every feature.
- Do not expose chain-of-thought; show action summaries, inputs/outputs allowed for the user, and evidence.
- Centralize dates, bytes, duration, status and error formatting.

## API and data standards

- Opaque UUIDs, explicit workspace scoping and uniform error envelopes.
- Idempotency on retried create/start operations.
- Pagination for lists and bounded payloads for trace/events.
- Schema migrations and API contract changes ship with corresponding tests/docs.
- Store prompt/template/model/config versions needed to reproduce an evaluation without logging confidential bodies.

## Git and review workflow

- Small vertical commits; no generated model weights, environments, secrets or runtime data in Git.
- Branch/PR titles reference epic/task and requirement IDs where applicable.
- Review focuses on correctness, boundary violations, failure behavior, traceability and test evidence.
- A security-sensitive change to tools, files, sandbox, networks or logging requires explicit boundary review.
- Never silently rewrite unrelated user work or destructive data/migrations.

## Continuous checks

Expected local/CI sequence once scaffolded:

1. Formatting/lint and TypeScript/Python type checks.
2. Backend/frontend unit tests.
3. Database migration-from-empty check.
4. Integration tests with local service containers.
5. Security negative suite for affected boundaries.
6. Deterministic E2E/evaluation jobs on the demo host before release.

## Documentation standards

Architecture/code decisions use ADR entries. Requirements keep stable IDs. API behavior comes from code-generated OpenAPI plus this semantic plan. Runbooks contain verified commands only after implementation; placeholders must never be presented as tested operations.
