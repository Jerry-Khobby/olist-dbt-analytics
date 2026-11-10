"""Load the raw Olist CSVs into the `raw` schema in Postgres.

This is the "E + L" of ELT: data is loaded untouched (every column as text)
so that all cleaning and type casting happens in dbt staging models.

Table names come from the file names, e.g.
    olist_orders_dataset.csv -> raw.orders
"""

import os
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

RAW_SCHEMA = "raw"


def table_name(csv_path: Path) -> str:
    name = csv_path.stem.lower()
    name = re.sub(r"^olist_", "", name)
    name = re.sub(r"_dataset$", "", name)
    return name


def main() -> None:
    data_dir = Path(os.environ.get("RAW_DATA_DIR", "data"))
    csv_files = sorted(data_dir.rglob("*.csv"))
    if not csv_files:
        raise SystemExit(f"No CSV files found under {data_dir.resolve()}")

    url = (
        f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ.get('POSTGRES_HOST', 'localhost')}:{os.environ.get('POSTGRES_PORT', '5432')}"
        f"/{os.environ['POSTGRES_DB']}"
    )
    engine = create_engine(url)

    with engine.begin() as conn:
        conn.execute(text(f"create schema if not exists {RAW_SCHEMA}"))

    for csv_path in csv_files:
        table = table_name(csv_path)
        df = pd.read_csv(csv_path, dtype=str)
        df.to_sql(table, engine, schema=RAW_SCHEMA, if_exists="replace",
                  index=False, chunksize=10_000, method="multi")
        print(f"Loaded {len(df):>9,} rows into {RAW_SCHEMA}.{table}")

    print("ETL complete.")


if __name__ == "__main__":
    main()
