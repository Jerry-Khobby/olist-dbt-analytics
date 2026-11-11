"""Load one CSV file into the `raw` schema.

Design:
- Raw means untouched: every column is loaded as TEXT. Casting is dbt's job.
- Fast: uses Postgres COPY, which also handles quoted multi-line values
  (some review comments span several lines).
- Atomic: drop, create, load and log all happen in ONE transaction. If anything
  fails, Postgres rolls back and the previous version of the table is untouched.
- Idempotent: every successful load is recorded in etl_meta.ingestion_log with
  the file's SHA-256. If the file hasn't changed since the last load (and the
  table still exists), it is skipped. Re-running the ETL is always safe.
"""

import csv
import time
from dataclasses import dataclass
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection as PgConnection

from logger import get_logger
from utils import file_sha256, table_name_from_file

log = get_logger(__name__)

RAW_SCHEMA = "raw"
META_SCHEMA = "etl_meta"
LOG_TABLE = "ingestion_log"
LOADED_AT_COLUMN = "_loaded_at"


class IngestionError(Exception):
    """A file could not be loaded for a reason we detected ourselves."""


@dataclass
class LoadResult:
    file: str
    table: str
    status: str  # "loaded" | "skipped" | "failed"
    rows: int = 0
    seconds: float = 0.0
    error: str | None = None


def ensure_schemas(conn: PgConnection) -> None:
    """Create the raw and metadata schemas plus the ingestion log, if missing."""
    with conn, conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(RAW_SCHEMA)))
        cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(META_SCHEMA)))
        cur.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {}.{} (
                    id           BIGSERIAL PRIMARY KEY,
                    table_name   TEXT        NOT NULL,
                    source_file  TEXT        NOT NULL,
                    file_sha256  CHAR(64)    NOT NULL,
                    row_count    BIGINT      NOT NULL,
                    duration_s   NUMERIC(10, 2) NOT NULL,
                    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            ).format(sql.Identifier(META_SCHEMA), sql.Identifier(LOG_TABLE))
        )


def read_header(path: Path) -> list[str]:
    """Read and validate the CSV header row."""
    # utf-8-sig strips a byte-order mark if the file has one
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        header = next(csv.reader(f), None)

    if not header:
        raise IngestionError("file is empty or has no header row")

    columns = [col.strip().lower() for col in header]
    if any(not col for col in columns):
        raise IngestionError(f"header has an empty column name: {header}")
    duplicates = sorted({col for col in columns if columns.count(col) > 1})
    if duplicates:
        raise IngestionError(f"header has duplicate columns: {duplicates}")
    if LOADED_AT_COLUMN in columns:
        raise IngestionError(f"header uses the reserved column name {LOADED_AT_COLUMN!r}")
    return columns


def _is_unchanged(conn: PgConnection, table: str, file_hash: str) -> bool:
    """True if the last successful load of `table` used this exact file and the table still exists."""
    with conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (f"{RAW_SCHEMA}.{table}",))
        if cur.fetchone()[0] is None:
            return False
        cur.execute(
            sql.SQL(
                "SELECT file_sha256 FROM {}.{} WHERE table_name = %s ORDER BY loaded_at DESC, id DESC LIMIT 1"
            ).format(sql.Identifier(META_SCHEMA), sql.Identifier(LOG_TABLE)),
            (table,),
        )
        row = cur.fetchone()
        return row is not None and row[0] == file_hash


def load_file(conn: PgConnection, path: Path, force: bool = False) -> LoadResult:
    """Load one CSV into raw.<table>. Never raises for per-file problems: returns a failed result instead."""
    start = time.perf_counter()
    try:
        table = table_name_from_file(path)
    except ValueError as exc:
        log.error("%s: %s", path.name, exc)
        return LoadResult(path.name, "?", "failed", error=str(exc))

    result = LoadResult(path.name, f"{RAW_SCHEMA}.{table}", "failed")

    try:
        file_hash = file_sha256(path)
        if not force and _is_unchanged(conn, table, file_hash):
            log.info("SKIP  %-45s unchanged since last load -> %s", path.name, result.table)
            result.status = "skipped"
            return result

        columns = read_header(path)
        log.info("LOAD  %-45s -> %s (%d columns)", path.name, result.table, len(columns))

        table_id = sql.Identifier(RAW_SCHEMA, table)
        column_ids = [sql.Identifier(col) for col in columns]

        # One transaction: commits on success, rolls back on any exception.
        with conn, conn.cursor() as cur:
            cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(table_id))
            cur.execute(
                sql.SQL("CREATE TABLE {} ({}, {} TIMESTAMPTZ NOT NULL DEFAULT now())").format(
                    table_id,
                    sql.SQL(", ").join(sql.SQL("{} TEXT").format(c) for c in column_ids),
                    sql.Identifier(LOADED_AT_COLUMN),
                )
            )

            copy_stmt = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)").format(
                table_id, sql.SQL(", ").join(column_ids)
            )
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                cur.copy_expert(copy_stmt.as_string(cur), f)

            cur.execute(sql.SQL("SELECT count(*) FROM {}").format(table_id))
            rows = cur.fetchone()[0]
            if rows == 0:
                raise IngestionError("file has a header but no data rows")

            duration = time.perf_counter() - start
            cur.execute(
                sql.SQL(
                    "INSERT INTO {}.{} (table_name, source_file, file_sha256, row_count, duration_s) "
                    "VALUES (%s, %s, %s, %s, %s)"
                ).format(sql.Identifier(META_SCHEMA), sql.Identifier(LOG_TABLE)),
                (table, path.name, file_hash, rows, round(duration, 2)),
            )

        result.status, result.rows, result.seconds = "loaded", rows, duration
        log.info("DONE  %-45s %10s rows in %.1fs", path.name, f"{rows:,}", duration)

    except IngestionError as exc:
        result.error = str(exc)
        log.error("FAIL  %s: %s (previous table left unchanged)", path.name, exc)
    except psycopg2.Error as exc:
        result.error = (exc.pgerror or str(exc)).strip()
        log.error("FAIL  %s: database error: %s (rolled back)", path.name, result.error)
    except (OSError, UnicodeDecodeError) as exc:
        result.error = str(exc)
        log.error("FAIL  %s: could not read file: %s", path.name, exc)

    result.seconds = result.seconds or time.perf_counter() - start
    return result
