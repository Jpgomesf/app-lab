"""JSON logging on top of the standard library.

structlog would buy formatting sugar and not much else here: the only
requirement is that every line is a single JSON object on stdout, which the
collector scrapes. A ~30-line formatter keeps the dependency list shorter.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Final

from api.config import SERVICE_NAME, LogLevel

# Attributes present on every LogRecord; anything else was passed by the caller
# via `extra=` and is worth promoting to a top-level field. `color_message` is
# uvicorn's ANSI-escaped copy of the message — noise in a JSON line.
_RESERVED: Final[frozenset[str]] = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | frozenset({"message", "asctime", "taskName", "color_message"})


class JsonFormatter(logging.Formatter):
    """Renders a LogRecord as one line of JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update({k: v for k, v in record.__dict__.items() if k not in _RESERVED})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: LogLevel) -> None:
    """Point the root logger at stdout with the JSON formatter.

    Uvicorn installs its own handlers on import; replacing the root handlers
    and clearing theirs keeps every line in one format.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True

    # RequestLogMiddleware is the access log. Leaving uvicorn's on as well
    # doubles every request line and the two disagree about what a "path" is.
    logging.getLogger("uvicorn.access").disabled = True
