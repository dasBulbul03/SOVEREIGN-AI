# Requirements Specification

Priority uses MoSCoW: **M** must, **S** should, **C** could. Each requirement has a stable ID for tests and traceability.

## Functional requirements

### Workspace and files

| ID | Pri | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-001 | M | Create and select a workspace | Workspace is persisted and isolates its documents, tasks and artifacts |
| FR-002 | M | Upload supported files | PDF, PNG/JPEG, TXT/MD, PY and CSV are accepted within configured limits |
| FR-003 | M | Validate files before storage | Unsafe filename/path, unsupported MIME, size excess and malformed file are rejected |
| FR-004 | M | List and download workspace files/artifacts | Only resolved paths beneath the workspace root are accessible |

### Knowledge and documents

| ID | Pri | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-010 | M | Parse digital PDFs locally | Extracted text retains page metadata |
| FR-011 | M | OCR scanned pages locally | A text-poor page triggers OCR and records the extraction method |
| FR-012 | M | Analyze supplied images locally | Description/findings are stored with source identity; no remote endpoint is used |
| FR-013 | M | Index documents in a knowledge base | Chunk count/status are persisted and vectors exist in Qdrant |
| FR-014 | M | Search a knowledge base semantically | Top results include document, page/section and relevance score |
| FR-015 | M | Produce grounded answers | Material claims cite source chunks; absent evidence is reported as such |
| FR-016 | S | Re-index safely | Replacement index is activated only after successful ingestion |
| FR-017 | M | Ground Workbench tasks across all selected sources | One small file is read directly; large/multiple files use bounded temporary retrieval; every selected ready knowledge base is searched; merged evidence retains file, knowledge-base and page provenance |

### Models and routing

| ID | Pri | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-020 | M | Register local models and capabilities | Registry exposes provider, model key, capabilities, context, quantization, resources and status |
| FR-021 | M | Health-check configured models | Status is `ready`, `degraded`, `unavailable` or `unknown` with timestamp |
| FR-022 | M | Classify supported task types | Coding, vision/document, RAG, spreadsheet and general fixtures classify deterministically |
| FR-023 | M | Select a capable healthy model | Selected model covers every required capability and decision reasons are persisted |
| FR-024 | S | Fall back to another capable model | Unhealthy preferred model causes a recorded fallback, not silent failure |

### Agent execution and tools

| ID | Pri | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-030 | M | Create and execute a task | Run status and steps persist and survive browser refresh |
| FR-031 | M | Bound every run | Maximum steps, retries, task timeout and per-tool timeout are enforced |
| FR-032 | M | Invoke tools through one registry | Inputs are schema-validated and results use a common envelope |
| FR-033 | M | Enforce per-agent tool allowlists | Unauthorized tool request is denied and audited |
| FR-034 | M | Stream/poll execution progress | UI receives ordered durable steps and terminal status |
| FR-035 | M | Create auditable artifacts | Artifact includes creator run, checksum, MIME, path and timestamp |
| FR-036 | M | Retry recoverable failures | Retry count is bounded and every attempt is visible in the trace |
| FR-037 | M | Support cancellation | A requested cancellation prevents new steps and ends in `cancelled` |

### Sandboxed coding

| ID | Pri | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-040 | M | Copy only task files into an ephemeral sandbox | Container cannot read host paths outside its mounted task workspace |
| FR-041 | M | Execute Python/tests without network | Execution captures exit code/stdout/stderr/duration and external request fails |
| FR-042 | M | Apply proposed changes only in sandbox | Original upload is retained; generated patch and verified output are separate artifacts |
| FR-043 | M | Enforce resource limits | CPU, memory, process, output and time limits terminate violations safely |

### Artifacts, audit and sovereignty

| ID | Pri | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-050 | M | Generate a structured DOCX | File opens successfully and contains required template sections |
| FR-051 | M | Generate a styled XLSX | File opens successfully, formulas/values are verified, and recommendation evidence is present |
| FR-052 | M | Audit security-relevant actions | Task, model, file, RAG, tool, sandbox, artifact and terminal events are queryable |
| FR-053 | M | Report sovereignty evidence | Screen distinguishes enforced status, observed counters and unknown metrics |
| FR-054 | M | Prove runtime egress denial | A repeatable in-container test fails to reach an external address and is logged |

## Non-functional requirements

| ID | Attribute | Requirement / target |
|---|---|---|
| NFR-001 | Sovereignty | Generation, vision, OCR and embedding execution is local; runtime has no required internet route |
| NFR-002 | Security | Default-deny tools, canonicalized workspace paths, MIME/size validation, no shell interpolation |
| NFR-003 | Reliability | Durable task/step state; terminal failure is explicit; restart does not corrupt completed runs |
| NFR-004 | Performance | API metadata p95 under 500 ms locally, excluding model/ingestion work; progress visible within 2 s |
| NFR-005 | Capacity | Prototype supports one active agent run and queued additional runs without data loss |
| NFR-006 | Maintainability | Typed contracts, clear module boundaries, migrations, linting and automated tests |
| NFR-007 | Observability | Correlation IDs, structured logs, run/tool timing, health status and error categories |
| NFR-008 | Portability | One documented Docker Compose startup on the selected Linux-compatible host |
| NFR-009 | Accessibility | Keyboard reachable core actions, meaningful labels, visible focus and non-color status cues |
| NFR-010 | Privacy | Prompts/document contents excluded from normal logs; no secrets in repository or trace payloads |
| NFR-011 | Explainability | Routing reason, sources, tool actions and artifact provenance are inspectable |
| NFR-012 | Compatibility | Current Chromium-based browser; generated DOCX/XLSX opens in standard office applications |

## Business rules

- BR-001: A model can be selected only when all mandatory capabilities match and its last health state is acceptable.
- BR-002: A task never gains a tool permission through model output; permissions come from server configuration.
- BR-003: User filenames are display metadata, not filesystem paths. Stored names are server-generated.
- BR-004: A knowledge answer without sufficient retrieval evidence must abstain or qualify uncertainty.
- BR-005: Every artifact is immutable after publication; revisions create a new artifact record.
- BR-006: A run reaches exactly one terminal state: `completed`, `failed`, `cancelled`, or `timed_out`.
- BR-007: Sovereignty counters are evidence-derived. Missing instrumentation is shown as `unknown`.

## Explicitly uncommitted production requirements

High availability, disaster recovery across hosts, enterprise identity, fine-grained document ACL synchronization, regulatory certification, GPU scheduling and horizontal scale require a later production discovery phase. The prototype architecture leaves seams for them but does not claim them.
