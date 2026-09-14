# System Design

## End-to-end task sequence

```mermaid
sequenceDiagram
    actor User
    participant UI
    participant API
    participant Task as Task Service
    participant Router
    participant Agent
    participant Policy
    participant Tool
    participant Model as Local Model
    participant DB as PostgreSQL

    User->>UI: Submit task with file/KB IDs
    UI->>API: POST /tasks
    API->>Task: validate ownership and inputs
    Task->>DB: create task + queued run
    API-->>UI: 202 + task/run IDs
    Task->>Router: classify and route
    Router->>DB: persist route and reason
    Task->>Agent: start bounded execution
    loop max 12 steps
        Agent->>Model: plan/select action
        Model-->>Agent: schema-constrained action
        Agent->>Policy: authorize tool and arguments
        Policy-->>Agent: allow/deny
        Agent->>Tool: execute authorized action
        Tool-->>Agent: typed observation
        Agent->>DB: append step + audit event
        UI->>API: SSE/poll progress
        API-->>UI: durable events
    end
    Agent->>DB: validate and commit terminal status
```

## Knowledge ingestion

```mermaid
flowchart TD
    A[Upload] --> B{MIME/size/path valid?}
    B -- no --> X[Reject and audit]
    B -- yes --> C[Store with generated ID + checksum]
    C --> D{Digital text sufficient?}
    D -- yes --> E[PyMuPDF extraction]
    D -- no --> F[Render selected pages]
    F --> G[Local OCR]
    E --> H[Normalized page records]
    G --> H
    H --> I[Clean and section-aware chunk]
    I --> J[Local embeddings]
    J --> K[Write staging collection/points]
    K --> L{Counts and sample query valid?}
    L -- yes --> M[Activate index version]
    L -- no --> N[Mark failed; keep prior version]
```

Chunk defaults: 700 tokens, 100-token overlap, split on headings/paragraphs where possible. These are configuration defaults and must be evaluated on the demo corpus. Every chunk retains document ID, checksum, page range, section, extraction method and index version.

## Retrieval and grounded generation

1. Validate workspace and selected knowledge base.
2. Embed normalized query using the registered local embedding model.
3. Search top 12 vectors with workspace/KB/version filters.
4. Deduplicate near-identical chunks and optionally rerank locally.
5. Select up to 5 chunks within context budget.
6. Generate structured answer with citation IDs restricted to supplied chunks.
7. Reject unknown citation IDs; map valid IDs to page/section links.
8. If evidence score/coverage is insufficient, return `needs_review` or abstain.

## Routing design

Required capabilities are produced from task type and inputs. Candidate models are hard-filtered by enabled state, health freshness, capability coverage and input size. Remaining models score as:

```text
score = priority
      + 20 * exact_task_specialization
      + 10 * warm_or_loaded
      + 10 * context_fit_margin
      - estimated_resource_pressure
```

Tie-break order is stable: higher score, lower configured cost class, then lexical model ID. Persist required capabilities, candidates, exclusions, scores and selected model.

## Tool execution boundary

```mermaid
flowchart LR
    MO[Untrusted model action] --> SV[Schema validation]
    SV --> PA[Agent permission check]
    PA --> AR[Argument/path/resource policy]
    AR --> EX[Tool adapter]
    EX --> EV[Result sanitization + limits]
    EV --> AU[Audit + typed observation]
```

No tool accepts a raw shell string. Commands are server-defined executable/argument arrays. File tools resolve server IDs to canonical paths and re-check containment after resolution.

## Artifact publication

Agent produces a schema-validated `ArtifactSpec`. The renderer writes to a temporary path, validates the package and required sections/sheets, calculates SHA-256, moves the file to immutable workspace artifact storage, and commits metadata. Failure before commit leaves no published artifact.

## Failure taxonomy

| Category | Examples | Handling |
|---|---|---|
| `validation` | bad MIME, missing ID, invalid schema | no retry; clear user correction |
| `policy_denied` | unauthorized tool/path/network | no retry unless plan selects an allowed action |
| `dependency_unavailable` | model/Qdrant/OCR unhealthy | bounded retry or capable fallback |
| `model_output_invalid` | malformed action/citation | one repair attempt, then fail safely |
| `tool_transient` | temporary read/DB contention | exponential bounded retry |
| `sandbox_failure` | tests fail, timeout, resource kill | return evidence; retry only if agent can change solution |
| `internal` | unexpected invariant violation | fail run, correlation ID, redacted log |

## Capacity assumptions

The prototype schedules one generation-heavy run at a time to avoid VRAM contention. Upload and metadata operations may remain concurrent. Queue position is visible. Resource metrics are best-effort and show `unknown` when the host/provider cannot expose them.
