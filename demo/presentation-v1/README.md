# Aegis Process Systems Presentation Dataset

Version: `presentation-v1.0.0`

This directory contains a synthetic, distributable, deterministic demonstration corpus for the three SovereignForge workflows. No file contains real personal, commercial, or operational data.

## Demo order

1. `01-inspection`: upload the report and image to workspace `01 Pump Inspection`; upload and index the SOP in knowledge base `Maintenance SOPs`.
2. `02-coding`: upload `p101-temperature-monitor.zip` to workspace `02 Controller Fix` and use the fixed prompt with automatic routing and `pytest` verification.
3. `03-procurement`: upload the CSV and policy to workspace `03 Pump Procurement` and use the fixed prompt with automatic routing.

Run `backend/.venv/bin/python demo/presentation-v1/build_dataset.py` from the repository root after any source change. The builder regenerates the PDFs, deterministic ZIP, and checksum manifest. Successful live-system DOCX/XLSX downloads belong in `output/`; QA renders belong in `qa/` and are not presentation inputs.

Run the complete live acceptance suite with a dedicated local demo account:

```bash
PRESENTATION_DEMO_EMAIL='presentation-v1@sovereignforge.local' \
PRESENTATION_DEMO_PASSWORD='<local-demo-password>' \
backend/.venv/bin/python demo/presentation-v1/run_acceptance.py
```

During document-layout iteration, run only the procurement gate by adding `PRESENTATION_DEMO_SCENARIOS=procurement`. The password is required at runtime and is never stored in this dataset.

See `docs/28-presentation-demo-datasets-plan.md` for ground truth, timings, acceptance gates, and fallback rules.
