# Day 2 Build Record

Date: 2026-09-07  
Hardware: MacBook Air, Apple M1, 8 GB unified memory  
Status: completed and locally verified

## Outcome

Day 2 delivers the first grounded-knowledge vertical slice: an operator can upload a local document, extract and normalize its content, create a versioned vector index, and retrieve evidence with a filename and page citation. No document content or embedding request leaves the machine.

## Implemented

- Additive Alembic migration for stored files, normalized documents, knowledge bases, versioned membership, chunks, and ingestion jobs.
- Seeded `Demo Workspace` for the prototype UI without replacing existing workspace records.
- Streamed 20 MB uploads using UUID-based storage keys, path-containment checks, extension allowlisting, and PDF/image signature validation.
- PDF native-text extraction with page-level Tesseract OCR fallback; UTF-8 text, Markdown, CSV, PNG, and JPEG support.
- Persisted normalized pages with extraction method and warnings.
- Deterministic, page-aware overlapping chunks with hashes and stable persisted ordering.
- Batched local embeddings through Ollama `nomic-embed-text` and Qdrant cosine vectors.
- Staged index versions: a knowledge base activates a new version only after every requested document and vector succeeds. A previous active version remains searchable after failure.
- Workspace, file, knowledge-base, ingestion-status, and cited-search APIs.
- Responsive Knowledge screen covering upload, indexing progress, stored files, semantic query, relevance, and citation display.
- A deterministic pump-maintenance SOP under `demo-data/` for repeatable demos.

## API surface

| Method and path | Purpose |
|---|---|
| `GET/POST /api/v1/workspaces` | List or create workspaces |
| `GET/POST /api/v1/workspaces/{id}/files` | List or securely upload files |
| `GET/POST /api/v1/knowledge-bases` | List or create knowledge bases |
| `POST /api/v1/knowledge-bases/{id}/ingestions` | Start a versioned full-set ingestion |
| `GET /api/v1/ingestions/{id}` | Poll progress and failure details |
| `POST /api/v1/knowledge-bases/{id}/search` | Retrieve cited semantic matches |

## Verification evidence

- `npm run check`: all six Turborepo tasks succeeded.
- Backend: Ruff and strict mypy passed; 6 tests passed, including secure filenames, chunk bounds, and real PDF extraction.
- Frontend: ESLint, TypeScript, and Vitest passed.
- `npm run build`: backend compile and Next.js production build passed, including `/knowledge`.
- Migration `20260906_0002` applied successfully to PostgreSQL; all four Compose services ran and both data services were healthy.
- Real SOP ingestion completed 1/1 documents and activated index version 1 in approximately 1.7 seconds.
- Real Qdrant search returned the correct pump isolation evidence, `pump-maintenance-sop.md · p. 1`, with score `0.765` for the fixed validation query.
- Playwright loaded the screen, submitted a second search, rendered the cited result at a 69% match, and reported zero console errors or warnings.

## Resource decisions for M1 8 GB

- Ingestion remains one job per knowledge base, with embedding batches of eight chunks.
- Ollama keeps a single model loaded and uses a two-minute keep-alive.
- OCR renders one page at a time at 1.5× resolution rather than materializing an entire PDF.
- Vector upserts are capped at 64 points per request.
- PostgreSQL and Qdrant remain private Compose services; native Ollama retains Metal acceleration.

## Known limitations carried forward

- FastAPI background tasks provide prototype-grade execution; the durable Day 3 worker/state-machine will make jobs restart-safe.
- The Day 2 search endpoint retrieves evidence but does not generate a composed answer. The Day 3 agent invokes it as a governed tool.
- Sections are not yet detected independently; citations are page-accurate and section is nullable.
- Duplicate content is hashed but not deduplicated across uploads in this milestone.
- Deletion is intentionally absent until confirmation and retention behavior are implemented.

## Day 3 entry criteria

The retrieval tool boundary is now proven. Day 3 can add the task contract and state machine, durable worker execution, deterministic capability routing, trace events, and the first governed agent loop using `search_knowledge`.
