# app-lab

Application repo for the two containerised services that run on the platform
built in the infra repo: an **HTTP API** and an **MCP server**. This repo owns
source, tests, images and the build pipeline. It owns no infrastructure — the
Kubernetes manifests, overlays and Terraform live in the infra repo, and the
only thing that crosses the boundary is an image reference.

Both services are Python and, for now, **stdlib-only**: no third-party runtime
dependencies at all. They answer `GET /` and `GET /healthz` with
`{"service": "...", "status": "ok"}` and read `PORT` from the environment
(default `8080`). That is enough to exercise the image build, the scan gate,
the health probes and the overlay wiring before any framework is chosen.

The MCP server is explicitly a stand-in. The real one must speak **streamable
HTTP** and target the **stateless MCP spec >= 2026-07-28**, so any replica can
serve any request and the Deployment can scale horizontally.

## Layout

```
apps/
  api/                     HTTP API service
    src/api/main.py        http.server app; build_response() is the unit under test
    tests/test_main.py
    pyproject.toml         project metadata + ruff + pytest config
    Dockerfile             python:3.12-slim, non-root, EXPOSE 8080
  mcp-server/              same shape, package `mcp_server`
.github/workflows/
  ci.yml                   lint + format + test, matrix over the changed apps
  build-scan-push.yml      reusable: build -> SBOM -> scan -> (guarded) push
  release-api.yml          main-branch release for api
  release-mcp-server.yml   main-branch release for mcp-server
  zizmor.yml               static analysis of the workflows themselves
Makefile                   lint / test / docker-build
requirements-dev.txt       pinned ruff + pytest, shared by local and CI
renovate.json
```

Each app keeps its own `pyproject.toml`; there is no root one. The services
are independent deployables and should stay that way — a shared root project
would quietly couple their dependency sets.

## Local development

```sh
make dev            # one-time: create .venv and install pinned ruff + pytest
make lint           # ruff check + ruff format --check across both apps
make test           # pytest per app
make lint test      # what CI runs
```

`make lint` and `make test` prefer `.venv/bin/python` when it exists and fall
back to whatever `python3` is on `PATH`, so the global pre-commit hook works
either way. **Run `make lint` before every commit.**

Run a service directly:

```sh
cd apps/api && PYTHONPATH=src PORT=8080 python -m api.main
curl -s localhost:8080/healthz
```

Build images (amd64 only — every deployment target is x86, so building arm64
would just double the build time, even on an Apple Silicon laptop):

```sh
make docker-build                 # app-lab/api:dev, app-lab/mcp-server:dev
docker run --rm -p 8080:8080 app-lab/api:dev
```

## Pairing with the infra repo's kind lab

The infra repo's `k8s/base` already defines `api` and `mcp-server`
Deployments, Services, ServiceAccounts and NetworkPolicies, currently running
`traefik/whoami` as a placeholder. To run the real services in the local kind
lab, build the images, load them into the cluster, and point the overlay at
them:

```sh
make docker-build
kind load docker-image app-lab/api:dev app-lab/mcp-server:dev --name lab
```

Then add to the infra repo's `k8s/overlays/local/kustomization.yaml`:

```yaml
images:
  - name: traefik/whoami
    newName: app-lab/api
    newTag: dev
```

(one `images:` entry per container; the container ports in the base manifests
are `80` and will need to become `8080` when the placeholder is retired).

In dev/prod the same mechanism is driven by CI instead of by hand: the release
workflow pushes `REGISTRY/<image>:<sha>` and bumps the `images:` block in
`k8s/overlays/dev`, which Argo CD then syncs. Nothing in `k8s/base` changes.

## CI

**`ci.yml`** — on every pull request and every push to `main`. GitHub's
`paths:` filter is per-workflow rather than per-matrix-leg, so a `changes` job
diffs against the PR base (or the previous `main` commit) and emits the list of
affected apps as a JSON matrix; a change to `ci.yml` or `requirements-dev.txt`
selects both. Each leg installs the pinned tooling and runs `ruff check`,
`ruff format --check` and `pytest`. Concurrency is grouped by ref with
`cancel-in-progress` on pull requests only.

