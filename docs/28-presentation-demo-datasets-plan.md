# Presentation Demo Dataset Plan

Status: approved planning baseline  
Demo organization: **Aegis Process Systems Pvt. Ltd.**  
Dataset policy: synthetic, deterministic, versioned, and safe to distribute

## Demo objective

Use three small datasets to prove one coherent story: a confidential industrial organization can inspect equipment, correct operational software, and evaluate suppliers using local models, governed tools, traceable evidence, and validated business artifacts.

The live presentation should use one fresh organization and one workspace per workflow. This makes tenancy and file selection easy to explain and prevents evidence from one scene leaking into another.

## Dataset portfolio

| ID | Workspace | Workflow demonstrated | Main proof | Target live time |
|---|---|---|---|---:|
| DS-01 | `01 Pump Inspection` | Document and multimodal analysis | image/PDF evidence + SOP retrieval + cited DOCX | 60–70 sec |
| DS-02 | `02 Controller Fix` | Governed coding agent | automatic coder routing + isolated tests + verified patch | 35–45 sec |
| DS-03 | `03 Pump Procurement` | Procurement analysis | deterministic comparison + policy checks + XLSX/DOCX | 35–45 sec |

Target corpus size is below 8 MB so it remains reliable on the MacBook Air M1 with 8 GB RAM. Documents should be one to four pages, images at most 1600 px on the longest side, and code repositories below 100 KB.

## Proposed folder structure

```text
demo/presentation-v1/
├── README.md
├── manifest.json
├── 01-inspection/
│   ├── aegis-p101-inspection-report.pdf
│   ├── aegis-p101-seal-leak.jpg
│   ├── aegis-pump-maintenance-sop.pdf
│   ├── prompt.txt
│   └── expected.json
├── 02-coding/
│   ├── p101-temperature-monitor.zip
│   ├── prompt.txt
│   ├── expected.patch
│   └── expected.json
├── 03-procurement/
│   ├── mechanical-seal-quotations.csv
│   ├── aegis-procurement-policy.pdf
│   ├── prompt.txt
│   └── expected.json
└── fallback/
    ├── successful-run-ids.md
    ├── expected-inspection-note.docx
    ├── expected-code-fix.patch
    ├── expected-procurement-comparison.xlsx
    └── expected-procurement-recommendation.docx
```

Generated fallback artifacts are presentation safety copies, not inputs to a live run. They must carry the same dataset version and expected checksum recorded in `manifest.json`.

## DS-01 — Pump inspection and approval

### Business story

An operator reports leakage and elevated vibration on centrifugal pump P-101. The maintenance lead needs a defensible recommendation based on the inspection record, equipment image, and internal SOP.

### Input files

| File | Required content |
|---|---|
| `aegis-p101-inspection-report.pdf` | P-101, 2026-09-12 inspection, vibration 8.2 mm/s, discharge pressure 5.8 bar, seal-area leakage, no guard damage, inspector name, and a recommendation request |
| `aegis-p101-seal-leak.jpg` | Clearly visible synthetic pump/seal area with a small leak marker; no embedded conclusion text |
| `aegis-pump-maintenance-sop.pdf` | shutdown, V-14/V-15 isolation order, lockout/tagout, DV-3 drain, zero-bar verification, two-person sign-off, and emergency stop-work rule |

The SOP is uploaded to the Knowledge Base and indexed before the presentation. The report and image are selected directly in Workbench. This deliberately demonstrates both persistent knowledge retrieval and newly uploaded task-scoped evidence.

### Fixed prompt

> Review the P-101 inspection report and image against the selected maintenance SOP. Identify the risk, state whether maintenance may proceed, list the required safety controls, cite the supporting file and page for every material claim, and create a concise approval-note DOCX for the maintenance manager. Do not invent missing facts.

### Ground truth

- Equipment: P-101 centrifugal pump.
- Risk: high and requires maintenance review because vibration is elevated and leakage is observed.
- Work must not start until P-101 is stopped, V-14 then V-15 are closed, motor and valves are locked/tagged, DV-3 is opened, zero bar is confirmed, and technician/operator signatures are recorded.
- If pressure is not zero, the only valid recommendation is stop work and escalate.
- The decision is a draft requiring human approval, not an autonomous maintenance authorization.

### Expected product evidence

