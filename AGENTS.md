# AGENTS.md

Working notes for this repo. `README.md` explains the why; this is the what and
the how.

## Commands

```sh
make dev            # .venv with pinned ruff/pytest/uv, plus `uv sync` for apps/api
make lint           # ruff check + ruff format --check (both apps), then pyright (api)
make typecheck      # pyright on apps/api alone
make test           # pytest per app; api runs in its uv environment
make format         # ruff check --fix + ruff format
make docker-build   # linux/amd64 images, tag `dev`
```

`make lint` **and** `make test` must pass before a commit. A task is not done
until they do.

Inside `apps/api`, work through uv:

```sh
uv run pytest
uv run pytest -m integration        # needs TEST_DATABASE_URL
uv run ruff check .
uv run pyright
uv run uvicorn api.main:app --port 8080
uv run python -m api.migrate        # upgrade to head; needs DATABASE_URL
uv run python -m api.seed           # idempotent
```

## Layout

Two independent deployables under `apps/`, each with its own `pyproject.toml`
and `Dockerfile`. There is no root project, deliberately: a shared one would
couple their dependency sets.

- `apps/api` — FastAPI + SQLAlchemy async + asyncpg + Alembic + OTel. A uv
  project with a committed `uv.lock`. See `apps/api/README.md`.
- `apps/mcp-server` — stdlib-only stand-in. Leave it alone until the real
  streamable-HTTP server is written.

Infrastructure lives in a separate repo. The only thing that crosses the
boundary is an image reference — do not add Kubernetes manifests here.

## Conventions

**Dependencies.** `apps/api` uses uv: compatible ranges in `pyproject.toml`,
exact versions in `uv.lock`, which is committed and installed with `--frozen`.
Never hand-edit the lock; run `uv lock`. Verify a version against PyPI before
pinning it rather than trusting memory. The uv pin in `requirements-dev.txt`,
the `version:` input in `ci.yml` and the `UV_VERSION` build arg in
`apps/api/Dockerfile` are the same number and move together.

**Types.** `pyright` gates `apps/api`. Type hints everywhere; `dataclasses` or
pydantic models over raw dicts.

**Style.** ruff, line length 100, `E,F,I,B,UP,N,SIM`. Readability over
brevity. Small, single-purpose functions. `pathlib`, no global state.

**Logging.** JSON on stdout, stdlib only. Minimal and operational — the access
middleware plus genuine events, nothing chatty.

**Config.** Environment variables only, through pydantic-settings, validated at
import so a bad value fails at startup instead of at first use.

**Tests.** Unit tests must run with no database and no network; that is what
the repository protocol in `apps/api/src/api/repository.py` is for. Anything
needing real Postgres is marked `integration` and skipped unless
`TEST_DATABASE_URL` is set.

**Workflows.** Every third-party action is pinned to a full commit SHA with a
`# vX.Y.Z` comment — resolve with `git ls-remote --tags <url>`, taking the
peeled `^{}` entry for annotated tags. Least-privilege `permissions:` on every
workflow; `persist-credentials: false` on every checkout. `zizmor` audits the
workflows and must stay clean.

**Images.** Base images pinned by digest, not tag. Non-root, `readOnlyRootFilesystem`
-compatible: the runtime writes nothing to disk.

**Commits.** Conventional Commits (`feat:`, `fix:`, `refactor:`, `chore:`,
`docs:`, `test:`, `ci:`, `perf:`), one or two lines. No AI attribution or
`Co-Authored-By` trailers.

**Naming.** No client or employer names anywhere in this repo — not in code,
comments, commit messages or docs.