**`build-scan-push.yml`** — reusable (`workflow_call`), taking `service` (the
directory under `apps/`) and `image` (the image name), and returning the pushed
`digest`. It runs:

1. **Build** with buildx, `platforms: linux/amd64`, `push: false`,
   `load: true`, GitHub Actions layer cache (`type=gha`).
2. **SBOM** via syft (`anchore/sbom-action`) in SPDX JSON, uploaded as a
   workflow artifact so a future CVE disclosure can be traced to a build.
3. **Scan** via grype (`anchore/scan-action`) with `fail-build: true` and
   `severity-cutoff: critical` — a critical vulnerability stops the release
   before anything is pushed. Note this can turn red on a base-image CVE that
   has no fix yet; the deliberate response is to rebase the image, not to
   loosen the gate.
4. **Push**, only when the cloud exists (see the guards below), as a second
   `build-push-action` invocation with `provenance: mode=max` and `sbom: true`.
   It has to be a second call: buildx cannot attach attestations while also
   loading into the docker daemon. The layer cache makes it a near no-op.

**Guards.** No GCP project or Artifact Registry exists yet, so every
cloud-touching step is conditioned on repository variables that are empty until
one does:

| Step | Guard | Why |
| --- | --- | --- |
| `google-github-actions/auth` | `vars.REGISTRY != '' && vars.WIF_PROVIDER != '' && vars.WIF_SERVICE_ACCOUNT != ''` | Workload Identity Federation needs all three; without them the step would fail. |
| `docker/login-action` | `vars.REGISTRY != '' && steps.auth.outcome == 'success'` | Nothing to log in to, and no token to log in with. |
| push `build-push-action` | `vars.REGISTRY != '' && steps.auth.outcome == 'success'` | Nowhere to push. |
| `bump-manifests` job | `vars.REGISTRY != '' && needs.build.outputs.digest != ''` | Never bump a manifest to an image that was not pushed. |

The result is that CI is fully green pre-cloud: build, SBOM and scan all run
for real, and only the push is skipped. The `digest` output is empty in that
case, which callers must check — the `bump-manifests` guard does.

**`release-api.yml` / `release-mcp-server.yml`** — on pushes to `main` under
that app's path (plus its own file and the reusable workflow). Each calls
`build-scan-push.yml`, then runs a `bump-manifests` stub that today only prints
the bump it would make. Implementing it needs a cross-repo credential — a
GitHub App installation token scoped to the infra repo's contents, in
preference to a classic PAT — which is left as a documented TODO rather than
half-wired secrets. Release concurrency is per service with
`cancel-in-progress: false`: a release is never cancelled mid-flight.

**`zizmor.yml`** — audits the workflow files on any change to
`.github/workflows/**`. SARIF upload is disabled (`advanced-security: false`)
because a fresh private repo has no GitHub Advanced Security; findings fail the
job directly instead.

**Supply chain.** Every third-party action is pinned to a full commit SHA with
the version in a trailing comment, and Renovate (`helpers:pinGitHubActionDigests`)
keeps both in step. Every workflow declares a least-privilege `permissions:`
block — `contents: read` throughout, plus `id-token: write` on the build job
solely for WIF. Checkouts use `persist-credentials: false` so the job token is
not left in `.git/config`.

## GitHub setup checklist

Once this repo is pushed to a remote:

1. **Ruleset on `main`** — require a pull request, and require these status
   checks to pass: `check (api)`, `check (mcp-server)`, `audit workflows`.
   Block force pushes and deletions.
2. **`production` environment** — create it, add required reviewers, and scope
   the deploy credentials to it once they exist.
3. **Repository variables** (Settings → Secrets and variables → Actions →
   Variables). Leave them unset until the GCP project exists; everything stays
   green meanwhile.
   - `REGISTRY` — e.g. `<region>-docker.pkg.dev/<project>/<repo>`
   - `WIF_PROVIDER` — full workload identity provider resource name
   - `WIF_SERVICE_ACCOUNT` — deployer service account email
4. **Renovate** — install the GitHub App on the repo; `renovate.json` is
   already committed (action digest pinning, plus the pip/PEP 621/uv and
   Dockerfile managers).
5. **Actions permissions** — set the default `GITHUB_TOKEN` permissions to
   read-only at the repo level; the workflows request what they need.
