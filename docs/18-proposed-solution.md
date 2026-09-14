# Proposed Solution

- SovereignForgeAI means a secure, organization-controlled AI workspace that transforms confidential industrial data into trusted and actionable outputs.

- It communicates:
- Sovereign: control over data, models and infrastructure
- Forge: transformation of industrial information into useful outcomes
- AI: immediately identifies the product category
Recommended presentation:
SovereignForgeAI
Secure On-Premise Agentic AI for Confidential Industrial Work

- Use the name consistently as one word and capitalize AI. Before commercial use, verify domain and trademark availability.


**Problem Statement:** Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal LLMs for Confidential Industrial Work  
**Problem Statement ID:** SHI26117  
**Solution Name:** SovereignForge

## 1. Detailed explanation of the proposed solution

SovereignForge is a sovereign, on-premise agentic AI workbench designed for industrial organizations that need the benefits of generative AI without sending confidential information to cloud AI services. It enables engineers and analysts to process internal documents, scanned reports, equipment images, source code, tabular data, maintenance procedures and procurement records entirely within an organization-controlled computing environment. Local open-weight models perform generation, reasoning, vision analysis and embedding; local services store files, metadata and vectors; and controlled tools convert AI decisions into verified actions and usable business deliverables.

Unlike a conventional chatbot, SovereignForge operates as an AI workbench. A user selects files and internal knowledge sources, describes the required outcome, and receives a live, auditable execution showing how the task was classified, which model was selected, which approved tools were used, what evidence supported the result and which artifacts were produced. The system is designed around seven integrated capabilities:

1. **Local open-weight model serving:** Ollama provides the initial on-premise inference layer, with cloud functionality disabled. A provider-neutral `ModelProvider` interface allows the same application to support vLLM, TGI or llama.cpp in future deployments without rewriting business workflows.
2. **Multi-model registry and intelligent routing:** The registry records each local model's capabilities, health, context window, quantization, priority and resource needs. A deterministic capability router classifies a task and selects a healthy model that satisfies all mandatory capabilities. General reasoning, coding and embedding workloads can therefore use models suited to their purpose instead of forcing every task through one large model.
3. **Multimodal document understanding:** The local ingestion pipeline accepts PDFs, scanned pages, PNG/JPEG images, text, Markdown, CSV and Python files. It extracts digital PDF text, invokes page-level OCR when necessary, preserves page provenance and merges text, image findings, tables, warnings and confidence into a normalized document representation.
4. **Grounded local knowledge retrieval:** Internal policies, SOPs and manuals are chunked with page-aware metadata, embedded locally and stored in Qdrant. Retrieval is restricted by workspace, knowledge base and index version. Answers may cite only supplied chunks; unsupported claims are qualified or marked for review rather than being presented as facts.
5. **Governed agentic execution:** A bounded plan–act–observe loop allows the selected model to propose one structured action at a time. Every action passes strict schema validation and a server-controlled tool-permission gateway before execution. The run enforces maximum steps, retry limits and task/tool timeouts, while durable task state and ordered events make progress inspectable and resilient to browser refresh.
6. **Isolated code verification:** Coding tasks execute in an ephemeral, non-root container with no network, a read-only base filesystem, a task-specific working directory and CPU, memory, process, output and time limits. Proposed changes are applied only to a working copy. A result is declared successful only after prescribed tests or verification commands pass; the original source remains unchanged.
7. **Validated artifacts and sovereignty evidence:** Typed, template-driven tools create DOCX approval notes, XLSX comparison workbooks, patches and test evidence. Before publication, the platform checks file structure and required content, then records the artifact's originating run, MIME type, size and SHA-256 checksum. A dedicated Sovereignty Center displays enforced network boundaries, local model health, controlled egress-test results, local request counts, tool denials and audit evidence. Missing telemetry is shown as `unknown`, not converted into a misleading zero.

The prototype uses a modular-monolith architecture to remain reliable and deliverable within the competition timeline while preserving clear module boundaries. A Next.js and TypeScript interface communicates with a FastAPI backend through REST and server-sent events. PostgreSQL is the authoritative store for workspaces, model metadata, tasks, execution steps, artifacts and audit events; Qdrant holds locally generated document vectors; the local filesystem stores immutable uploads, normalized extracts and published artifacts; Ollama serves the open-weight models; Tesseract provides offline OCR; and an isolated container runner verifies generated code. PostgreSQL and Qdrant remain on private container networks, while user-facing services bind only to the controlled local host.

