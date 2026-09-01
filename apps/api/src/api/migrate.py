"""Migration entrypoint: `python -m api.migrate [revision]`.

Shaped for an Argo CD PreSync hook Job — same image as the Deployment, a
different command, exits non-zero if the upgrade fails so the sync stops before
the new pods roll. Builds its Alembic config in code so it needs no ini file on
disk and no writable filesystem.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from api.config import settings
from api.logging import configure_logging

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def build_config(database_url: str) -> Config:
    """Alembic configuration equivalent to the committed alembic.ini."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", database_url)
    # env.py calls fileConfig() only when this is left on; there is no ini
    # here, and configure_logging() has already set the handlers.
    config.attributes["configure_logger"] = False
    return config


def upgrade(revision: str = "head") -> None:
    """Apply migrations up to `revision`."""
    if settings.database_url is None:
        raise SystemExit("DATABASE_URL is required to run migrations")
    logger.info("running migrations", extra={"event": "migrate_start", "revision": revision})
    command.upgrade(build_config(settings.database_url), revision)
    logger.info("migrations applied", extra={"event": "migrate_done", "revision": revision})


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    configure_logging(settings.log_level)
    upgrade(args[0] if args else "head")


if __name__ == "__main__":
    main()
