# Deployment and Operations Plan

## Local service topology

| Service | Purpose | Exposure |
|---|---|---|
| `frontend` | Next.js workbench | localhost only |
| `api-worker` | FastAPI plus prototype background worker | localhost API; private dependencies |
| `postgres` | durable metadata/state/audit | private network only |
| `qdrant` | vector index | private network only |
| native `ollama` | local generation/vision/embeddings with Apple Metal | localhost; API reaches host gateway |
| `sandbox-controller` | starts constrained ephemeral runners | private; no public port |

Do not mount the Docker socket into the general API container. If the prototype controller requires Docker access, isolate it behind a narrow request contract and document this as a high-risk production gap. Native Ollama must start with cloud features disabled, one loaded model and one parallel request on the M1 8 GB profile.

## Configuration groups

- Application: environment, base URL, data root, log level, correlation settings.
- Database/vector: internal URLs, credentials, collection prefix.
- Models: provider endpoint, model keys, capabilities, context, priorities, health TTL.
- Agent: maximum 12 steps, 3 recoverable retries, 180-second run timeout, 60-second tool timeout.
- Upload/document: byte/page/pixel/text limits, MIME allowlist, OCR thresholds.
- Sandbox: image digest, CPU/memory/PID/time/output limits and executable allowlist.
- Security: allowed origins, redaction, internal network/probe expectations.

Commit safe defaults in `.env.example`; never commit secrets or host-specific absolute paths.

## Startup runbook

1. Confirm Docker, disk space, memory/VRAM and preloaded model availability.
2. Validate configuration and bound ports.
3. Start data/model services; wait for health.
4. Run database migrations exactly once.
5. Start API/worker and frontend.
6. Run application, database, Qdrant, model and sandbox smoke checks.
7. Seed versioned demo workspace only when explicitly requested.
8. Switch to offline/restricted network state and run sovereignty verification.

The repository implementation should provide scripts/commands for these operations; this document specifies their behavior without inventing command names before code exists.

## Health model

- **Liveness**: process responds and event loop is functioning.
- **Readiness**: required dependencies for its role are available.
- **Capability health**: individual model/OCR/sandbox capability status may be degraded.

The overall application can be `degraded` while allowing unaffected metadata views. Starting a workflow with unavailable mandatory capabilities must be blocked with an actionable message.

## Observability

### Structured logs

Fields: timestamp, severity, service, environment, correlation ID, workspace/run IDs when safe, event/error code, duration and bounded metadata. Exclude prompt bodies, source text, embeddings, credentials, raw tool stdout and full host paths.

### Metrics

- API count/error/latency by route class.
- queued/running/terminal tasks and run duration.
- model health, request count, first-token/total latency when available.
- tool count/failure/timeout and sandbox limit termination.
- ingestion pages/chunks/duration and retrieval latency.
- artifact success/validation failures.
- sovereignty probe result/age and denied tool actions.

### Alerts for prototype

Visible UI/operator warnings are sufficient: required model unavailable, database/vector unhealthy, disk space critical, stale sovereignty probe, sandbox not enforcing network mode, repeated workflow failures.

## Recovery

- API restart: queued runs remain; formerly running runs become `interrupted` and require safe retry.
- Model restart: health changes to unavailable; new runs queue/fail/fallback based on policy.
- Qdrant loss: relational provenance remains, but search is unavailable; rebuild from normalized pages.
- PostgreSQL loss: restore from backup; it is the authoritative state.
- Artifact/file loss: report checksum/path inconsistency; do not silently regenerate under the same artifact ID.

## Backup and demo resilience

Before final demo, save version-pinned images, model weights/cache, dependency caches, database dump, Qdrant snapshot or reproducible index inputs, demo files, expected artifacts and a screen recording. Verify restoration to a separate temporary environment. Keep a pre-warmed but honest demo state and also prove a cold start during rehearsal.

## Production hardening backlog

Separate worker queue, dedicated sandbox host/runtime, TLS and reverse proxy, OIDC/RBAC, secret manager, encrypted backups, SBOM/signatures/scanning, formal retention, high availability, capacity tests, automated restore drills, centralized metrics/logs and incident response.
