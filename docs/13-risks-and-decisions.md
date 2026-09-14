# Risks and Architecture Decisions

## Risk register

Scales: probability/impact `L`, `M`, `H`. Owners are roles to assign.

| ID | Risk | P/I | Mitigation | Trigger/contingency | Owner |
|---|---|---|---|---|---|
| R-01 | Model too slow or exceeds VRAM | H/H | quantized models, one-run queue, measure early, pre-warm | miss workflow budget -> smaller capable model | AI/platform |
| R-02 | Local model emits invalid tool action | H/H | strict schema, repair once, bounded fallback/failure | validation rate high -> simplify prompt/actions | Backend |
| R-03 | OCR/table quality harms facts | M/H | digital extraction first, demo corpus, confidence/review | required field absent -> qualified output/manual review | Documents |
| R-04 | Sandbox boundary is incomplete | M/H | hardened profile, narrow controller, negative tests | any escape/network success -> release blocker | Security |
| R-05 | “Zero calls” claim lacks evidence | M/H | network config plus probe/audit; honest unknown state | probe stale/fails -> mark degraded | Platform |
| R-06 | Qdrant/metadata lifecycle diverges | M/M | versioned staging/activation, relational provenance | count/check failure -> retain prior active version | Backend |
| R-07 | Agent runs are flaky | H/H | fixed prompts/data, low temperature, validators, 10 rehearsals | <10 consecutive successes -> simplify workflow | Lead |
| R-08 | Seven-day scope expands | H/H | must/should/deferred, daily gate, cut list | critical path slips -> cut should items | Lead |
| R-09 | Artifact appears valid but contains wrong values | M/H | structured specs and source assertions, package validation | mismatch -> block publication | Artifacts/QA |
| R-10 | Host/repo lacks reproducible dependencies | M/H | lock/pin, preload, offline cold-start test | download attempted offline -> release blocker | DevOps |
| R-11 | Confidential content leaks to logs | M/H | metadata-only logs, redaction, log scan | any raw content -> fix/purge before demo | Security |
| R-12 | Single-process worker loses in-flight work | M/M | durable steps, interrupted state, safe retry | restart -> retry from clean attempt | Backend |

## Architecture decision records

### ADR-001: modular monolith

- Status: accepted.
- Decision: one FastAPI codebase with enforced modules; PostgreSQL, Qdrant, Ollama and sandbox remain separate processes.
- Rationale: shortest path to a coherent prototype while retaining clear extraction seams.
- Consequence: independent scaling/deployment is deferred; internal boundaries need tests/review.

### ADR-002: Ollama behind provider protocol

- Status: accepted.
- Decision: Ollama is the prototype adapter; domain code depends on `ModelProvider`.
- Rationale: quick local setup with a migration seam for vLLM/TGI/llama.cpp.
- Consequence: only required provider behavior is generalized; avoid lowest-common-denominator overdesign.

### ADR-003: deterministic capability routing

- Status: accepted.
- Decision: derive capabilities with rules and select via hard filters plus stable score.
- Rationale: predictability, testability and auditability are more important than autonomous model choice.
- Consequence: new task classes require explicit rule/fixture changes.

### ADR-004: PostgreSQL + Qdrant + filesystem

- Status: accepted.
- Decision: relational state/provenance in PostgreSQL, vectors in Qdrant, binaries locally.
- Rationale: appropriate tools for durable workflow state, vector retrieval and large files.
- Consequence: lifecycle consistency is application-managed through versioning and validation.

### ADR-005: bounded plan/action/observe runtime

- Status: accepted.
- Decision: one structured action per step with 12-step/3-retry/timeout defaults.
- Rationale: inspectable autonomy with deterministic safety bounds.
- Consequence: complex tasks may stop incomplete and must report that honestly.

### ADR-006: container-isolated code execution

- Status: accepted for prototype with caveat.
- Decision: ephemeral non-root no-network container with strict resources and task-only files.
- Rationale: generated code must never run in API process/host context.
- Consequence: Docker-controller access is a privileged boundary requiring further production isolation.

### ADR-007: template-driven artifacts

- Status: accepted.
- Decision: generate DOCX/XLSX from typed specs and controlled templates.
- Rationale: reliable structure, safer content and direct validation.
- Consequence: flexible free-form layouts are deferred.

### ADR-008: SSE plus durable state

- Status: accepted.
- Decision: SSE provides live progress; PostgreSQL is authoritative and supports polling/reconnect.
- Rationale: responsive UX without making a transient connection part of correctness.
- Consequence: event ordering and reconnection need explicit sequence numbers.

### ADR-009: evidence-scoped sovereignty claim

- Status: accepted.
- Decision: report enforced application/runtime boundaries, observations and unknowns separately.
- Rationale: a containerized app cannot honestly prove the absence of all host traffic.
- Consequence: presentation language is narrower but defensible.

### ADR-010: native Ollama on Apple Silicon prototype

- Status: accepted.
- Decision: run Ollama natively on macOS with cloud features disabled; run application and data services in Colima/Docker Compose.
- Rationale: native Ollama uses Apple Metal, while a Linux container on macOS would not provide the same practical acceleration on the M1 8 GB demo machine.
- Consequence: the API needs an explicit host-gateway route, and Day 6 egress controls must preserve only that local dependency route. The final sovereignty claim remains scoped to measured/enforced boundaries.

### ADR-011: versioned full-set ingestion command

- Status: accepted on Day 2.
- Decision: `POST /knowledge-bases/{id}/ingestions` receives the complete desired file set and creates an immutable index version. Activation occurs only after extraction, metadata persistence, embedding, and vector upsert all succeed.
- Rationale: an explicit ingestion resource exposes progress/failure cleanly and avoids ambiguous partial-add semantics. It also gives Day 3 a durable command boundary to move from framework background tasks to a DB-claimed worker.
- Consequence: clients must send the desired file set for each replacement version; incremental vector patching and garbage collection of inactive versions are deferred.

### ADR-012: privileged sandbox controller and ephemeral volumes

- Status: accepted for the Day 4 prototype.
- Decision: keep the Docker socket out of the API container. An internal token-protected controller creates a short-lived materializer, an ephemeral task volume, and a separate no-network execution container. The generated-code container mounts repository content read-only and is removed with its volume in every terminal path.
- Rationale: Docker cannot copy an archive directly into a read-only container root. A bounded materializer allows safe population without giving the API daemon access or making the execution mount writable.
- Consequence: the controller remains daemon-privileged infrastructure. Production hardening requires a dedicated host or micro-VM runtime, mutual authentication, scheduling, and independent monitoring.

## Open decisions with deadline

| Decision | Decide by | Evidence needed | Default |
|---|---|---|---|
| Exact general/vision/coder/embedding models | Day 1 | demo hardware VRAM, capability smoke tests, licenses | smallest capable quantized models |
| OCR engine | Resolved Day 2 | page-level fallback verified locally | Tesseract 5 |
| In-process worker mechanism | Resolved for Day 2 | complete vertical slice; restart durability deferred | FastAPI background task, DB job record |
| Host egress enforcement method | Day 1 | OS/Docker environment | internal network + sandbox none |
| Demo office viewers | Day 5 | target machine availability | LibreOffice or installed standard suite |
