# Traceability and Readiness Checklists

## Requirement-to-evidence map

| Capability | Requirements | Primary implementation | Evidence |
|---|---|---|---|
| Workspace/files | FR-001-004 | API, file/security modules | unit + two-workspace integration |
| Documents/knowledge | FR-010-016 | documents, RAG, Qdrant | ingestion/retrieval suite |
| Models/routing | FR-020-024 | provider, registry, routing | 20 routing fixtures + health tests |
| Agent/tools | FR-030-037 | task worker, runtime, policy | state/tool integration + E2E traces |
| Code sandbox | FR-040-043 | sandbox controller/runner | coding E2E + SEC-T01-T08 |
| Artifacts/audit/sovereignty | FR-050-054 | renderers, audit, security status | artifact validators + probe/audit tests |
| Quality attributes | NFR-001-012 | cross-cutting | release report and checklist |

## Architecture review checklist

- [ ] Every module owns one coherent responsibility and dependencies follow the architecture.
- [x] PostgreSQL remains authoritative for task and provenance state. (Day 3)
- [ ] Qdrant points can be rebuilt from normalized data and relational metadata.
- [ ] Model provider is not referenced directly outside its adapter/service boundary.
- [x] All tools pass through schema and policy gateways. (Day 3)
- [x] No generated code runs in API/model-serving processes. (Day 4 sandbox boundary)
- [x] Client-controlled names/paths never become trusted storage paths. (Days 2–3)
- [x] Background work has durable state, bounded retries and explicit terminal outcomes. (Day 3)
- [ ] Metrics/UI represent unknown and degraded states honestly.

## Feature readiness checklist

- [ ] Three versioned demo datasets and fixed prompts exist.
- [x] At least two distinct generation model classes plus local embeddings are registered. (Day 1)
- [x] Routing decisions and exclusions are visible and persisted. (Day 3)
- [ ] Digital PDF, scan/OCR and image inputs are demonstrated.
- [x] RAG answers link to actual page/section evidence. (Days 2–3)
- [x] Every selected Workbench file and ready knowledge base is processed through bounded hybrid retrieval, with used pages visible in result and trace evidence. (Day 3 stabilization)
- [ ] Document, coding and procurement flows pass completion validators.
- [x] Document and coding flows pass their completion validators; procurement remains Day 5.
- [ ] DOCX and XLSX open and contain source-correct values.
- [ ] Task refresh/reconnect, cancellation and failure states behave correctly.
- [x] Audit view is driven by persistent backend evidence. (Day 3)
- [ ] Sovereignty view has dedicated egress-verification evidence.

## Security readiness checklist

- [ ] Runtime/inference networks have no unintended external route.
- [x] Sandbox has network disabled, non-root identity, read-only base and resource limits. (Day 4)
- [x] Docker socket/privileged runner risk is isolated and documented. (ADR-012)
- [x] MIME, size, pages/pixels and path containment are enforced for implemented inputs. (Days 2–4)
- [x] Tool permissions default deny and all denials are audited. (Days 3–4)
- [ ] Cross-workspace access and prompt injection tests pass.
- [ ] Logs/errors contain no prompts, document text, secrets or sensitive host paths.
- [ ] Artifact spreadsheet injection and unsafe link/macro cases pass.
- [ ] All SEC-T01 through SEC-T12 pass with recorded evidence.

## Offline release checklist

- [ ] Dependencies, images and model weights are pinned and locally available.
- [ ] Fresh Compose start requires no internet download.
- [ ] Database migrations complete from empty state.
- [ ] All service/capability health checks pass or expected degradation is documented.
- [ ] Controlled egress test records denial and probe configuration.
- [ ] Full test and evaluation reports record hardware/model/prompt/data versions.
- [ ] All three demos pass 10 consecutive rehearsals.
- [ ] Restart and interrupted-run behavior is verified.
- [ ] Database/data backup and restore have been rehearsed.
- [ ] Backup recording, screenshots, expected artifacts and talk track are available.
- [ ] Known limitations and production gaps are ready to present.

## Definition-of-done evidence record

For each must requirement, record:

```text
Requirement ID:
Build/commit:
Test case/report:
Input dataset version:
Model/provider/prompt version:
Observed result:
Reviewer/date:
Known limitation:
```

## Final go/no-go rule

No-go if any must workflow cannot complete reliably; a required security negative test fails; execution needs the public internet; artifacts cannot be validated; evidence is fabricated/missing for a central claim; or a fresh start cannot be recovered in the available demo window. Cosmetic defects and explicitly deferred should/could features do not block release unless they obscure evidence or make the demo unusable.
