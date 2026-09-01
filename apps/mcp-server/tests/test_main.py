"""Unit tests for the MCP server stand-in. No sockets: the routing and
config helpers are pure functions, so they are tested directly."""

from __future__ import annotations

import json

import pytest

from mcp_server.main import DEFAULT_PORT, build_response, read_port


@pytest.mark.parametrize("path", ["/", "/healthz", "/healthz?probe=1"])
def test_ok_routes_return_service_status(path: str) -> None:
    status, body = build_response(path)
    assert status == 200
    assert json.loads(body) == {"service": "mcp-server", "status": "ok"}


def test_unknown_route_returns_404() -> None:
    status, body = build_response("/nope")
    assert status == 404
    assert json.loads(body)["status"] == "not_found"


def test_read_port_defaults_when_unset_or_blank() -> None:
    assert read_port({}) == DEFAULT_PORT
    assert read_port({"PORT": "  "}) == DEFAULT_PORT


def test_read_port_uses_env_value() -> None:
    assert read_port({"PORT": "9090"}) == 9090


def test_read_port_rejects_malformed_value() -> None:
    with pytest.raises(ValueError):
        read_port({"PORT": "http"})