- Automatic route requires text, vision, retrieval, reasoning, and document-generation capabilities.
- Trace names the report, image, SOP, cited pages, selected local model, and retrieval/tool stages.
- Result renders as formatted Markdown.
- One branded, validated DOCX is previewable and downloadable.
- Any uncertain visual observation is labelled `needs review`.

## DS-02 — Temperature-monitor coding repair

### Business story

The P-101 monitoring utility subtracts vibration alarms from temperature alarms instead of reporting their combined count. Engineering needs the smallest verified correction without allowing generated code to access the network or host machine.

### Repository contents

```text
p101-temperature-monitor/
├── monitor.py
├── test_monitor.py
├── readings.csv
└── README.md
```

Planned defect in `monitor.py`:

```python
return temperature_alarms - vibration_alarms
```

Required correction:

```python
return temperature_alarms + vibration_alarms
```

Tests cover mixed alarms, temperature-only alarms, and zero alarms. The baseline must fail exactly one test; the corrected repository must pass the entire suite. Only `monitor.py` may change.

### Fixed prompt

> Fix the defect so total_alarm_count returns the sum of temperature and vibration alarms. Make the smallest safe change and run the complete pytest suite. Do not modify tests, data, or dependencies. Publish the verified patch and repository only if all tests pass.

### Ground truth

- The operator summary must add both alarm counts; it must never subtract one alarm category.
- Only `monitor.py` may change.
- Canonical patch changes `-` to `+` in one return expression.
- Baseline: one failing test and two passing tests. Final: all three tests pass with exit code 0.

### Expected product evidence

- `Automatic` workflow selects a coding-capable model without manual dropdown selection.
- Controlled network probe reports blocked before generated code executes.
- Trace shows immutable uploaded source, baseline failure, bounded patch attempt, final verification, and cleanup.
- Three artifacts are available: unified diff, verified repository ZIP, and sandbox report JSON.

## DS-03 — Mechanical-seal procurement recommendation

### Business story

Procurement must select a replacement mechanical seal for P-101. The cheapest quotation violates delivery and warranty policy, while a slightly more expensive offer satisfies every deterministic control.

### Quotation rows

| Vendor | Item | Qty | Unit price | Total | Delivery | Warranty | Declared compliance |
|---|---|---:|---:|---:|---:|---:|---|
| Aravind Industrial | API-compatible P-101 seal kit | 2 | INR 22,500 | INR 45,000 | 12 days | 24 months | Yes |
| Beacon Controls | P-101 seal kit | 2 | INR 21,000 | INR 42,000 | 20 days | 12 months | Yes |
| Crest Process Supply | Premium P-101 seal kit | 2 | INR 25,500 | INR 51,000 | 10 days | 24 months | Yes |

### Policy controls

- Maximum total budget: INR 50,000.
- Delivery must be 14 calendar days or fewer.
- Warranty must be at least 18 months.
- Currency must be INR.
- Recommendation requires human procurement-manager approval.

### Fixed prompt

> Compare all quotations against the selected procurement policy. Preserve source values, calculate totals, identify every failed control, recommend the lowest-cost fully compliant vendor, cite the policy evidence, and create a formatted comparison XLSX plus a recommendation DOCX. Treat missing data as “Not provided” and keep final approval with the procurement manager.

### Ground truth

- Aravind Industrial passes all controls and is recommended at INR 45,000.
- Beacon Controls is cheaper but fails delivery and warranty.
- Crest Process Supply fails the budget control.
- No vendor may be recommended solely because a model prefers it; deterministic policy results control the outcome.

### Expected product evidence

- Trace shows structured CSV extraction, policy evidence, deterministic calculations, local-model review, validation, and atomic publication.
- Workbook contains comparison, quotation-line, and policy-control sheets with formulas and formatting.
- DOCX contains organization branding/trademark, source-backed reasoning, control failures, and a human-approval statement.
- Both artifacts expose checksums, previews, and downloads.

## Manifest and expected-result contract

`manifest.json` should record:

- dataset name and semantic version (`presentation-v1.0.0`);
- synthetic-data declaration and owner;
- filename, MIME type, byte size, and SHA-256 for every input;
- workspace and knowledge-base destination;
- fixed prompt and workflow mode (`automatic`);
- expected route capabilities, facts, citations, validators, and artifact types;
- maximum acceptable live duration on the target M1 machine;
- known-safe fallback run ID and artifact checksums after rehearsal.

