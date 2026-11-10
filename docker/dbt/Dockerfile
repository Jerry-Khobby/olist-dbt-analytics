FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DBT_PROFILES_DIR=/usr/app/dbt

# dbt-postgres pulls in a matching dbt-core
RUN pip install --no-cache-dir "dbt-postgres~=1.9"

WORKDIR /usr/app/dbt

# dbt project, including profiles.yml (credentials come from env vars)
COPY dbt/ .

# Install packages, then run + test all models in dependency order
CMD ["sh", "-c", "dbt deps && dbt build"]
