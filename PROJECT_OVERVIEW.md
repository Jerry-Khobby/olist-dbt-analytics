# Olist E-Commerce Analytics with dbt

A learning project that turns raw Brazilian e-commerce data into tested, documented, analytics-ready tables using dbt and PostgreSQL.

---

## 1. Project Summary

**Goal:** Build a complete dbt project on a real dataset, covering the full analytics engineering workflow: raw data in, clean business tables out.

**Dataset:** [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (Kaggle). About 99k real, anonymised orders from 2016 to 2018, spread across 9 related CSV files: orders, customers, order items, payments, reviews, products, sellers, geolocation, and a category translation table.

**Business context:** Olist is a marketplace that connects small sellers to large online storefronts. The business wants to understand revenue performance, delivery reliability, and seller quality.

**Business questions the project answers:**

| Question | Output model |
|---|---|
| How is revenue trending month over month? | `monthly_revenue` |
| Which regions receive orders late, and by how many days? | `delivery_delay_by_state` |
| Who are the best and worst sellers by revenue and review score? | `top_sellers` |
| How many customers buy more than once? | `customer_repeat_rate` (bonus) |

---

## 2. Tech Stack

| Component | Tool |
|---|---|
| Extract + Load | Python (`psycopg2`, Postgres `COPY`) |
| Warehouse | PostgreSQL 15 |
| Transformation | dbt Core 1.12 with the `dbt-postgres` adapter |
| Dashboard | Streamlit + Plotly |
| Runtime | Docker Compose |
| Version control | Git / GitHub |
| Docs and lineage | `dbt docs` |

---

## 3. Where dbt Fits in the ETL Pipeline

Traditional ETL is **Extract, Transform, Load**: data is transformed before it reaches the warehouse. Modern cloud warehouses are powerful enough to transform data in place, so most teams now use **ELT**: Extract, Load, then Transform.

```text
 Sources              Extract + Load              Transform (dbt)               Consume
┌──────────┐        ┌───────────────┐        ┌──────────────────────┐        ┌────────────┐
│ Olist    │        │ Raw tables in │        │ staging              │        │ Streamlit  │
│ CSVs     │  --->  │ PostgreSQL    │  --->  │   -> intermediate    │  --->  │ dashboard  │
│          │        │ (untouched)   │        │     -> marts         │        │            │
└──────────┘        └───────────────┘        └──────────────────────┘        └────────────┘
     E + L (not dbt)                              T  <-- dbt lives here
```

**dbt is only the "T".** It does not extract data from sources and it does not load data into the warehouse. It assumes the raw data is already sitting in the warehouse, then transforms it using SQL that runs inside the warehouse itself.

In this project:

- **Extract + Load:** a Python job (`etl/`) loads each CSV into the `raw` schema with Postgres `COPY`. Every column lands as `TEXT`, untouched; typing happens in dbt staging. It is idempotent: a SHA-256 hash of each file is logged in `etl_meta.ingestion_log`, and unchanged files are skipped on the next run.
- **Transform:** everything after that is dbt.
- **Consume:** a Streamlit dashboard that reads only the marts.

---

## 4. What Is dbt?

**dbt (data build tool)** is a command-line framework that lets you build data transformations using plain SQL `SELECT` statements, then handles the engineering work around them: dependency ordering, testing, documentation, and version control.

### The core idea

You write a `SELECT` statement in a `.sql` file. dbt wraps it in the `CREATE VIEW` or `CREATE TABLE` DDL for you and runs it in your warehouse. One file equals one model, and one model equals one table or view.

```sql
-- models/staging/stg_orders.sql
select
    order_id,
    customer_id,
    order_status,
    cast(order_purchase_timestamp as timestamp) as purchased_at
from {{ source('olist_raw', 'orders') }}
```

dbt turns this into a view or table called `stg_orders`. You never write `CREATE TABLE` yourself.

### The key building blocks

| Concept | What it is |
|---|---|
| **Model** | A `.sql` file containing one `SELECT`. The basic unit of dbt. |
| **`ref()`** | Function to reference another model: `{{ ref('stg_orders') }}`. dbt uses these to build the dependency graph and run models in the right order. |
| **`source()`** | Declares a raw table that dbt did not create, so you can reference it, test it, and track freshness. |
| **Materialization** | How a model is built: `view`, `table`, `incremental` (only process new rows), or `ephemeral` (inlined as a CTE). |
| **Tests** | Assertions about your data. Generic tests (`unique`, `not_null`, `relationships`, `accepted_values`) are one line of YAML. Custom singular tests are SQL files that return failing rows. |
| **Jinja** | A templating language inside `{{ }}` and `{% %}`. Adds variables, loops, conditionals, and macros to SQL. |
| **Macros** | Reusable Jinja functions, like Python functions for SQL. |
| **Seeds** | Small CSV files in your repo that dbt loads as tables. Good for lookup data. |
| **Docs and lineage** | `dbt docs generate` builds a website with column descriptions and a visual graph of how every model connects. |

### The main commands

```bash
dbt debug            # check the connection works
dbt seed             # load CSV seeds into the warehouse
dbt run              # build all models
dbt test             # run all tests
dbt build            # run + test everything in dependency order
dbt docs generate    # build documentation
dbt docs serve       # open the docs and lineage graph in a browser
```

### Why teams use it

- **SQL stays the language.** Analysts and engineers share one skill.
- **Version control.** Transformations live in Git, with code review and history.
- **Built-in testing.** Bad data is caught at build time rather than discovered in a dashboard.
- **Automatic lineage.** You can see exactly which upstream tables feed any report.
- **Modular and DRY.** Models build on each other rather than repeating logic.

### What dbt is not

- Not an orchestrator (use Airflow, Dagster, or dbt Cloud to schedule it).
- Not an ingestion tool (use Airbyte, Fivetran, or custom scripts).
- Not a database (it runs on top of one).

---

## 5. Project Layers

dbt projects are organised in layers. Each layer has one job.

```
models/
├── staging/          Layer 1: clean
├── intermediate/     Layer 2: prepare
└── marts/            Layer 3: serve
```

### Staging (`stg_*`)
- One model per raw table, 1:1.
- Only light cleaning: rename columns, cast types, fix typos, standardise values.
- No joins and no business logic.
- Materialised as **views**.

### Intermediate (`int_*`)
- Combines and reshapes staging models for reuse.
- Examples: aggregate payments to one row per order, keep only the latest review per order.
- Exists mainly to prevent **join fan-out** (double-counting revenue).

### Marts
- Business-ready tables used by dashboards and analysts.
- **Dimensions** (`dim_*`): descriptive entities such as customers, products, sellers.
- **Facts** (`fct_*`): events and measurements, such as orders.
- **Reporting marts**: pre-aggregated KPIs such as `monthly_revenue`.
- Materialised as **tables** (or incremental).

---

## 6. Data Quirks to Handle

These are real problems in the dataset, and each teaches a dbt skill.

| Quirk | How it is handled |
|---|---|
| `customer_id` is unique per order, not per person. `customer_unique_id` is the real customer. | Build `dim_customers` on `customer_unique_id`. |
| Orders can have multiple items and multiple payments. | Aggregate in intermediate models before joining, to avoid double-counting. |
| Multiple reviews per order. | Deduplicate with `row_number()` and keep the latest. |
| Misspelled columns (`product_name_lenght`). | Rename in staging. |
| Some categories have no English translation. | Left join to the translation table and `coalesce` to a default. |
| Null delivery dates on undelivered orders. | Conditional logic in the delivery metrics. |

---

## 7. Tests

110 tests run on every `dbt build`.

**Generic (YAML):**

- `unique` and `not_null` on every primary key, in sources, staging and marts
- `accepted_values` on `order_status`, `payment_type` and `review_score`
- `relationships` between models, e.g. `fct_orders.customer_unique_id` to `dim_customers`, and `fct_order_items` to `dim_products`, `dim_sellers` and `fct_orders`

**Singular (SQL in `dbt/tests/`, each returns the failing rows):**

| Test | Checks that |
|---|---|
| `assert_payments_agg_matches_staging_total` | rolling payments up to one row per order loses no money |
| `assert_payment_type_amounts_add_up` | the per-type payment columns sum to the order total |
| `assert_items_agg_matches_staging_totals` | rolling items up loses no items, price or freight |
| `assert_reviews_dedup_keeps_every_order` | deduplicating reviews drops no order |
| `assert_fct_orders_has_one_row_per_order` | `fct_orders` has exactly one row per order in `stg_orders` |
| `assert_fct_order_items_has_no_duplicates` | the incremental model never duplicates an item |
| `assert_dim_customers_covers_every_customer` | every real customer appears in `dim_customers` |
| `assert_monthly_revenue_matches_fct_orders` | the monthly report adds up to the fact table |
| `assert_payment_matches_order_total` | payments equal item prices + freight (**warns** only: 303 orders differ, mostly installment interest) |

---

## 8. Folder Structure

```text
olist-dbt-analytics/
├── docker-compose.yml        # postgres -> etl -> dbt, plus streamlit
├── .env.example              # copy to .env (gitignored) and set credentials
├── docker/                   # one Dockerfile per service
│   ├── dbt/Dockerfile
│   ├── etl/Dockerfile
│   └── streamlit/Dockerfile
├── data/                     # raw Kaggle CSVs (gitignored)
├── docs/                     # screenshots and diagrams for the README
├── etl/                      # loads CSVs into the `raw` schema
│   ├── main.py               # entry point: discovery, advisory lock, summary
│   ├── ingestion.py          # one file -> one table, in one transaction
│   ├── utils.py              # config, connection retry, file hashing
│   └── logger.py
├── streamlit/
│   └── app.py                # dashboard on top of the marts
└── dbt/                      # the dbt project
    ├── dbt_project.yml
    ├── profiles.yml          # reads credentials from env vars, safe to commit
    ├── macros/               # delivery_days, generate_schema_name (+ _macros.yml)
    ├── tests/                # 9 singular tests
    └── models/
        ├── staging/          # views, 1:1 with raw tables
        │   ├── _sources.yml
        │   ├── _staging.yml
        │   ├── stg_orders.sql
        │   ├── stg_customers.sql
        │   ├── stg_order_items.sql
        │   ├── stg_payments.sql
        │   ├── stg_reviews.sql
        │   ├── stg_products.sql
        │   ├── stg_product_category_translation.sql
        │   └── stg_sellers.sql
        ├── intermediate/     # views, one row per order
        │   ├── _intermediate.yml
        │   ├── int_order_items_agg.sql
        │   ├── int_order_payments_agg.sql
        │   └── int_order_reviews_dedup.sql
        └── marts/            # tables
            ├── _marts.yml
            ├── dim_customers.sql
            ├── dim_products.sql
            ├── dim_sellers.sql
            ├── fct_orders.sql
            ├── fct_order_items.sql      # incremental
            ├── monthly_revenue.sql
            ├── delivery_delay_by_state.sql
            ├── top_sellers.sql
            └── customer_repeat_rate.sql
```

---

## 9. How to Run

Everything runs in Docker; see the [README](README.md#getting-started) for details.

```bash
# 1. Configure credentials
cp .env.example .env

# 2. Start everything: Postgres -> ETL -> dbt build -> Streamlit (http://localhost:8501)
docker compose up --build

# 3. After changing models, re-run dbt without re-running the ETL
docker compose run --rm --no-deps dbt dbt build

# 4. Docs and lineage graph at http://localhost:8080
docker compose run --rm --no-deps -p 8080:8080 dbt sh -c "dbt docs generate && dbt docs serve --host 0.0.0.0 --port 8080 --no-browser"
```

---

## 10. Learning Checklist

- [x] Declare sources and use `source()` and `ref()`
- [x] Build staging, intermediate, and marts layers
- [x] Write generic tests in YAML
- [x] Write one custom singular test
- [x] Write one macro (for example `delivery_days(start, end)`)
- [x] Build one incremental model
- [x] Use Jinja `{% if %}` or `{% for %}` in a model
- [x] Add column descriptions and generate docs
- [x] Screenshot the lineage graph for the README
- [x] Push to GitHub with a README that includes two or three business insights

---

## 11. Timeline

| Day | Focus |
|---|---|
| 1 | Setup, load raw data, build staging models |
| 2 | Intermediate models, dimensions, `fct_orders` |
| 3 | Reporting marts and tests |
| 4 | Macro, incremental model, docs, README |

---

## 12. Outcome

A tested, documented, version-controlled dbt project that demonstrates:

- ELT thinking and clear layer separation
- Dimensional modelling (dimensions and facts)
- Data quality testing
- Reusable SQL through Jinja and macros
- Business-focused KPI modelling
