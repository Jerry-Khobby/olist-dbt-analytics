"""Logging setup shared by every ETL module.

Usage:
    from logger import get_logger
    log = get_logger(__name__)

The level comes from the LOG_LEVEL env var (DEBUG, INFO, WARNING, ERROR).
Logs go to stdout so `docker compose logs etl` shows them.
"""

import logging
import os
import sys

_ROOT = "etl"
_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-16s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _configure_root() -> logging.Logger:
    root = logging.getLogger(_ROOT)
    if root.handlers:  # already configured
        return root

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, _DATE_FORMAT))
    root.addHandler(handler)

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = logging.getLevelName(level_name)
    if not isinstance(level, int):  # unknown name -> fall back to INFO
        level = logging.INFO
    root.setLevel(level)
    root.propagate = False
    return root


def get_logger(name: str) -> logging.Logger:
    """Return a child of the `etl` logger, e.g. `etl.ingestion`."""
    _configure_root()
    short = name.rsplit(".", 1)[-1] if name != "__main__" else "main"
    return logging.getLogger(f"{_ROOT}.{short}")
