# M5 16 GB Setup and Run Guide

Status: operator profile for a second Apple Silicon Mac  
Target machine: Apple M5, 16 GB unified memory, 512 GB SSD  
Recommended models: `qwen3:4b`, `qwen2.5-coder:3b`, and `nomic-embed-text`

## Profile goals

This profile favors responsive local use and safe memory headroom for macOS, Ollama, Docker, PostgreSQL, Qdrant, the API, frontend, and sandbox services. It does not promise ten simultaneous model generations. The current governed worker executes one run at a time; ten users can submit work only through queueing until the scaling plan is implemented.

The recommended M5 models are larger than the M1 demo defaults:

| Role | M1 compatibility model | M5 16 GB preferred model | Approximate Ollama download |
|---|---|---|---:|
| General reasoning | `qwen3:1.7b` | `qwen3:4b` | 2.5 GB |
| Coding | `qwen2.5-coder:1.5b` | `qwen2.5-coder:3b` | 1.9 GB |
| Embeddings | `nomic-embed-text` | `nomic-embed-text` | 274 MB |

Keep `OLLAMA_MAX_LOADED_MODELS=1` and `OLLAMA_NUM_PARALLEL=1` initially. A larger model or higher concurrency must be justified by measurements, not only by successful model loading.

## Before starting

Confirm that the machine is using native Apple Silicon tools rather than Rosetta:

```bash
uname -m
arch
```

Both commands should report `arm64`.

Check the macOS version and available disk:

```bash
sw_vers
df -h /
```

Keep at least 50 GB free for Docker images, model downloads, application data, build caches, and temporary artifacts. The 512 GB SSD is sufficient for this profile, but SSD space does not replace unified memory.

## First-time installation

### 1. Install host tools

Install Homebrew first if it is not already available. Then run:

```bash
brew update
brew install node@22 uv ollama colima docker docker-compose docker-buildx
brew link --overwrite --force node@22
```

Verify every required tool:

```bash
node --version
npm --version
uv --version
ollama --version
colima version
docker --version
docker-compose version
```

Node.js must be version 22 or newer.

### 2. Clone the exact project revision

```bash
git clone <repository-url> ai-agentic-flow
cd ai-agentic-flow
git branch --show-current
git rev-parse HEAD
git status --short
```

Compare `git rev-parse HEAD` with the source machine. A Git clone does not include uncommitted files from the source machine. Commit and push required work before expecting the second machine to contain it.

### 3. Start Colima

For this 16 GB profile, reserve four CPU cores and 4 GB memory for containers, leaving most unified memory available to macOS and native Ollama:

```bash
colima start --cpu 4 --memory 4 --disk 40
colima status
docker info
```

Do not run Docker Desktop and Colima simultaneously. If Docker Desktop is preferred, start it instead and wait for its engine to become ready.

### 4. Install repository dependencies

From the repository root:

```bash
make doctor
make setup
```

Confirm that `.env` now exists:

```bash
test -f .env && echo '.env is ready'
```

Do not copy another machine's `.env` blindly and do not commit it.

### 5. Start Ollama

In terminal 1, from the repository root:

```bash
OLLAMA_CONTEXT_LENGTH=8192 make ollama-serve
```

Leave this terminal running. The Make target already restricts Ollama to one parallel request, one loaded model, a two-minute keep-alive, and disabled cloud features.

If the Ollama macOS application already owns port `11434`, do not start another server. Verify the existing process instead:

```bash
curl http://localhost:11434/api/tags
```

### 6. Download the compatibility and M5 models

In terminal 2, from the repository root, first download the three models seeded by the current database migration:

```bash
make ollama-models
```

Then download the preferred M5 models:

```bash
ollama pull qwen3:4b
ollama pull qwen2.5-coder:3b
ollama list
```

  ollama pull llama3.2:3b
  ollama pull gemma3:4b
  ollama pull mistral:7b-instruct
  ollama list

## Test each model directly

  Before registering it in the project:

  ollama run llama3.2:3b "Reply with exactly: MODEL READY"
  ollama run gemma3:4b "Reply with exactly: MODEL READY"
  ollama run mistral:7b-instruct "Reply with exactly: MODEL READY"

  Check which model is loaded:

llama ps

  Because this project starts Ollama with OLLAMA_MAX_LOADED_MODELS=1, Ollama unloads the previous model when another model needs the memory. All three can remain stored on disk
  without remaining loaded simultaneously.    

Expected model keys include:

```text
qwen3:1.7b
qwen2.5-coder:1.5b
nomic-embed-text
qwen3:4b
qwen2.5-coder:3b
```

Keeping the smaller seeded models costs additional disk space but provides fallback compatibility and lets every seeded registry entry report ready. It does not mean that all models remain loaded in memory.

### 7. Start the application

Still in terminal 2:

```bash
ENV_FILE=.env make up
make status
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/readiness
```

The readiness response should report PostgreSQL, Qdrant, and Ollama as ready.

Open:

- Application: <http://localhost:3000>
- Models: <http://localhost:3000/models>
- Workbench: <http://localhost:3000/workbench>
- API documentation: <http://localhost:8000/docs>

### 8. Register the preferred M5 models

Sign in as the organization owner and open the Models screen. Register these two already-downloaded Ollama models:

#### General model

