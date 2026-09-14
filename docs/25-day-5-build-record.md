# Day 5 Build Record — Multimodal Procurement

Status: complete on 2026-09-14

## Outcome

Day 5 adds a governed multimodal evidence stage and a complete procurement
decision-support workflow. Workbench can combine uploaded quotation CSV files,
policy documents, indexed knowledge, images, and scanned PDF pages. It publishes
a formula-backed comparison workbook and a formatted recommendation document only
after deterministic validation.

## End-to-end flow

User → Workbench → task validation and routing → OCR and local vision analysis →
normalized evidence merge → quotation and policy validation → deterministic
comparison → bounded local-model review → validated XLSX and DOCX → trace and
downloads.

## Implemented controls

- Explicit procurement task mode and deterministic procurement-agent routing.
- CSV quotation contract with required vendor, item, quantity, and unit-price
  fields plus optional currency, delivery, warranty, and declared compliance.
- Extracted maximum-budget, delivery, warranty, and currency policy controls.
- Deterministic totals and compliance evaluation; the language model cannot
  override the calculated award candidate.
- Local Gemma 3 vision preprocessing for images and OCR-triggered PDF pages.
- Page-bounded visual analysis with image pixel, PDF page, task time, and output
  controls.
- Explicit OCR-only trace warning when no registered vision model is healthy.
- Normalized page representation that merges OCR text and visual descriptions
  before direct reading or temporary RAG.
- Branded DOCX recommendation with native tables, evidence, approval controls,
  and organization trademark.
- Branded XLSX with recommendation, quotation-line, and policy-control sheets;
  formulas, filters, frozen headers, number formatting, and structural validation.
- Atomic artifact-set behavior: partial generated files are rolled back if the
  complete pair cannot be validated.
- Immutable artifact metadata, SHA-256 checksums, organization-scoped downloads,
  citations, and persistent trace events.

## Acceptance fixture

Use the versioned inputs under demo/day5-procurement/.

Expected decision:

- Aravind Industrial: INR 45,000, 12-day lead time, 24-month warranty, pass.
- Beacon Controls: INR 42,000, 20-day lead time, 12-month warranty, review.
- Recommendation: Aravind Industrial, subject to human approval.

## Automated evidence

- Backend tests cover deterministic comparison, malformed quotation rejection,
  multimodal image transport, normalized vision evidence, workbook formulas,
  workbook structure, DOCX branding, and DOCX tables.
- Strict mypy and Ruff cover backend application, migrations, and tests.
- Frontend ESLint, TypeScript, Vitest, and production build cover the Workbench
  workflow contract.
- The complete repository gate passed with 53 backend tests and one frontend
  test, plus strict mypy, Ruff, ESLint, TypeScript, and production builds.

## Live acceptance evidence

The deployed procurement run 9a263bea-b295-42d5-8bf3-8a39625f7853
completed in seven persisted steps with zero retries:

- deterministic route: qwen3:1.7b with procurement_agent;
- result: Aravind Industrial passed at INR 45,000;
- result: Beacon Controls was flagged for 20-day delivery and 12-month warranty;
- approval control: recommendation remains subject to human review;
- artifacts: valid XLSX and valid DOCX with matching downloaded SHA-256 values;
- workbook inspection: three required sheets and the first line-total formula;
- DOCX inspection: five required sections, one native comparison table, and the
  organization trademark.

The deployed image run 80bbf24c-4129-4937-9d19-dadb22854630 also completed:

- one PNG page passed through local gemma3:4b vision analysis;
- OCR and visual context merged into one page-scoped S1 source;
- the trace recorded one candidate page, one vision page, one OCR page, and no
  fallback warnings;
- a validated cited DOCX was published;
- a routing guard now reserves vision models for visual preprocessing, so Gemma
  remains enabled without displacing qwen3:1.7b for normal reasoning tasks.

## Known limits

- Structured procurement comparison requires CSV quotation rows. PDF/image quote
  content is available as cited evidence and review context, but automatic table
  reconstruction from arbitrary layouts remains a human-review boundary.
- Vision work is capped per task for the 8 GB Apple Silicon profile; remaining
  scanned pages use OCR and the trace records the fallback.
- Taxes, currency conversion, vendor eligibility, signatures, and commercial
  terms require responsible human verification before purchase commitment.
