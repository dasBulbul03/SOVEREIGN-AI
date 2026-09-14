# UX and Demonstration Plan

## Information architecture

```text
Dashboard
Workbench
  Files | Task | Live execution | Sources | Artifacts
Models
Knowledge
Runs / Audit
Sovereignty
```

## Screen requirements

### Dashboard

Show measured completed tasks, success rate with numerator/denominator, healthy local models, indexed documents, artifacts, average run time and latest sovereignty status. Avoid decorative metrics without a data source.

### Workbench

Three primary panes: workspace files, task composition, execution/result. Show selected model and reason, actual durable steps, sources, review flags, errors and artifact download. Disable submit when mandatory capability/inputs are missing.

### Model registry

Show display name, provider/model key, capabilities, context, quantization, configured resources/priority, loaded state, latest health and observation time. The MVP is read-mostly; arbitrary provider endpoints are not exposed to normal users.

### Knowledge

Show knowledge bases, documents, page/chunk counts, index version/status and warnings. Actions: upload, ingest/re-index, test search, and deletion only with explicit confirmation if implemented.

### Run trace

Show route decision, ordered step status, tool/model name, duration, retries, bounded observations, citations, terminal validator and categorized errors. Never display hidden chain-of-thought; use concise action/reason summaries.

### Sovereignty

Separate configuration, observed evidence and capability health. Include last egress test result/time, restricted topology, local request count and clear scope of the claim.

## State design checklist

Each screen handles loading, empty, partial/degraded, success, validation error, dependency error and retry/cancel where relevant. Status uses icon/text as well as color. Downloads show name, MIME, size and checksum/provenance.

## Versioned demo data

```text
demo-data/
├── inspection/
│   ├── centrifugal_pump_inspection.pdf
│   ├── pump_photo.jpg
│   └── expected.json
├── knowledge/
│   ├── pump_maintenance_sop.pdf
│   ├── procurement_policy.pdf
│   └── safety_guideline.pdf
├── coding/
│   ├── temperature_monitor.py
│   ├── test_temperature_monitor.py
│   ├── readings.csv
│   └── expected.patch
└── procurement/
    ├── vendor_a.pdf
    ├── vendor_b.pdf
    ├── vendor_c.pdf
    └── expected.json
```

All documents must be synthetic or licensed/approved. Expected files turn the demo corpus into regression tests.

## Three-minute demo script

| Time | Scene | Proof |
|---:|---|---|
| 0:00-0:20 | Confidential-data problem and product statement | clear user value |
| 0:20-0:35 | Sovereignty screen | local models, restricted runtime, fresh probe evidence |
| 0:35-1:45 | Inspection workflow | multimodal processing, route, SOP sources, validated DOCX |
| 1:45-2:25 | Coding workflow | coder route, patch, isolated execution, tests pass |
| 2:25-2:45 | Procurement output | cited comparison and valid XLSX/DOCX |
| 2:45-3:00 | Architecture/close | reusable local control plane and honest boundary |

Use fixed prompts from the workflow specification. Do not type risky improvisations during the timed demo.

## Demo evidence to expose

- Local provider/model identity and route decision.
- Actual task/tool timestamps and terminal validator result.
- Page/section citations opened beside the result.
- Office artifacts opened in a standard viewer.
- Test command exit code and passed count.
- Restricted-network configuration plus controlled egress result.

## Failure playbook

| Failure | Response |
|---|---|
| Model cold/slow | show queue/health, use pre-warmed approved model, never fake completion |
| Preferred model down | demonstrate recorded capable fallback if implemented |
| OCR uncertainty | show review flag and source page; use known good demo input next |
| Sandbox/test failure | show honest trace and retry; switch to recorded successful run if time-bound |
| Office viewer issue | download/checksum plus pre-opened validated copy |
| Whole environment unavailable | use backup recording and architecture/evaluation evidence |

## Presentation claims

Say “prototype evaluation on this hardware/dataset,” not “industrial-grade accuracy.” Say “application runtime egress is blocked by these boundaries,” not “the entire host can never communicate.” Never claim a feature from a static mock unless its backend evidence exists.
