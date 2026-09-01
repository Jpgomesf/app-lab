"""Access logging.

Written as raw ASGI rather than `BaseHTTPMiddleware`: the latter wraps every
request in an extra task and a memory-object stream, which is real overhead for
something that only needs to read the response status.
"""

from __future__ import annotations

import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("api.access")


class RequestLogMiddleware:
    """Log one JSON line per HTTP request: method, path, status, duration."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        # Stays 500 unless the app actually sends a response start, which is
        # exactly what an unhandled exception looks like from out here.
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            logger.info(
                "request",
                extra={
                    "event": "request",
                    "http_method": scope.get("method", ""),
                    "path": scope.get("path", ""),
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