### Representative end-to-end workflows

**Industrial inspection review:** A maintenance engineer uploads an inspection report, an equipment image and the approved maintenance SOP. SovereignForge extracts or OCRs the report, analyzes the image locally, identifies the equipment and observed defect, retrieves the applicable SOP clauses, assesses severity and prepares a cited corrective-maintenance approval note in DOCX format. Low-confidence identity, unreadable pages or insufficient policy evidence cause an explicit `needs_review` outcome instead of an invented conclusion.

**Safe coding agent:** An automation engineer supplies Python source, tests and a CSV fixture. The router selects the coding model; the agent reads only the provided workspace, diagnoses the defect, proposes a patch and executes tests inside the network-disabled sandbox. It returns the patch, modified file and test evidence only after validation. Timeouts, resource violations and unsafe network or path requests are terminated and recorded.

**Procurement decision support:** A procurement analyst uploads vendor quotations and the organization's procurement policy. The workbench extracts price, warranty, delivery and compliance data while retaining original source references, applies explicit comparison criteria, retrieves relevant policy requirements and produces a validated XLSX comparison plus a cited DOCX recommendation. Missing values remain “Not provided,” conflicts remain visible and tied recommendations are not broken arbitrarily.

Together, these workflows demonstrate that SovereignForge is not limited to answering questions: it can perceive multimodal inputs, retrieve institutional knowledge, reason under policy, invoke controlled tools, verify outcomes and deliver files that fit real industrial work.

## 2. How the solution addresses the problem

| Problem faced by industrial organizations | SovereignForge response | Verifiable outcome |
|---|---|---|
| Sensitive reports, designs, code and commercial bids cannot be shared with public AI services | All generation, vision, OCR, embeddings, retrieval and file processing run on organization-controlled infrastructure using open-weight models | No cloud AI dependency during execution; controlled runtime-egress checks and local-request evidence are displayed |
| A single general-purpose model is inefficient and unreliable across diverse industrial tasks | Capability-based routing selects a healthy general, vision or coding model based on explicit task requirements | The selected model, excluded candidates and routing reasons are persisted and visible |
| Industrial information exists in mixed formats, including scans, images, PDFs, tables and code | A unified local ingestion layer performs native extraction, OCR fallback, image analysis and page-aware normalization | Findings retain document and page provenance, warnings and confidence information |
| LLM responses may hallucinate procedures, clauses or commercial facts | Workspace-scoped RAG supplies internal evidence, restricts citation IDs and requires abstention or review when evidence is weak | Users can open the cited page or section beside each material claim |
| Autonomous agents may access unsafe tools, paths, networks or commands | Model output is treated as untrusted; strict schemas, default-deny tool profiles, opaque file IDs, path containment and fixed command allowlists constrain every action | Allowed and denied actions are recorded in a durable execution and audit trace |
| Generated code can damage the host or leak data | Code runs only in a disposable, resource-bounded, network-disabled container using task-specific files | Exit code, test results, duration, output limits and cleanup status provide objective verification |
| AI outputs often stop at chat text and do not integrate into existing work | Controlled templates generate standard DOCX and XLSX deliverables, while artifact validators inspect structure and content before publication | Users receive openable, traceable files with checksum and source-run provenance |
| “On-premise” and “zero external calls” are often marketing claims without proof | The Sovereignty Center separates enforced configuration, observed evidence and unknown health/telemetry | Judges and administrators can inspect topology, model identity, timestamps, probe results and audit counters |
| Complex AI execution is difficult to trust or reproduce | Durable states, ordered action summaries, citations, model/config versions, retries and completion validators are preserved | Runs survive UI refresh and can be evaluated against fixed datasets and expected outputs |

The project plan also turns these capabilities into measurable acceptance criteria. The release target is three complete end-to-end workflows, full model-routing accuracy on the fixed routing suite, valid required artifacts, at least 90% grounded answers with usable citations on the fixed evaluation set, complete blocking of defined sandbox traversal/network cases, zero unplanned external runtime connections and ten consecutive successful demo rehearsals. These figures are treated as targets until recorded tests produce evidence; failed runs remain part of the evaluation report.

