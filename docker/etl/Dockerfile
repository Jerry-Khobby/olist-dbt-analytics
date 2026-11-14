FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# The loader only talks to Postgres (COPY via psycopg2); no pandas needed
RUN pip install --no-cache-dir "psycopg2-binary~=2.9.13"

WORKDIR /app

# Loader code only; the raw CSVs are mounted at runtime (see docker-compose.yml)
COPY etl/ ./etl/

# Load the raw CSVs into the `raw` schema. Compose waits for Postgres to be
# healthy before starting this, so no sleep is needed.
CMD ["python", "etl/main.py"]
