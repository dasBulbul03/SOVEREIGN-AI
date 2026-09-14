• Start with one thin vertical slice:

  > Browser → FastAPI → Ollama local model → response displayed in UI.

  Do not begin with RAG, agents, OCR, or sandboxing simultaneously. First establish a clean foundation that every later
  feature can reuse.

  - OCR
    - AI-powered OCR (Optical Character Recognition) transforms static images and scanned documents into structured, machine-readable data by combining traditional text recognition with artificial intelligence and machine learning
    

  ## Phase 1: Day 1 foundation

  ### 1. Confirm prerequisites
  - The development machine needs:

  - Docker with Compose
  - Node.js and npm
  - Python 3.12+
  - Ollama
  - Sufficient disk space for local models
  - Ideally 16 GB+ RAM; GPU is helpful but not mandatory for initial development

  Before selecting models, record the machine’s RAM, GPU, VRAM, OS, and available disk space. Model selection depends
  heavily on this.

  ### 2. Create the repository structure
  ai-agentic-flow/
  ├── frontend/
  ├── backend/
  ├── sandbox/
  ├── docker/
  ├── demo-data/
  ├── scripts/
  ├── docs/
  ├── docker-compose.yml
  ├── .env.example
  ├── .gitignore
  ├── Makefile
  └── README.md

  Backend:

  backend/app/
  ├── api/
  ├── core/
  ├── db/
  ├── tasks/
  ├── agents/
  ├── routing/
  ├── model_providers/
  ├── tools/
  ├── documents/
  ├── rag/
  ├── sandbox/
  ├── artifacts/
  ├── audit/
  └── security/

  ### 3. Scaffold the frontend

  Use:

  - Next.js
  - TypeScript strict mode
  - Tailwind CSS
  - shadcn/ui
  - TanStack Query

  Initially create only:

  - Application shell and navigation
  - Dashboard placeholder
  - Workbench page
  - Models page
  - API health indicator

  Avoid building detailed screens until backend contracts exist.

  ### 4. Scaffold the backend
  Use:
  - FastAPI
  - Pydantic
  - SQLAlchemy
  - Alembic
  - PostgreSQL driver
  - pytest
  - Ruff
  - mypy or pyright

  The first API endpoints should be:

  GET  /api/v1/health
  GET  /api/v1/readiness
  GET  /api/v1/models
  POST /api/v1/models/{id}/health-check
  POST /api/v1/inference/chat

  The temporary /inference/chat endpoint proves connectivity. Later, normal users should submit tasks instead of
  selecting models directly.

  ### 5. Establish local infrastructure

  The first docker-compose.yml should contain:

  frontend
  api-worker
  postgres
  qdrant
  ollama

  Configure:

  - PostgreSQL and Qdrant on private networks
  - Ollama accessible only to the backend
  - Persistent local volumes
  - Health checks
  - No cloud AI SDKs
  - No runtime model downloads during the final demo

  The sandbox runner can be added on Day 4.

  ### 6. Implement the model-provider abstraction

  Do not call Ollama directly throughout the application.

  class ModelProvider(Protocol):
      async def chat(self, request: ChatRequest) -> ChatResult:
          ...

      async def embed(
          self,
          texts: list[str],
          model_key: str,
      ) -> list[list[float]]:
          ...

      async def health(self, model_key: str) -> ModelHealth:
          ...

  Then implement:

  OllamaModelProvider

  This prevents Ollama-specific behavior from leaking into routing, agents, and workflows.

  ### 7. Create the first database migration

  Start with only:

  models
  model_health
  workspaces

  Seed:

  - One general/vision-capable model
  - One coding-capable model
  - One embedding model

  Store capabilities explicitly:

  [
    "text",
    "reasoning",
    "vision",
    "document_analysis"
  ]

  ### 8. Deliver the first vertical slice

  The Workbench should send a simple prompt to FastAPI. FastAPI selects a configured local model, calls Ollama, and
  returns:

  {
    "model_id": "...",
    "model_name": "...",
    "provider": "ollama",
    "content": "...",
    "duration_ms": 1234,
    "local": true
  }

  The UI displays the response, selected model, duration, and health status.

  ## Day 1 acceptance criteria

  Do not proceed to document ingestion until all these pass:

  - [ ] Repository starts with one documented command
  - [ ] Frontend can reach FastAPI
  - [ ] PostgreSQL migration succeeds from an empty database
  - [ ] Qdrant health check succeeds
  - [ ] Ollama health check succeeds
  - [ ] A local model returns a response
  - [ ] Model metadata is loaded from PostgreSQL
  - [ ] No OpenAI, Gemini, Anthropic, or other cloud AI dependency exists
  - [ ] Errors are structured and visible in the UI
  - [ ] Basic backend tests and frontend checks pass

  ## What comes immediately afterward

  Once the first slice is reliable:

  1. Day 2: secure uploads, PDF extraction, OCR, chunking, embeddings, and Qdrant retrieval.
  2. Day 3: task state machine, model router, agent loop, tool permissions, execution trace, and DOCX generation.
  3. Day 4: coding model, patch workflow, isolated Docker sandbox, and tests.
  4. Day 5: image analysis, procurement extraction, XLSX generation, and all three workflows.
  5. Day 6–7: security proof, evaluation, UX polish, offline installation, and rehearsals.



