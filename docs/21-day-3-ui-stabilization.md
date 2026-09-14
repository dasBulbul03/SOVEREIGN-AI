# Day 3 UI and Control Stabilization

Date: 2026-09-13  
Hardware: MacBook Air, Apple M1, 8 GB unified memory  
Status: implemented, tested, and verified in the running application

## Decision

The reported controls were visible product promises, so they were treated as current stabilization work instead of being left as dead UI until later milestones. Items 1–9, 13, and 14 close Day 3 integration gaps. Items 10–12 pull small, safe prototype slices forward from later registry, security, and account-management work. Day 4 remains the coding-sandbox milestone.

## Resolution matrix

| # | Reported gap | Implemented contract |
|---:|---|---|
| 1 | File X did not delete | Confirmed organization-scoped soft removal, hidden from subsequent lists, rejected by new tasks/tools, with `FILE_REMOVED` audit evidence |
| 2 | Drop zone was decorative | Native browser file-drop events now use the same validated upload API as the picker |
| 3 | Three shown, all submitted | The complete scrollable list is shown; an explicit checkbox set is the only file set submitted, with a master Select all/deselect all control |
| 4 | New task retained files | New task clears selected files, selected knowledge bases, active run, prompt, and mutation state |
| 5 | Trace ignored `?task=` | The server page passes the task parameter into Trace; selecting another run also updates the URL |
| 6 | Collection buttons did not filter | All, Indexed, and Not indexed filter the document table using API-derived index membership |
| 7 | Library dropdown did nothing | Workspace and knowledge-library selectors now change the active API context |
| 8 | Top search did not submit | Toolbar search is a real form using the selected library's search endpoint |
| 9 | First workspace/base only | Workspace selection is available in Workbench and Knowledge; Workbench supports multiple ready knowledge-base selections; a browser-local default workspace can be saved |
| 10 | Model registration unavailable | Owner-only model registration API and form persist Ollama metadata, reject duplicate keys, and immediately record a health check |
| 11 | Egress testing unavailable | Authenticated controlled HTTPS probe reports `blocked` or `egress_detected` with target, latency, and plain-language evidence |
| 12 | Profile/security unavailable | Profile update, default-workspace preference, session listing, and confirmed session revocation are available under `/settings` |
| 13 | First artifact only | Workbench renders and downloads every artifact in the latest run |
| 14 | Router was illustrative | Models shows the latest persisted task classification, capabilities, candidate evaluation, selection reason, and selected model |

## Important behavior

- File removal is deliberately a soft delete in this prototype. It preserves immutable task/audit provenance and does not expose the file to new lists, task submissions, ingestion jobs, or file tools. A later retention-policy job can perform physical erasure and vector cleanup.
- The egress probe is evidence, not a green status button. The 2026-09-13 live check returned **egress detected** because the current `app_net` permits outbound HTTPS. Network hardening and a passing blocked-egress test remain part of Day 6.
- Model registration does not download an Ollama model. Register an already-installed local model key; readiness accurately reports unavailable when Ollama does not have it.
- The default workspace is a browser preference. API authorization remains organization-scoped and does not trust that preference.

## Verification evidence

- Backend: Ruff passed, strict mypy passed, and 13 tests passed.
- Frontend: TypeScript passed, ESLint passed, and the Next.js production build generated all 13 routes.
- Compose rebuilt successfully on the M1/8 GB profile; PostgreSQL and Qdrant were healthy and the API/frontend started.
- Playwright verified a real file drop, `1 OF 1 SELECTED`, New task changing it to `0 OF 1 SELECTED`, and confirmed removal of only the temporary upload.
- Playwright verified the registration form, the persisted three-candidate routing decision, `?task=` trace selection, profile/session settings, and the controlled egress response.

## Remaining milestone scope

These fixes do not replace Day 4–7 work. The next build milestone is still Day 4: hardened coding sandbox, repository tools, bounded patch/test execution, and negative isolation tests. Day 6 still owns container-level egress enforcement, broader accessibility/UX polish, regression hardening, and release security evidence.
