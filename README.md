# Olist E-Commerce Analytics

An end-to-end analytics engineering project on real Brazilian e-commerce data: raw CSVs are loaded into **PostgreSQL**, modelled and tested with **dbt**, and explored in a **Streamlit** dashboard. The whole stack runs with Docker Compose.

> **Status:** in progress. The infrastructure is in place; the ETL, dbt models and dashboard are being built.

## Business questions

Olist is a marketplace that connects small sellers to large online storefronts. This project answers:

| Question | dbt model |
|---|---|
| How is revenue trending month over month? | `monthly_revenue` |
| Which regions receive orders late, and by how many days? | `delivery_delay_by_state` |
| Who are the best and worst sellers by revenue and review score? | `top_sellers` |
| How many customers buy more than once? | `customer_repeat_rate` |

## Architecture

```text
 Kaggle CSVs ──► ETL (Python) ──► Postgres `raw` schema ──► dbt ──► staging ► intermediate ► marts ──► Streamlit
                 Extract + Load                            Transform                                  Dashboard
```

| Service | Role |
|---|---|
| `postgres` | Warehouse (Postgres 15) |
| `etl` | One-off job that loads the raw CSVs into the `raw` schema |
| `dbt` | One-off job that runs `dbt deps && dbt build` (models + tests) |
| `streamlit` | Dashboard on top of the marts, at <http://localhost:8501> |

## Dataset

[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce): about 99k anonymised orders from 2016 to 2018 across 9 related tables.

![Olist source data model](docs/image.png)

## Getting started

**Prerequisites:** Docker with Docker Compose.

1. Clone the repo and download the dataset from Kaggle. Unzip it anywhere inside `data/` (the folder is gitignored).
2. Create your env file and set a password:

   ```bash
   cp .env.example .env
   ```

3. Start the stack:

   ```bash
   docker compose up --build
   ```

4. Open the dashboard at <http://localhost:8501>. Postgres is available on `localhost:5432` (or `POSTGRES_HOST_PORT` from `.env`).

Re-run only the dbt step after changing models (the `dbt/` folder is mounted, so no rebuild is needed):

```bash
docker compose run --rm dbt
```

## Project structure

```text
├── docker-compose.yml
├── .env.example
├── docker/              # one Dockerfile per service (dbt, etl, streamlit)
├── data/                # raw Kaggle CSVs (gitignored)
├── docs/                # diagrams and screenshots
├── etl/                 # Python loader for the raw CSVs
├── dbt/                 # dbt project
│   ├── dbt_project.yml
│   ├── profiles.yml     # reads credentials from env vars
│   └── models/
│       ├── staging/     # 1:1 cleaned views of the raw tables
│       ├── intermediate/# reusable joins and aggregations
│       └── marts/       # dimensions, facts and reporting tables
└── streamlit/           # dashboard app
```

## Tech stack

PostgreSQL 15 · dbt Core (`dbt-postgres`) · Python (pandas, SQLAlchemy) · Streamlit · Docker Compose

## Learn more

[PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) covers the full plan: modelling layers, data quirks in the dataset, the testing approach and the roadmap.
