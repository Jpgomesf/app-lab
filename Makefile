APPS      := api mcp-server
APP_DIRS  := $(addprefix apps/,$(APPS))
IMAGE_TAG ?= dev

# Prefer the repo-local venv (`make dev`) so the pre-commit hook and a bare
# shell behave the same; fall back to whatever python3 is on PATH.
VENV_PY := $(CURDIR)/.venv/bin/python
PY      := $(if $(wildcard $(VENV_PY)),$(VENV_PY),python3)

.PHONY: dev lint format test docker-build

dev:
	python3 -m venv .venv
	$(VENV_PY) -m pip install --quiet --upgrade pip
	$(VENV_PY) -m pip install --quiet -r requirements-dev.txt
	@echo "dev env ready: .venv"

lint:
	$(PY) -m ruff check $(APP_DIRS)
	$(PY) -m ruff format --check $(APP_DIRS)
	@echo "lint OK"

format:
	$(PY) -m ruff check --fix $(APP_DIRS)
	$(PY) -m ruff format $(APP_DIRS)

test:
	@set -e; for app in $(APPS); do \
		echo "==> apps/$$app"; \
		( cd apps/$$app && $(PY) -m pytest ); \
	done

# amd64 only: cloud nodes are x86, and a same-arch image is what ships.
docker-build:
	@set -e; for app in $(APPS); do \
		echo "==> apps/$$app"; \
		docker buildx build --platform linux/amd64 --load \
			-t app-lab/$$app:$(IMAGE_TAG) apps/$$app; \
	done
