"""Minimal stdlib HTTP service for the API.

Deliberately dependency-free: it exists so the container image, the CI
pipeline and the Kubernetes manifests can be exercised end to end before any
real framework (FastAPI or otherwise) is chosen.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final
from urllib.parse import urlsplit

SERVICE_NAME: Final[str] = "api"
DEFAULT_PORT: Final[int] = 8080
OK_ROUTES: Final[frozenset[str]] = frozenset({"/", "/healthz"})


def encode_body(payload: Mapping[str, str]) -> bytes:
    """Serialise a JSON payload to the bytes written on the wire."""
    return json.dumps(dict(payload)).encode("utf-8")


def build_response(path: str) -> tuple[int, bytes]:
    """Map a request path to an HTTP status code and a JSON body."""
    route = urlsplit(path).path
    if route in OK_ROUTES:
        return 200, encode_body({"service": SERVICE_NAME, "status": "ok"})
    return 404, encode_body({"service": SERVICE_NAME, "status": "not_found"})


def read_port(env: Mapping[str, str]) -> int:
    """Read the listen port from PORT, falling back to the default."""
    raw = env.get("PORT", "").strip()
    if not raw:
        return DEFAULT_PORT
    # A malformed PORT is a deployment error: fail loudly at startup.
    return int(raw)


def log_event(**fields: object) -> None:
    """Emit a single structured log line to stdout."""
    print(json.dumps({"service": SERVICE_NAME, **fields}), flush=True)


class Handler(BaseHTTPRequestHandler):
    """Serves the health and root routes; everything else is a 404."""

    server_version = f"{SERVICE_NAME}/0.1.0"
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - name mandated by BaseHTTPRequestHandler
        status, body = build_response(self.path)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        """Replace the default access log with one structured line."""
        log_event(event="request", message=fmt % args)


def main() -> None:
    """Serve forever on the configured port."""
    port = read_port(os.environ)
    # Bind on all interfaces: the process only ever runs inside a container.
    server = ThreadingHTTPServer(("", port), Handler)
    log_event(event="listening", port=port)
    server.serve_forever()


if __name__ == "__main__":
    main()
