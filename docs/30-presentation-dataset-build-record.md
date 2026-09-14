# Presentation Dataset Build Record

Status: accepted for rehearsal  
Dataset: `presentation-v1.0.0`  
Target machine: MacBook Air M1, 8 GB unified memory

## Delivered corpus

The synthetic dataset is stored in `demo/presentation-v1/`. Its deterministic builder creates two inspection PDFs, one synthetic inspection image, a deliberately failing Python repository ZIP, a quotation CSV, a procurement-policy PDF, fixed prompts, expected-result contracts, and a SHA-256 manifest.

The pump image is synthetic demonstration evidence generated for this project. It depicts a blue centrifugal pump, an intact yellow coupling guard, and visible seal-area leakage; it contains no embedded conclusion, logo, watermark, or real facility data.

## Accepted live runs

| Scenario | Task type | Selected local model | Task ID | Run ID | Result |
|---|---|---|---|---|---|
| Pump inspection | `rag` | `qwen3:1.7b` | `52e36181-26e3-4e5d-8386-08ac06dc818e` | `5411471a-83ff-4e85-8308-1db966cc81d5` | Passed; eight trace steps and one DOCX |
| Controller repair | `coding` | `qwen2.5-coder:1.5b` | `8f3c39dc-a178-471a-8d51-00776f3f98c9` | `75610c80-4c2c-4ade-baac-a69fed21cf8c` | Passed; eleven trace steps and three governed artifacts |
| Seal procurement | `procurement` | `qwen3:1.7b` | `6328e121-c881-490d-aa34-b4fc163cfca8` | `7f567ba1-a71c-47d7-b21e-3bcd6e66a2fd` | Passed; seven trace steps and two Office artifacts |

All four registered models reported `ready`. The application-runtime sovereignty probe reported outbound access `blocked`, with enforcement `configured` and probe version `day6-v1`.

## Accepted Office outputs

| File | SHA-256 | Validation |
|---|---|---|
| `inspection-approval-recommendation-5411471a.docx` | `a03796cc6febf990c2839ccbf3a385dc430ee5ed56dfe5529fcb62dc43be00ad` | Application checksum/structure passed; both rendered pages visually inspected |
| `procurement-procurement-comparison-7f567ba1.xlsx` | `d8c7fdd67a27ae6bcb9e6772d7a7576029ad8e59cdc816a56ca483b9f689a6d0` | Application checksum, sheet, recommendation, and formula checks passed |
| `procurement-procurement-recommendation-7f567ba1.docx` | `bd278a4c02eca4a97c7654b2f18656a42d3e781270322be58c4959b4ac948e56` | Application checksum/structure passed; final one-page render visually inspected |

The spreadsheet contains `Recommendation`, `Quotation Lines`, and `Policy Controls`; the first quotation line retains its `=C5*D5` formula. The recommendation is Aravind Industrial. The spreadsheet artifact renderer was unavailable in this workspace, so XLSX visual rendering remains a presentation-machine spot check; structural and formula validation passed.

## Corrections found by acceptance testing

- Repository ZIP ingestion now accepts CSV test fixtures while restricting implementation changes to source-code suffixes.
- The coding fixture uses one deterministic alarm-count defect: one baseline failure, two baseline passes, then three final passes after a one-line source fix.
- Procurement policy text uses deterministic control labels so budget, currency, lead-time, and warranty rules are extracted consistently.
- The procurement Word report uses renderer-safe vendor cards instead of a fragile wide table, includes Aegis branding/trademark, and preserves human approval controls.
- The dataset builder uses reproducible PDF settings and fixed ZIP timestamps/member ordering.

## Commands

From the repository root:

```bash
backend/.venv/bin/python demo/presentation-v1/build_dataset.py

PRESENTATION_DEMO_EMAIL='presentation-v1@sovereignforge.local' \
PRESENTATION_DEMO_PASSWORD='<local-demo-password>' \
backend/.venv/bin/python demo/presentation-v1/run_acceptance.py
```

For a focused procurement artifact rerun, add `PRESENTATION_DEMO_SCENARIOS=procurement`. Do not commit the demo password.

## Remaining presentation work

- Exercise the complete setup through the UI on the clean presentation account.
- Confirm cancellation, retry, preview, and task-specific audit links in that UI rehearsal.
- Open the accepted XLSX in Excel or Numbers for a final visual spot check.
- Record exact scene timings, screenshots, and the backup video against `presentation-v1.0.0`.

One additional cold inspection attempt immediately after a container rebuild returned the system's safe internal-error state. The earlier accepted inspection run remains the fallback evidence; presentation rehearsal should warm the models and confirm the primary live scene before recording.


###
The presentation dataset is built and tested end to end against the running system.

  - Three scenarios: inspection/RAG, governed coding repair, and procurement analysis.
  - Automatic routing selected qwen3:1.7b and qwen2.5-coder:1.5b.
  - All four local models reported healthy.
  - Sovereignty test confirmed outbound access was blocked.
  - npm run check: 80 backend tests and frontend tests passed.
  - npm run build: production build passed.
  - Dataset regeneration is deterministic.
  - DOCX files passed structural and visual QA.
  - XLSX passed checksum, formula, sheet, branding, and recommendation validation. A final visual spot check in Excel/Numbers is recommended because the spreadsheet rendering runtime was
    unavailable.

  The synthetic pump image was generated specifically for this demo using a photorealistic industrial inspection prompt showing an intact guard and visible seal leak, without logos,
  conclusions, or real facility data.

  Documentation:

  Dataset instructions (demo/presentation-v1/README.md)

  Acceptance results (demo/presentation-v1/output/acceptance-results.json)

  Build and testing record (docs/30-presentation-dataset-build-record.md)

  Successful system-generated outputs:

  Inspection approval recommendation DOCX (demo/presentation-v1/output/inspection-approval-recommendation-5411471a.docx)

  Procurement comparison XLSX (demo/presentation-v1/output/procurement-procurement-comparison-7f567ba1.xlsx)

  Procurement recommendation DOCX (demo/presentation-v1/output/procurement-procurement-recommendation-7f567ba1.docx)

  One subsequent cold inspection attempt immediately after rebuilding containers returned a safe internal-error state. The previously accepted inspection run remains valid; warm the models
  before the presentation rehearsal.