## 3. Innovation and uniqueness of the solution

### A. Sovereignty is a measurable product capability

Most local-AI demonstrations equate “the model is running on my laptop” with security. SovereignForge makes a narrower and more defensible claim. It combines local open-weight inference with private service networks, network-disabled sandboxes, the absence of cloud AI adapters, controlled egress probes, local-model request counters and auditable security events. The interface clearly separates what is enforced, what has been observed and what is not measurable. This makes sovereignty visible and testable rather than a deployment assumption.

### B. Deterministic governance around probabilistic models

The platform uses AI where interpretation and generation add value, but keeps authority in deterministic software. Task capabilities, model eligibility, tool permissions, path boundaries, timeouts, citation validation and completion rules are enforced by server code. The model proposes actions; it does not grant itself tools, choose arbitrary host paths or certify its own success. This combination delivers useful autonomy without surrendering operational control.

### C. One sovereign control plane for heterogeneous models and work

SovereignForge unifies general reasoning, multimodal understanding, coding and embeddings behind a capability-aware registry. A lightweight specialist model can be selected for each workload based on capability and health, which is especially valuable on constrained on-premise hardware. The provider abstraction also avoids locking the organization to a single serving engine or model family.

### D. Evidence-linked actions, not only evidence-linked answers

Traditional RAG products usually end with a cited paragraph. SovereignForge carries evidence through the entire operational chain: source page to retrieved chunk, retrieved chunk to recommendation, recommendation to tool action, and tool action to validated artifact. A maintenance approval note or procurement workbook therefore retains both knowledge provenance and execution provenance.

### E. Workflow-specific proof of completion

The system never accepts a model's statement that a task succeeded. Inspection results require valid citations and a structurally valid approval note; coding tasks require test evidence and no unrelated source changes; procurement tasks require source-correct values and valid workbook/document structures. These validators convert an open-ended AI response into an outcome that can be objectively checked.

### F. Secure multimodal and agentic processing in one practical workbench

The distinctive value is the integration of offline multimodal understanding, local RAG, multi-model routing, governed tool execution, sandboxed coding, office artifact generation and sovereignty monitoring in one coherent user experience. The same platform can support maintenance, engineering and commercial teams while applying common controls for data locality, permissions, traceability and validation.

### G. Reliability designed for constrained industrial deployments

The prototype is intentionally optimized for a single workstation, including an Apple M1 system with 8 GB unified memory. Quantized local models, single-run scheduling, page-at-a-time OCR, bounded embedding batches, staged vector-index activation and immutable artifact publication enable useful work without requiring a data center. If re-indexing fails, the prior knowledge-base version stays active; if a service becomes unavailable, the interface reports a degraded state rather than presenting fabricated success.

## Current prototype evidence and delivery position

The implementation has already validated the foundation and local-knowledge vertical slice on the target M1/8 GB machine. The working prototype includes the Next.js/FastAPI application, PostgreSQL and Qdrant private data services, provider-neutral Ollama integration, local model health and inference, secure uploads, native PDF extraction with page-level Tesseract OCR fallback, deterministic chunking, local `nomic-embed-text` embeddings, versioned Qdrant ingestion, cited semantic retrieval and the Dashboard, Workbench, Models and Knowledge interfaces. The registered local models include `qwen3:1.7b` for general reasoning, `qwen2.5-coder:1.5b` for coding and `nomic-embed-text` for embeddings.

Verified evidence includes clean lint, type-check, test and production-build runs; successful service health checks and database migrations; direct local-model inference; ingestion of the demonstration maintenance SOP; retrieval of the correct pump-isolation evidence with a page citation; and browser-level verification without console errors. The remaining planned milestones add the durable agent runtime and router, coding sandbox, multimodal inspection and procurement workflows, artifact ecosystem, audit and sovereignty screens, full security suite and final offline rehearsal. This distinction keeps the proposal transparent: completed capabilities are supported by recorded evidence, while later capabilities remain scheduled prototype scope until their acceptance tests pass.
