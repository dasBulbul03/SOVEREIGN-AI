COMPOSE ?= $(shell if command -v docker-compose >/dev/null 2>&1; then echo docker-compose; else echo "docker compose"; fi)
DOCKER_CONFIG ?= $(CURDIR)/.docker-local
COLIMA_SOCKET := $(HOME)/.colima/default/docker.sock
USE_COLIMA ?= $(shell if command -v colima >/dev/null 2>&1 && colima status >/dev/null 2>&1; then echo 1; else echo 0; fi)
LOCAL_DOCKER_HOST := $(if $(filter 1,$(USE_COLIMA)),DOCKER_HOST=unix://$(COLIMA_SOCKET),)
DOCKER_ENV := DOCKER_CONFIG=$(DOCKER_CONFIG) $(LOCAL_DOCKER_HOST)

.PHONY: setup doctor up dev down restart status logs migrate test check backend-dev frontend-dev ollama-serve ollama-models

setup:
	test -f .env || cp .env.example .env
	npm install
	cd backend && uv sync --dev

doctor:
	@command -v node >/dev/null || (echo "Missing Node.js 22+" && exit 1)
	@node -e 'if (Number(process.versions.node.split(".")[0]) < 22) process.exit(1)' || (echo "Node.js 22+ is required" && exit 1)
	@command -v npm >/dev/null || (echo "Missing npm" && exit 1)
	@command -v uv >/dev/null || (echo "Missing uv" && exit 1)
	@command -v ollama >/dev/null || (echo "Missing Ollama" && exit 1)
	@command -v docker >/dev/null || (echo "Missing Docker CLI" && exit 1)
	@$(COMPOSE) version >/dev/null || (echo "Missing Docker Compose" && exit 1)
	@echo "Required development tools are installed."

up:
	$(DOCKER_ENV) $(COMPOSE) up --build -d

# Run stateful services and the API in Docker, while Next.js runs locally with
# Fast Refresh. Keep this command in the foreground and press Ctrl-C to stop
# Next.js; run `make down` when the supporting containers are no longer needed.
dev:
	$(DOCKER_ENV) $(COMPOSE) stop frontend
	$(DOCKER_ENV) $(COMPOSE) up --build -d postgres qdrant api-worker
	NEXT_PUBLIC_API_URL=$${NEXT_PUBLIC_API_URL:-http://localhost:8000/api/v1} npm run dev --workspace=@sovereignforge/frontend

down:
	$(DOCKER_ENV) $(COMPOSE) down

restart:
	$(DOCKER_ENV) $(COMPOSE) restart

status:
	$(DOCKER_ENV) $(COMPOSE) ps

logs:
	$(DOCKER_ENV) $(COMPOSE) logs -f --tail=200

migrate:
	$(DOCKER_ENV) $(COMPOSE) run --rm api-worker alembic upgrade head

test:
	npm run test

check:
	npm run check

backend-dev:
	npm run dev --workspace=@sovereignforge/backend

frontend-dev:
	npm run dev --workspace=@sovereignforge/frontend

ollama-serve:
	OLLAMA_NO_CLOUD=1 OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KEEP_ALIVE=2m ollama serve

ollama-models:
	ollama pull qwen3:1.7b
	ollama pull qwen2.5-coder:1.5b
	ollama pull nomic-embed-text
	ollama pull gemma3:4b
