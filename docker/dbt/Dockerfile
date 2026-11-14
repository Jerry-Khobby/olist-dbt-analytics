FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DBT_PROFILES_DIR=/usr/app/dbt

# git: needed by `dbt debug` and for dbt packages hosted on GitHub
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Pin dbt-core explicitly: dbt-postgres alone lets pip pick a dbt-core beta
RUN pip install --no-cache-dir "dbt-core~=1.12.0" "dbt-postgres~=1.11.0"

WORKDIR /usr/app/dbt

# dbt project, including profiles.yml (credentials come from env vars)
COPY dbt/ .

# Run + test all models in dependency order.
# (If you add a packages.yml, change this to: sh -c "dbt deps && dbt build")
CMD ["dbt", "build"]