# Day 1 is complete, including Turborepo integration and a working local inference path.

  What is running:

  - UI: http://localhost:3000
  - API documentation: http://localhost:8000/docs
  - PostgreSQL and Qdrant are healthy
  - Native Ollama is using Apple Metal with cloud features disabled
  - All three local models report ready

  Installed models:

  - qwen3:1.7b for general reasoning
  - qwen2.5-coder:1.5b for coding
  - nomic-embed-text for embeddings

  These model identifiers and sizes were verified against the official Ollama library: Qwen3 1.7B
  (https://ollama.com/library/qwen3%3A1.7b), Qwen2.5 Coder (https://ollama.com/library/qwen2.5-coder), and Nomic Embed
  Text (https://ollama.com/library/nomic-embed-text).

  Implemented:

  - Turborepo with npm workspaces
  - Next.js Dashboard, Models, and Workbench
  - FastAPI typed API and structured errors
  - Ollama provider abstraction
  - PostgreSQL model registry
  - Alembic migration and seeded models
  - Persistent model health records
  - Qdrant readiness integration
  - Docker Compose ARM64 stack
  - Locked npm and Python dependencies
  - M1 8 GB resource settings
  - Local-only inference smoke endpoint

  Verification passed:

  - Six Turbo checks succeeded
  - Backend: Ruff, strict mypy, and 3 tests
  - Frontend: ESLint, TypeScript, and 1 test
  - Production builds succeeded
  - Browser-to-Ollama inference returned the exact expected response
  - Playwright found zero browser console errors or warnings
  - Actual local inference completed in approximately 6.7 seconds

  Useful commands:

  make ollama-serve
  make up
  npm run check
  npm run build
  make logs
  make down

  The implementation guide is in README.md, and the complete build evidence is recorded in docs/16-day-1-build-
  record.md.

  The stack is ready for Day 2: secure file storage, PDF extraction, local embeddings, Qdrant ingestion, and cited
  knowledge search.


# day 2

Day 2 is complete and running at http://localhost:3000/knowledge (http://localhost:3000/knowledge).

  Implemented:

  - Secure streamed document uploads with validation and 20 MB limit
  - PDF extraction with page-level Tesseract OCR fallback
  - Markdown, text, CSV, PNG, and JPEG support
  - Deterministic page-aware chunking
  - Local embeddings through nomic-embed-text
  - Versioned Qdrant indexes with safe activation
  - Asynchronous ingestion jobs with progress and errors
  - Semantic search with filename, page, and relevance citations
  - Responsive Knowledge Library UI
  - PostgreSQL Day 2 migration and persistent document storage

  Verification passed:

  - All six Turborepo checks
  - 6 backend tests
  - Ruff, strict mypy, ESLint, TypeScript, and Vitest
  - Production frontend and backend builds
  - PostgreSQL, Qdrant, and Ollama readiness
  - Real SOP ingestion completed in approximately 1.7 seconds
  - Semantic retrieval returned the correct pump isolation procedure with citation
  - Playwright UI workflow passed with zero console errors

  Key references:

  - Day 2 build record (docs/17-day-2-build-record.md)
  - Knowledge UI (frontend/app/knowledge/page.tsx)
  - Knowledge API (backend/app/api/routes/knowledge.py)
  - Ingestion pipeline (backend/app/services/knowledge_ingestion.py)
  - Demo SOP (demo-data/pump-maintenance-sop.md)
  - UI screenshot (day2-knowledge.png)

  The complete stack is left running. Day 3 is ready to begin with durable task execution, capability routing, trace
  events, and the first governed agent loop using search_knowledge.

─ Worked for 19m 16s ───────────────────────────────────────────────────────────────────────────────────────────────────

─ Conversation recap ───────────────────────────────────────────────────────────────────────────────────────────────────

  Day 2 is complete and running at http://localhost:3000/knowledge, with secure streamed uploads, validation, PDF OCR
  fallback, multiple file formats, and deterministic page-aware chunking. No next step or blocker was recorded.