| Field | Value |
|---|---|
| Display name | `General M5 4B` |
| Ollama model key | `qwen3:4b` |
| Capabilities | `text,reasoning,general` |
| Context window | `8192` |
| Quantization | `ollama-default` |
| Priority | `200` |

#### Coding model

| Field | Value |
|---|---|
| Display name | `Coder M5 3B` |
| Ollama model key | `qwen2.5-coder:3b` |
| Capabilities | `text,coding` |
| Context window | `8192` |
| Quantization | `ollama-default` |
| Priority | `190` |

The higher priorities make the capability router prefer the M5 models over the seeded M1 compatibility models. Registration does not download a model; the `ollama pull` commands must succeed first.

The registry context value is routing metadata. The `OLLAMA_CONTEXT_LENGTH=8192` setting controls the host Ollama default for this startup profile.

Run **Check readiness** for every model that still displays `unknown`. Expected final state: all installed and registered models report `ready`.

### 9. Verify inference and memory behavior

Run one simple task in the Workbench. While it is executing, inspect Ollama in terminal 2:

```bash
ollama ps
```

Confirm:

- only one model is loaded at a time;
- the model uses the Apple GPU/Metal path rather than an unintended CPU-only path;
- macOS does not enter sustained memory pressure or heavy swap;
- the task reaches a terminal state without an Ollama timeout.

Use Activity Monitor's Memory tab during the first long task. Green memory pressure is the desired operating condition. A model merely loading successfully is not sufficient if it causes persistent swapping.

### 10. Run repository checks

```bash
make check
npm run build
```

Then run the documented knowledge and governed-agent smoke tests from [`19-setup-and-run-guide.md`](19-setup-and-run-guide.md).

## Normal daily startup

### Terminal 1

```bash
colima start
cd <path-to>/ai-agentic-flow
OLLAMA_CONTEXT_LENGTH=8192 make ollama-serve
```

Skip `make ollama-serve` if an existing Ollama application is already responding on port `11434`.

### Terminal 2

```bash
cd <path-to>/ai-agentic-flow
ENV_FILE=.env make up
make status
curl http://localhost:8000/api/v1/readiness
```

Open <http://localhost:3000>.

## Normal shutdown

Stop application containers without deleting data:

```bash
make down
```

Stop the foreground Ollama server with `Control-C`. Optionally release Colima resources:

```bash
colima stop
```

Never add `-v` to the Compose shutdown command unless permanent database, Qdrant, and uploaded-file deletion is explicitly intended.

## Optional quality upgrade after benchmarking

On a 16 GB M5, `qwen3:8b` and `qwen2.5-coder:7b` can be evaluated one at a time, but they are not the default ten-user profile:

```bash
ollama pull qwen3:8b
ollama pull qwen2.5-coder:7b
```

Before registering them, compare the 4B/3B and 8B/7B profiles using the same prompts and output limits. Record:

- cold and warm time to first response;
- total task duration;
- output tokens per second;
- peak memory and swap;
- model-switch delay;
- queue delay for several submitted tasks;
- answer and artifact quality on the fixed evaluation dataset.

Prefer the larger models only when their quality improvement outweighs lower throughput and longer queue time. Do not attempt a 14B default model on this 16 GB application host without a separate capacity test.

## Troubleshooting

### Models remain unknown

Open the Models screen and select **Check readiness** for each model. `unknown` means no model-health observation has been recorded yet.

### A model reports unavailable

```bash
curl http://localhost:11434/api/tags
ollama list
curl http://localhost:8000/api/v1/readiness
```

The registry key must exactly match an installed Ollama key.

### Ollama is ready on the host but unavailable to the API

```bash
make logs
make down
ENV_FILE=.env make up
curl http://localhost:8000/api/v1/readiness
```

The container reaches native Ollama through `http://host.docker.internal:11434`.

### Memory pressure or swapping

```bash
ollama ps
make status
```

Then:

1. confirm only one Ollama server is running;
2. keep `OLLAMA_MAX_LOADED_MODELS=1` and parallelism at one;
3. stop other model-heavy applications;
4. return to the 4B/3B profile if testing 8B/7B;
5. reduce context length if long prompts cause KV-cache pressure;
6. keep Colima at 4 GB unless container metrics prove it needs more.

### Ten users submit tasks together

The current application accepts task records but executes governed runs serially. Later tasks may wait long enough to approach their deadline. Use the system as a queued pilot, not as ten simultaneous inference slots. Follow [`23-scaling-and-capacity-plan.md`](23-scaling-and-capacity-plan.md) before presenting a ten-user concurrency claim.

## Completion checklist

- [ ] Native architecture reports `arm64`.
- [ ] Colima or Docker Desktop is ready, but not both.
- [ ] Ollama responds on port `11434`.
- [ ] All five compatibility/preferred models appear in `ollama list`.
- [ ] PostgreSQL, Qdrant, and Ollama report ready through the API.
- [ ] The 4B general and 3B coder models are registered with higher routing priorities.
- [ ] Model health checks report ready.
- [ ] A Workbench task selects the intended M5 model.
- [ ] `ollama ps` shows one loaded model and Metal acceleration.
- [ ] Memory pressure remains acceptable during a representative task.
- [ ] Repository checks and smoke tests pass.
- [ ] The exact Git commit and measured results are recorded before declaring the machine ready.
