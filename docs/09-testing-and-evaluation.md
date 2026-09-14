# Testing and AI Evaluation Strategy

## Quality gates

| Gate | Required to merge | Required to demo/release |
|---|:---:|:---:|
| Format/lint/type checks | yes | yes |
| Unit suite | yes | yes |
| Integration suite for touched modules | yes | yes |
| Three end-to-end workflows | for workflow changes | yes |
| Security negative suite | for boundary changes | yes |
| Offline/cold-start test | no | yes |
| Artifact open/structure validation | for renderer changes | yes |
| Recorded evaluation report | no | yes |

## Test layers

### Unit

- Capability derivation, router filtering/scoring/tie-break.
- Run state transitions, limit and retry logic.
- Tool schema/permission decisions.
- Path containment, filename/MIME/size validation and redaction.
- Chunk boundaries, metadata propagation and citation validation.
- DOCX/XLSX template builders and formula escaping.
- Error categorization and sovereignty status aggregation.

### Integration

- PDF -> normalized pages -> chunks -> local embeddings -> Qdrant -> cited result.
- Task -> route -> agent -> mock/local model -> tool -> durable steps -> artifact.
- Upload/download ownership with two isolated workspaces.
- Sandbox materialization -> test command -> bounded result -> cleanup.
- Process interruption and recovery marking.

### End to end

Run the exact three demo prompts against versioned demo files and model/config versions. Assert terminal state, selected capability/model class, required tools, source IDs, artifact MIME/structure, test evidence, and zero unexpected outbound dependency.

## Required security cases

| ID | Case | Expected result |
|---|---|---|
| SEC-T01 | path `../../etc/passwd` | validation/policy denial and audit |
| SEC-T02 | symlink in sandbox input/output | rejected or not followed |
| SEC-T03 | generated network request | connection fails in sandbox |
| SEC-T04 | generated subprocess/shell tool request by document agent | permission denial |
| SEC-T05 | prompt-injected SOP requests unrelated file | tool/workspace policy denial |
| SEC-T06 | infinite Python loop | timeout and runner cleanup |
| SEC-T07 | fork/process bomb | PID/resource kill |
| SEC-T08 | stdout flood | bounded/truncated result |
| SEC-T09 | formula-leading vendor value | emitted as safe text, not executable formula |
| SEC-T10 | cross-workspace UUID | not found/forbidden without metadata leak |
| SEC-T11 | malformed/oversized upload | rejected before processing |
| SEC-T12 | logs after confidential task | no raw prompt/document/secrets |

## AI evaluation set

Version the dataset, expected behavior, model identifiers, quantization, prompt version and thresholds.

| Slice | Minimum cases | Metric |
|---|---:|---|
| Routing | 20 | exact capability/model-class accuracy |
| Document retrieval/QA | 20 questions | Recall@5, citation validity, answer correctness |
| Multimodal extraction | 5 | required field accuracy and review flag quality |
| Coding | 5 defects | verified task completion and regression pass |
| Artifact generation | 10 outputs | opens, required structure, value correctness |
| Adversarial/prompt injection | 10 | policy violation prevention |

## Scoring definitions

- **Routing accuracy**: cases whose selected model satisfies the expected class/capabilities divided by all cases.
- **Citation validity**: citations that resolve to supplied chunks and support the adjacent claim.
- **Grounded answer correctness**: human-reviewed rubric score for required facts, unsupported claims and abstention.
- **Coding completion**: prescribed tests pass and no unrelated file change occurs.
- **Artifact validity**: package opens, required sections/sheets exist, values match structured inputs, and security checks pass.
- **Agent success**: workflow-specific completion validator passes; model self-report is ignored.

## Determinism and evidence

- Use fixed demo inputs and prompts, low generation temperature, versioned templates and bounded context selection.
- Save only permitted evaluation outputs, route decisions, timings, checksums and test reports.
- Repeat each demo at least 10 times after freeze; report numerator/denominator, hardware and date.
- Do not publish aspirational numbers. Failed runs remain in the report.

## Performance tests

Capture cold/warm model readiness, ingestion time per page, retrieval latency, first visible progress, generation wall time, sandbox duration and peak memory/VRAM when measurable. Targets are budgets for the selected demo hardware, not universal platform guarantees.

## Release exit criteria

- All must-priority requirements have passing evidence or an explicit release-blocking exception.
- All three workflows succeed 10 consecutive times on the demo machine.
- All required security cases pass.
- Offline startup and runtime complete without a package/model download.
- DOCX/XLSX artifacts open in target viewers and match source data.
- Known limitations and measured results are documented.
