# Product Charter

## Product statement
- SovereignForge is a local-first agentic AI workbench that lets industrial teams   `analyze confidential documents` and `images`, `use internal knowledge`, `execute controlled tools`, and c`reate business artifacts` without sending data to external AI services.

## Problem
- Industrial inspection reports, 
- maintenance procedures, 
- procurement bids, and 
- source code are often confidential. 
- Cloud AI products create data-residency, egress, auditability, and tool-safety concerns. 
- Users need useful AI automation while retaining local control over models, files, execution, and evidence.

## Target users

| Persona | Need | Demonstrated workflow |
|---|---|---|
| Maintenance/reliability engineer | Compare inspection evidence with an approved SOP | Inspection review |
| Software/automation engineer | Diagnose, patch and verify code safely | Coding agent |
| Procurement analyst | Compare quotations against policy and create decision artifacts | Vendor analysis |
| Platform/security administrator | Configure local models and prove isolation | Registry and sovereignty screens |

## Product outcomes

- The prototype must prove:

1. All model inference and embeddings run locally.
2. Capability-based routing selects between at least two open-weight generation models.
3. PDFs, scanned content, images, tabular files and source code can be processed.
4. Local RAG returns page/section-level evidence.
5. Agents use allowlisted tools and persist an auditable execution trace.
6. Generated DOCX/XLSX files are valid and useful.
7. Code execution is resource-bounded, workspace-isolated and network-disabled.
8. The offline posture is enforced and demonstrable.

## Scope

### Must ship

- Local model provider and health-aware model registry.
- Deterministic task classification and capability routing.
- Upload, validation, local storage and document ingestion.
- PDF text extraction, OCR fallback and image analysis.
- Local embeddings, Qdrant retrieval and citations.
- Bounded plan/action/observe agent runtime.
- Tool registry, schemas, per-agent permissions and audit events.
- Sandboxed Python/test execution with no network.
- DOCX and XLSX artifact generation.
- Dashboard, workbench, registry, knowledge, trace and sovereignty screens.
- Three deterministic demo datasets/workflows.

### Should ship if must-scope is stable

- Model fallback when the preferred model is unhealthy.
- Artifact preview and richer run metrics.
- A small React Flow visualization of execution.
- Scanned-PDF mixed page handling.

### Deferred

- Kubernetes, microservices or distributed agents.
- Fine-tuning and custom model training.
- Enterprise SSO/RBAC/LDAP, multi-tenancy and policy synchronization.
- Production integrations such as SAP, PLM, CAD or SIEM.
- Workflow designer, mobile client or full office editor.
- PPTX as a critical demo dependency.

## Assumptions and constraints

- Delivery time is seven calendar days; scope stability has priority over breadth.
- A development machine with Docker and enough RAM/VRAM for quantized local models is available.
- Demo data is synthetic or approved for local use.
- The browser may access only the local application endpoints during the demo.
- The prototype uses one trusted local operator; full authentication is deferred but APIs still enforce workspace boundaries.
- Ollama is the initial provider; the application depends only on a provider interface.
- PostgreSQL is authoritative metadata storage, Qdrant is the vector index, and the local filesystem stores binary files.

## Success measures

| Measure | Release target |
|---|---:|
| Required workflows complete end to end | 3/3 |
| Routing fixture accuracy | 100% on fixed evaluation set |
| Valid required artifacts | 100% |
| Grounded document answers with usable citation | at least 90% on fixed set |
| Sandbox traversal/network security cases blocked | 100% |
| Unplanned external connections from runtime | 0 |
| Successful cold-start demo rehearsals | 10 consecutive |
| Hero workflow wall time on demo hardware | target under 90 seconds |

Metrics are claims only after recorded evaluation. The UI must label unavailable measurements as `unknown`, never invent zeroes.

## Definition of product done

The product is done when a fresh documented install starts offline, local models are healthy, each workflow produces its expected trace and artifacts, negative security tests pass, evidence is recorded, and a backup demo is available. Partial UI mockups do not count as completed capability.
