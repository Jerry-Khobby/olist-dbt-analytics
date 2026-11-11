"""Helpers: configuration, database connection with retries, file utilities."""

import hashlib
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as PgConnection

from logger import get_logger

log = get_logger(__name__)


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    user: str
    password: str
    dbname: str

    @classmethod
    def from_env(cls) -> "DbConfig":
        """Read connection settings from POSTGRES_* env vars."""
        required = ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"]
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise ConfigError(f"Missing required env vars: {', '.join(missing)}")

        port_raw = os.environ.get("POSTGRES_PORT", "5432")
        try:
            port = int(port_raw)
        except ValueError:
            raise ConfigError(f"POSTGRES_PORT must be a number, got {port_raw!r}") from None

        return cls(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=port,
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            dbname=os.environ["POSTGRES_DB"],
        )

    def describe(self) -> str:
        """Connection target without the password, safe to log."""
        return f"{self.user}@{self.host}:{self.port}/{self.dbname}"


def connect_with_retry(cfg: DbConfig, attempts: int = 5, base_delay: float = 2.0) -> PgConnection:
    """Connect to Postgres, retrying with exponential backoff (2s, 4s, 8s, ...)."""
    for attempt in range(1, attempts + 1):
        try:
            conn = psycopg2.connect(
                host=cfg.host,
                port=cfg.port,
                user=cfg.user,
                password=cfg.password,
                dbname=cfg.dbname,
                connect_timeout=10,
                client_encoding="UTF8",
                application_name="olist-etl",
            )
            log.info("Connected to %s", cfg.describe())
            return conn
        except psycopg2.OperationalError as exc:
            if attempt == attempts:
                log.error("Could not connect to %s after %d attempts", cfg.describe(), attempts)
                raise
            delay = base_delay * 2 ** (attempt - 1)
            log.warning(
                "Connection attempt %d/%d failed (%s). Retrying in %.0fs",
                attempt, attempts, str(exc).strip(), delay,
            )
            time.sleep(delay)
    raise AssertionError("unreachable")


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file in chunks so large files don't need to fit in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


_VALID_TABLE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def table_name_from_file(path: Path) -> str:
    """Map a CSV file name to a table name.

    olist_orders_dataset.csv          -> orders
    product_category_name_translation -> product_category_name_translation
    """
    name = path.stem.lower().strip()
    name = re.sub(r"^olist_", "", name)
    name = re.sub(r"_dataset$", "", name)
    name = re.sub(r"[^a-z0-9_]", "_", name)
    if not _VALID_TABLE.match(name):
        raise ValueError(f"Cannot derive a valid table name from {path.name!r} (got {name!r})")
    return name
