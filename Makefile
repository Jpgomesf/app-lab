APPS      := api mcp-server
APP_DIRS  := $(addprefix apps/,$(APPS))
IMAGE_TAG ?= dev

# Prefer the repo-local venv (`make dev`) so the pre-commit hook and a bare
# shell behave the same; fall back to whatever python3 is on PATH.
VENV_PY := $(CURDIR)/.venv/bin/python
PY      := $(if $(wildcard $(VENV_PY)),$(VENV_PY),python3)

# apps/api is a uv project with its own locked environment; apps/mcp-server is
# still stdlib-only and runs on $(PY). Prefer the pinned uv from .venv, then
# any uv on PATH, then the environment uv already built at apps/api/.venv —
# that last one keeps things working on a machine with no uv at all.
VENV_UV     := $(CURDIR)/.venv/bin/uv
UV          := $(if $(wildcard $(VENV_UV)),$(VENV_UV),$(shell command -v uv 2>/dev/null))
API_VENV    := $(CURDIR)/apps/api/.venv/bin
API_MISSING := "apps/api needs its locked deps: run 'make dev'"

.PHONY: dev lint format typecheck test docker-build

dev:
	python3 -m venv .venv
	$(VENV_PY) -m pip install --quiet --upgrade pip
	$(VENV_PY) -m pip install --quiet -r requirements-dev.txt
	$(VENV_UV) sync --frozen --project apps/api
	@echo "dev env ready: .venv + apps/api/.venv"

lint:
	$(PY) -m ruff check $(APP_DIRS)
	$(PY) -m ruff format --check $(APP_DIRS)
	@$(MAKE) --no-print-directory typecheck
	@echo "lint OK"

format:
	$(PY) -m ruff check --fix $(APP_DIRS)
	$(PY) -m ruff format $(APP_DIRS)

# pyright covers apps/api only. mcp-server is a stdlib placeholder with nothing
# worth checking; it joins when the real server lands.
typecheck:
	@set -e; \
	if [ -n "$(UV)" ]; then \
		( cd apps/api && $(UV) run --frozen pyright ); \
	elif [ -x "$(API_VENV)/pyright" ]; then \
		( cd apps/api && $(API_VENV)/pyright ); \
	else \
		echo $(API_MISSING) >&2; exit 1; \
	fi

test:
	@set -e; \
	echo "==> apps/api"; \
	if [ -n "$(UV)" ]; then \
		( cd apps/api && $(UV) run --frozen pytest ); \
	elif [ -x "$(API_VENV)/python" ]; then \
		( cd apps/api && $(API_VENV)/python -m pytest ); \
	else \
		echo $(API_MISSING) >&2; exit 1; \
	fi; \
	echo "==> apps/mcp-server"; \
	( cd apps/mcp-server && $(PY) -m pytest )

# amd64 only: cloud nodes are x86, and a same-arch image is what ships.
docker-build:
	@set -e; for app in $(APPS); do \
		echo "==> apps/$$app"; \
		docker buildx build --platform linux/amd64 --load \
			-t app-lab/$$app:$(IMAGE_TAG) apps/$$app; \
	done
