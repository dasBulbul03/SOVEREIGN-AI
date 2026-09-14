# Low-Level Design

## Proposed backend package layout

```text
backend/app/
├── api/routes/            workspaces, files, knowledge, tasks, models, security
├── core/                  config, errors, IDs, logging, clock
├── db/                    sessions, ORM models, repositories, migrations
├── tasks/                 service, worker, lifecycle, cancellation
├── agents/                runtime, state, planner, prompts, action schemas
├── routing/               classifier, capability map, scorer
├── model_providers/       protocol, ollama adapter, health
├── tools/                 protocol, registry, policy, implementations/
├── documents/             validator, parser, OCR, page model
├── rag/                   chunker, embedder, indexer, retriever, citations
├── sandbox/               client, request policy, result parser
├── artifacts/             specs, docx, xlsx, validators, publisher
├── audit/                 event types, writer, queries
└── security/              paths, redaction, sovereignty, limits
```

Dependencies point inward: routes call application services; services depend on protocols/repositories; adapters implement protocols. Tool implementations cannot bypass the policy gateway.

## Core contracts

```python
class ModelProvider(Protocol):
    async def chat(self, request: ChatRequest) -> ChatResult: ...
    async def embed(self, texts: list[str], model_key: str) -> list[list[float]]: ...
    async def health(self, model_key: str) -> ModelHealth: ...

class AgentTool(Protocol):
    name: str
    input_model: type[BaseModel]
    async def execute(self, ctx: ToolContext, args: BaseModel) -> ToolResult: ...

class ArtifactRenderer(Protocol):
    media_type: str
    async def render(self, spec: ArtifactSpec, destination: Path) -> RenderResult: ...
```

All boundary types are Pydantic models with forbidden unknown fields. `ToolResult` contains `status`, bounded `summary`, typed `data`, optional artifact IDs, duration and categorized error; it does not expose unrestricted exception strings.

## Agent state

```text
TaskState
  task_id, run_id, workspace_id
  goal, task_type, required_capabilities
  selected_model_id, routing_decision
  input_file_ids, knowledge_base_ids
  plan[], current_step, step_count, retry_count
  observations[], source_refs[], artifact_ids[]
  status, error_category
  started_at, deadline_at, completed_at, version
```

Persist the stable state after every step. Large observations are stored as referenced blobs; the state keeps bounded summaries. Use optimistic `version` checks to prevent two workers advancing one run.

## Runtime algorithm

```text
validate task and deadline
classify task; derive required capabilities
select model; persist routing decision
build initial plan
while not terminal:
  enforce cancellation, deadline, max steps and retry budget
  request one structured action from local model
  validate action schema
  if action is FINISH: validate claimed result and artifacts; complete
  authorize tool for agent profile
  execute with timeout and output bounds
  sanitize and persist observation + audit event
  update plan/state
on exception: map category, persist safe error, apply retry policy or fail
```

The runtime never treats a model's `success=true` as proof. Completion validators inspect artifacts, citations or test results depending on workflow.

## Task classification rules

- Source/test repository plus fix/debug/test intent -> `CODING`.
- Image or scanned-document analysis intent -> `VISION` or `DOCUMENT_ANALYSIS`.
- Policy/SOP knowledge lookup -> `RAG`.
- Comparison/table/workbook intent -> `SPREADSHEET` (usually plus `RAG`).
- Otherwise -> `GENERAL`.

Multi-label capabilities are allowed even though one primary task type is stored. Ambiguous high-risk input returns `needs_clarification`; demo prompts are fixed and should not trigger it.

## Tool profiles

| Tool | Document agent | Coding agent | Procurement agent |
|---|:---:|:---:|:---:|
| `read_file` | yes | yes | yes |
| `inspect_image` | yes | no | optional |
| `search_knowledge` | yes | no | yes |
| `create_docx` | yes | no | yes |
| `create_xlsx` | no | no | yes |
| `propose_patch` | no | yes | no |
| `run_python_tests` | no | yes | no |

No prototype profile receives general host shell or arbitrary network access.

## Filesystem design

```text
data/workspaces/{workspace_uuid}/
├── uploads/{file_uuid}/original
├── extracted/{document_uuid}/{version}/pages.jsonl
├── runs/{run_uuid}/inputs/        materialized sandbox inputs
├── runs/{run_uuid}/working/       non-published intermediate files
└── artifacts/{artifact_uuid}/{safe_filename}
```

Client input never supplies these paths. The server validates UUIDs, resolves the configured data root, rejects symlinks in writable task material, and checks canonical containment.

## Document model

`NormalizedPage` fields: document ID, page number, text, OCR text, image references, vision description, tables, extraction method, language, warnings and confidence. The chunker operates on a merged normalized view and never loses page provenance.

## Sandbox request

```json
{
  "run_id": "uuid",
  "input_file_ids": ["uuid"],
  "entrypoint": ["pytest", "-q"],
  "timeout_seconds": 60,
  "memory_mb": 512,
  "cpu_count": 1,
  "max_output_bytes": 200000
}
```

Entrypoints are selected from a server allowlist. Runner result includes exit/signal, stdout/stderr truncation flags, duration, limit reason and output checksums.

## Concurrency and idempotency

- Task creation accepts `Idempotency-Key`; same key and payload returns the existing task.
- Ingestion key is document checksum plus ingestion configuration version.
- Artifact publishing uses a database uniqueness constraint on `(run_id, logical_name, revision)`.
- One worker claims a run through an atomic status/version update.

## Error response

```json
{
  "error": {
    "code": "POLICY_PATH_OUTSIDE_WORKSPACE",
    "message": "The requested file is outside this workspace.",
    "correlation_id": "uuid",
    "retryable": false,
    "details": {}
  }
}
```

Stack traces, host paths, prompts, document text and secrets are not returned to clients or normal logs.
