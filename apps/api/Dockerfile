# syntax=docker/dockerfile:1

# Pinned by digest, not by tag: `python:3.12-slim` moves on every patch release
# and a digest is the only way a rebuild is the same build. This is the
# manifest-list digest, so buildx still selects linux/amd64 from it.
#
# Re-resolve with:
#   docker buildx imagetools inspect python:3.12-slim --format '{{.Manifest.Digest}}'
# Renovate's dockerfile manager keeps it current.
ARG PYTHON_IMAGE=python:3.12-slim@sha256:e5c9fa26ffb76e11e0f054f30dc2523a2f9693f0c36c0cf1e39b27e152d899fc

# --------------------------------------------------------------------------
# builder: resolve dependencies from uv.lock into a self-contained venv
# --------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS builder

# Must match requirements-dev.txt: this is the uv that wrote uv.lock.
ARG UV_VERSION=0.12.9

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    # Never fetch an interpreter: the base image's 3.12 is the one that ships.
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

RUN pip install --no-cache-dir "uv==${UV_VERSION}"

WORKDIR /src

# Dependencies before source, so the expensive layer is invalidated by a lock
# change and not by every edit to a route.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY src/ ./src/
# Installs the project itself; migrations live inside the package, so they
# land in the venv with it. --no-editable is load-bearing: the default
# editable install writes a path reference to /src into the venv, and /src
# does not exist in the runtime stage — the venv must be self-contained.
RUN uv sync --frozen --no-dev --no-editable

# --------------------------------------------------------------------------
# runtime
# --------------------------------------------------------------------------
FROM ${PYTHON_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PORT=8080

# uid 65532 is what the Deployment's securityContext pins. The passwd entry is
# not required to run, but without it anything calling getpwuid() — including
# os.path.expanduser — raises instead of returning a home directory.
RUN groupadd --gid 65532 nonroot \
    && useradd --uid 65532 --gid 65532 --home-dir /home/nonroot --create-home nonroot

COPY --from=builder /opt/venv /opt/venv

USER 65532:65532
WORKDIR /home/nonroot

EXPOSE 8080

# The image writes nothing at runtime: no bytecode (PYTHONDONTWRITEBYTECODE),
# no logs to disk, no temp files. That is what makes readOnlyRootFilesystem
# work with no emptyDir mounted anywhere.
#
# `sh -c` so $PORT is expanded at runtime rather than baked in; `exec` so
# uvicorn is PID 1 and receives SIGTERM directly.
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
