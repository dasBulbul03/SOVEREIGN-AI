# Successful system outputs

This folder receives artifacts downloaded from completed, validated application runs against `presentation-v1.0.0`.

Files must not be placed here merely because they were generated. The acceptance runner records the owning task/run ID, application checksum, downloaded checksum, validation status, and dataset version in `acceptance-results.json`. Word artifacts are rendered into `../qa/` and visually inspected before the dataset is declared presentation-ready.

Accepted presentation artifacts:

- `inspection-approval-recommendation-5411471a.docx`
- `procurement-procurement-comparison-7f567ba1.xlsx`
- `procurement-procurement-recommendation-7f567ba1.docx`

`procurement-layout-acceptance.json` records the focused final layout run. Superseded artifacts that failed content or visual QA were moved to ignored folders below `../qa/`; they are not successful presentation outputs.
