# SovereignForge Engineering Plan

Status: Day 5 prototype complete
Target: seven-day prototype  
Source brief: [`../details.md`](../details.md)

This folder is the implementation source of truth for **SovereignForge**, an on-premise agentic AI workbench for confidential industrial work. The plan intentionally optimizes for a reliable competition prototype, not a production-scale platform.

## Document map

| Document | Purpose | Primary audience |
|---|---|---|
| [01-product-charter.md](01-product-charter.md) | Vision, outcomes, scope, assumptions, success measures | Product, judges, engineering |
| [02-requirements.md](02-requirements.md) | Functional and non-functional requirements with acceptance criteria | Product, QA, engineering |
| [03-features-and-workflows.md](03-features-and-workflows.md) | Features, user journeys, workflow behavior, UX states | Product, design, frontend |
| [04-architecture.md](04-architecture.md) | Architecture drivers, boundaries, deployment, major decisions | Architects, backend, DevOps |
| [05-system-design.md](05-system-design.md) | Runtime flows, components, data movement, Mermaid diagrams | Engineering team |
| [06-low-level-design.md](06-low-level-design.md) | Modules, interfaces, state machines, algorithms, error behavior | Implementers, reviewers |
| [07-data-and-api-design.md](07-data-and-api-design.md) | Data model, API contracts, events, retention | Backend, frontend, QA |
| [08-security-and-sovereignty.md](08-security-and-sovereignty.md) | Threat model, controls, trust boundaries, proof plan | Security, judges, DevOps |
| [09-testing-and-evaluation.md](09-testing-and-evaluation.md) | Test pyramid, AI evaluation, quality gates, test cases | QA, engineering |
| [10-delivery-plan.md](10-delivery-plan.md) | Seven-day schedule, work breakdown, dependencies, DoD | Lead, all contributors |
| [11-operations.md](11-operations.md) | Local deployment, configuration, monitoring, recovery | DevOps, developers |
| [12-demo-and-ux-plan.md](12-demo-and-ux-plan.md) | Screen inventory, demo script, demo data and fallbacks | Design, presenters |
| [13-risks-and-decisions.md](13-risks-and-decisions.md) | Risk register and architecture decision records | Lead, reviewers |
| [14-traceability-and-checklists.md](14-traceability-and-checklists.md) | Requirements coverage, readiness and release checklists | Lead, QA |
| [15-technology-and-engineering-standards.md](15-technology-and-engineering-standards.md) | Chosen stack, repository structure, coding and review standards | Developers, DevOps |
| [16-day-1-build-record.md](16-day-1-build-record.md) | Implemented foundation, verification evidence, and remaining limitations | Lead, developers, QA |
| [17-day-2-build-record.md](17-day-2-build-record.md) | Implemented knowledge ingestion/retrieval, verification evidence, and Day 3 handoff | Lead, developers, QA |
| [18-proposed-solution.md](18-proposed-solution.md) | Submission-ready solution explanation, problem alignment, innovation, and current evidence | Judges, product, presenters |
| [19-setup-and-run-guide.md](19-setup-and-run-guide.md) | First-time machine setup, daily startup, shutdown, migration, and troubleshooting | Developers, operators |
| [20-day-3-build-record.md](20-day-3-build-record.md) | Governed task runtime, routing, tools, artifacts, audit trail, and verification evidence | Lead, developers, QA |
| [21-day-3-ui-stabilization.md](21-day-3-ui-stabilization.md) | Closure record for the 14 reported UI/control gaps and remaining milestone boundaries | Lead, developers, QA |
| [22-day-3-hybrid-retrieval.md](22-day-3-hybrid-retrieval.md) | Workbench direct-read, temporary RAG, multi-library merge, limits, provenance, and verification | Lead, developers, QA |
| [23-scaling-and-capacity-plan.md](23-scaling-and-capacity-plan.md) | Current concurrency limits, latency and throughput metrics, ten-user architecture, load tests, and phased scaling plan | Architects, backend, DevOps, QA |
| [24-m5-16gb-setup-guide.md](24-m5-16gb-setup-guide.md) | Exact installation, model, startup, registration, verification, and daily-use commands for an M5 Mac with 16 GB unified memory | Developers, operators |
| [24-day-4-build-record.md](24-day-4-build-record.md) | Governed coding mode, sandbox boundaries, patch validation, artifacts, and acceptance evidence | Lead, developers, security, QA |
| [25-day-5-build-record.md](25-day-5-build-record.md) | Multimodal evidence, procurement comparison, validated XLSX/DOCX artifacts, and acceptance evidence | Lead, developers, security, QA |
| [sovereign-ai-architecture-flowchart.png](sovereign-ai-architecture-flowchart.png) | Draw.io-style UML component/deployment flow from browser ingress through agents, knowledge, governed tools, and local infrastructure ([editable SVG](sovereign-ai-architecture-flowchart.svg)) | Architects, developers, judges |
| [27-architecture-flowchart-guide.md](27-architecture-flowchart-guide.md) | Reading guide, notation, boundaries, and stage-by-stage explanation for the architecture flowchart | Architects, developers, product, judges |
| [28-presentation-demo-datasets-plan.md](28-presentation-demo-datasets-plan.md) | Three-workflow synthetic dataset specification, fixed prompts, ground truth, setup, acceptance, timing, and fallback plan | Presenters, product, QA, engineering |
| [30-presentation-dataset-build-record.md](30-presentation-dataset-build-record.md) | Built corpus, live acceptance run IDs, artifact checksums, QA findings, and presentation-day commands | Presenters, product, QA, engineering |
| [sovereign-ai-workbench-flow.png](sovereign-ai-workbench-flow.png) | Draw.io-style UML activity flow for automatic routing, governed execution, validation, audit, and artifacts ([editable SVG](sovereign-ai-workbench-flow.svg)) | Architects, developers, judges |
| [26-workbench-flowchart-guide.md](26-workbench-flowchart-guide.md) | Stage-by-stage explanation of every activity, decision, branch, control, and terminal state in the UML flowchart | Architects, developers, product, judges |

## Working rules

1. Scope is frozen to the three demo workflows and seven core capabilities.
2. A feature is complete only when its acceptance criteria and relevant tests pass.
3. AI-generated claims must be grounded in supplied files or explicitly marked as inference.
4. No cloud AI API or internet dependency is allowed during task execution.
5. Security controls must be enforced by code/container boundaries and demonstrated by tests.
6. New scope requires an explicit trade-off: remove or defer work of comparable effort.

## Decision authority

- Product scope and priority: product/technical lead.
- Architecture, data and security boundaries: technical lead.
- Acceptance evidence and release decision: technical lead plus QA owner.
- Demo narration may simplify wording but must not contradict measured behavior.

## Suggested repository target

```text
frontend/              Next.js application
backend/               FastAPI modular monolith and tests
sandbox/               isolated code-runner image and policies
docker/                service configuration
demo-data/             deterministic demo and evaluation inputs
scripts/               setup, health, seed and offline verification
docs/                  this planning baseline
docker-compose.yml     local orchestration
README.md              setup and operator quick start
```

## Change control

For material design changes, update the affected document, add an ADR in `13-risks-and-decisions.md`, and update traceability in `14-traceability-and-checklists.md`. Do not silently change a security boundary or acceptance criterion in code.
