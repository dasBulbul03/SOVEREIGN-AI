# Day 4 Developer Notes

## Start

```bash
make ollama-serve   # terminal 1, omit when Ollama is already running
make up             # terminal 2
make status
```

Compose builds the sandbox runtime/controller and applies migration `20260913_0006` automatically.

## Coding smoke test

Use `demo/day4-coding/day4-broken-repository.zip` in Workbench, select **Coding agent** and `pytest -q`, then request the smallest fix for the failing `add` tests. A successful run publishes three artifacts.

For one standalone Python source file with no `test_*.py` or `*_test.py` suite, the runtime automatically executes the program and records that decision in the trace. Source stays mounted read-only, while the process runs from an ephemeral writable `/tmp` directory so normal runtime outputs do not mutate the repository. Multiple source files without tests fall back to a read-only syntax check.

The local 1.5B coder receives numbered source and returns validated line-range edits. Each candidate passes a read-only syntax gate before the selected verification command; syntax-breaking candidates are rolled back. Runtime tracebacks are condensed to the final repository frame while raw output remains in the audit record.

For a file with many independent defects, include focused tests or route to a stronger registered coding model. The 1.5B default may safely exhaust its correction budget before completing a large semantic repair.

## Quality checks

```bash
cd backend
.venv/bin/pytest -q
.venv/bin/ruff check app tests ../sandbox-runner ../sandbox-image
.venv/bin/mypy --strict app

cd ../frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

Do not run unscoped `pytest` from the repository root: `demo/day4-coding` is intentionally broken input and is expected to fail before the agent repairs its working copy.

## Sandbox invariants

- Never add a general shell command to the public task contract.
- The API must not receive the Docker socket.
- Test files, deletes, renames, symlinks, traversal, and ambiguous patch context remain denied.
- Generated code runs only in the ephemeral runtime container with network disabled.
- Publish artifacts only after the selected fixed command exits successfully.
- Preserve the original upload and remove the run working directory/container/volume in all terminal paths.

See [Day 4 Build Record](../24-day-4-build-record.md) for design and acceptance evidence.
