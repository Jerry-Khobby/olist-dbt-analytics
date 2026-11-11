"""Entry point: load every Olist CSV into the `raw` schema in Postgres.

Run in Docker:   docker compose up etl
Run locally:     python etl/main.py --data-dir data
Force reload:    python etl/main.py --force

Exit codes: 0 = all files loaded or skipped, 1 = one or more files failed or
the database was unreachable, 2 = bad configuration. A non-zero exit stops the
dbt service from starting (it waits for this job to succeed).
"""

import argparse
import os
import sys
import time
from pathlib import Path

import psycopg2

from ingestion import LoadResult, ensure_schemas, load_file
from logger import get_logger
from utils import ConfigError, DbConfig, connect_with_retry, table_name_from_file

log = get_logger(__name__)

# The 9 tables in the Kaggle dataset. Missing ones are warned about, not fatal.
EXPECTED_TABLES = {
    "customers",
    "geolocation",
    "order_items",
    "order_payments",
    "order_reviews",
    "orders",
    "products",
    "sellers",
    "product_category_name_translation",
}

# Arbitrary constant: stops two ETL runs from loading at the same time.
ADVISORY_LOCK_ID = 7_301_955


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load raw Olist CSVs into Postgres.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("RAW_DATA_DIR", "data")),
        help="Folder searched recursively for *.csv files (default: $RAW_DATA_DIR or ./data)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=os.environ.get("FORCE_RELOAD", "").lower() in {"1", "true", "yes"},
        help="Reload every file even if it is unchanged (or set FORCE_RELOAD=true)",
    )
    return parser.parse_args(argv)


def discover_files(data_dir: Path) -> dict[str, Path]:
    """Find CSVs and map table name -> file. Raises ConfigError on problems."""
    if not data_dir.is_dir():
        raise ConfigError(f"Data directory not found: {data_dir.resolve()}")

    files = sorted(data_dir.rglob("*.csv"))
    if not files:
        raise ConfigError(f"No CSV files found under {data_dir.resolve()}")

    by_table: dict[str, Path] = {}
    for path in files:
        try:
            table = table_name_from_file(path)
        except ValueError as exc:
            raise ConfigError(str(exc)) from None
        if table in by_table:
            raise ConfigError(
                f"Two files map to table {table!r}: {by_table[table]} and {path}. Remove one."
            )
        by_table[table] = path

    missing = EXPECTED_TABLES - by_table.keys()
    if missing:
        log.warning("Expected files not found for: %s", ", ".join(sorted(missing)))
    unexpected = by_table.keys() - EXPECTED_TABLES
    if unexpected:
        log.warning("Loading extra files not in the Olist dataset: %s", ", ".join(sorted(unexpected)))
    return by_table


def log_summary(results: list[LoadResult], seconds: float) -> None:
    loaded = [r for r in results if r.status == "loaded"]
    skipped = [r for r in results if r.status == "skipped"]
    failed = [r for r in results if r.status == "failed"]

    log.info("-" * 70)
    log.info(
        "Summary: %d loaded (%s rows), %d skipped, %d failed in %.1fs",
        len(loaded), f"{sum(r.rows for r in loaded):,}", len(skipped), len(failed), seconds,
    )
    for r in failed:
        log.error("  failed: %s -> %s: %s", r.file, r.table, r.error)


def main(argv: list[str] | None = None) -> int:
    started = time.perf_counter()
    args = parse_args(argv)
    log.info("Starting ingestion from %s%s", args.data_dir, " (force reload)" if args.force else "")

    try:
        cfg = DbConfig.from_env()
        files = discover_files(args.data_dir)
    except ConfigError as exc:
        log.error("Configuration error: %s", exc)
        return 2
    log.info("Found %d CSV files", len(files))

    try:
        conn = connect_with_retry(cfg)
    except psycopg2.OperationalError:
        return 1

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (ADVISORY_LOCK_ID,))
            if not cur.fetchone()[0]:
                log.error("Another ETL run is already in progress. Exiting.")
                return 1
        conn.commit()

        ensure_schemas(conn)
        results = [load_file(conn, path, force=args.force) for path in files.values()]
    except psycopg2.Error as exc:
        log.error("Database error during setup: %s", (exc.pgerror or str(exc)).strip())
        return 1
    except KeyboardInterrupt:
        log.warning("Interrupted. The file being loaded was rolled back.")
        return 130
    finally:
        conn.close()  # also releases the advisory lock

    log_summary(results, time.perf_counter() - started)
    return 1 if any(r.status == "failed" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