Each `expected.json` is machine-readable and should be used by smoke/evaluation scripts. Assertions should test stable facts and controls, not exact model prose.

## Fresh-organization setup

Use this order during rehearsal and on presentation day:

1. Create organization `Aegis Process Systems Pvt. Ltd.` and sign in as the demo owner.
2. Create the three workspaces named in the portfolio table.
3. Create knowledge bases `Maintenance SOPs` and `Procurement Policies`.
4. Upload and index only the two policy/SOP documents in their respective knowledge bases.
5. Upload task files to each workspace but do not run the presentation tasks yet.
6. Confirm all required local models are registered and healthy; keep workflow selection on `Automatic`.
7. Run the sovereignty probe and confirm it records blocked application-runtime egress.
8. Execute one rehearsal run per workflow and record run IDs, timings, artifact names, and checksums in the fallback record.
9. Reset the Workbench task state and leave DS-01 preselected for the live presentation.

Do not reuse a development organization containing unrelated files or audit history.

## Three-minute dataset sequence

| Time | Action | Narration/proof |
|---:|---|---|
| 0:00–0:20 | Open Sovereignty | local model health and fresh blocked-egress evidence |
| 0:20–1:25 | Run DS-01 | mixed task-scoped and indexed evidence, routing, citations, DOCX |
| 1:25–2:05 | Open rehearsed or live DS-02 | failed baseline, network denial, minimal patch, passing tests |
| 2:05–2:40 | Run/open DS-03 | policy-controlled award, formatted XLSX/DOCX |
| 2:40–3:00 | Open architecture flowchart | one reusable governed local control plane, then close |

Because M1 inference may vary, DS-01 should be the primary live run. DS-02 and DS-03 may be pre-completed in the same fresh organization and opened through their task-specific trace links. Say clearly when a run was completed during rehearsal.

## Dataset acceptance gate

All boxes must pass before recording screenshots or the backup video:

- [x] Every input is synthetic, has no personal/confidential data, and opens correctly.
- [x] `manifest.json` checksums match the checked-in files.
- [ ] Fresh-organization setup succeeds using the documented commands and UI only.
- [x] DS-01 cites the inspection report/image and at least one correct SOP page.
- [x] DS-02 baseline fails as designed; only `monitor.py` changes; final tests pass.
- [x] DS-03 produces the exact three-vendor control outcome above.
- [x] Automatic routing chooses a capable healthy local model for all three workflows.
- [ ] Trace, cancellation, retry, preview, all artifacts, and task-specific audit links work.
- [x] DOCX/XLSX files open correctly and contain the Aegis organization trademark.
- [x] Sovereignty probe is fresh and reports the observed result honestly.
- [ ] Each live run completes within its rehearsed time budget on the M1 8 GB machine.
- [x] Successful run IDs and artifact checksums are recorded for fallback.
- [ ] Screenshots and backup video show the same dataset version as the live demo.

## Failure and fallback rules

| Live issue | Presenter action |
|---|---|
| Model is cold | Explain local loading once; open the rehearsed successful run if it exceeds the scene budget |
| Vision/OCR is uncertain | Show the review flag and cited source rather than claiming certainty |
| Coding attempts are exhausted | Show the honest failed trace, then open the verified fallback run and its test evidence |
| Artifact viewer fails | Download the artifact and open the checksum-matched fallback copy |
| Service becomes unavailable | Switch to the backup recording and continue with the UML architecture PNG |

Never alter an expected answer during the live presentation, hide a failed trace, or describe a fallback run as live.

## Implementation order

1. Generate the inspection PDF, synthetic pump image, and SOP PDF.
2. Build and test the single-defect coding repository, then package its ZIP deterministically.
3. Finalize the procurement CSV and policy PDF from the accepted Day 5 fixture.
4. Add manifests, expected-result contracts, checksum generation, and validation scripts.
5. Run all three datasets in a new organization on the target M1 machine.
6. Freeze `presentation-v1.0.0`, capture screenshots, and record the backup demonstration.

After the dataset version is frozen, content changes require a version increment and a new rehearsal; replacing a file without updating its checksum is not permitted.
