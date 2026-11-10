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
| Transformation | dbt Core |
| Warehouse | PostgreSQL (or DuckDB for zero setup) |
| Adapter | `dbt-postgres` |
| Version control | Git / GitHub |
| Docs and lineage | `dbt docs` |

---

## 3. Where dbt Fits in the ETL Pipeline

Traditional ETL is **Extract, Transform, Load**: data is transformed before it reaches the warehouse. Modern cloud warehouses are powerful enough to transform data in place, so most teams now use **ELT**: Extract, Load, then Transform.

```
 Sources              Extract + Load              Transform (dbt)               Consume
┌──────────┐        ┌───────────────┐        ┌──────────────────────┐        ┌────────────┐
│ Olist    │        │ Raw tables in │        │ staging              │        │ BI tools   │
│ CSVs     │  --->  │ PostgreSQL    │  --->  │   -> intermediate    │  --->  │ Metabase   │
│          │        │ (untouched)   │        │     -> marts         │        │ Grafana    │
└──────────┘        └───────────────┘        └──────────────────────┘        └────────────┘
     E + L (not dbt)                              T  <-- dbt lives here
```

**dbt is only the "T".** It does not extract data from sources and it does not load data into the warehouse. It assumes the raw data is already sitting in the warehouse, then transforms it using SQL that runs inside the warehouse itself.

In this project:

- **Extract + Load:** done manually by loading the CSVs into a `raw` schema in Postgres (using `dbt seed`, `COPY`, or a Python script).
- **Transform:** everything after that is dbt.

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

**Generic (YAML):**
- `unique` and `not_null` on every primary key
- `relationships` from `fct_orders.customer_id` to `dim_customers`
- `accepted_values` on `order_status`

**Custom singular test:**
- For each order, payment total should equal item price plus freight. Failures are expected for a small number of orders and are worth investigating.

**Bonus:**
- Source freshness checks and row-count comparisons between layers.

---

## 8. Folder Structure

```
olist-dbt-analytics/
├── docker-compose.yml        # postgres -> etl -> dbt, plus streamlit
├── .env.example              # copy to .env (gitignored) and set credentials
├── docker/                   # one Dockerfile per service
│   ├── dbt/Dockerfile
│   ├── etl/Dockerfile
│   └── streamlit/Dockerfile
├── data/                     # raw Kaggle CSVs (gitignored)
├── docs/                     # images for the README
├── etl/
│   └── main.py               # loads CSVs into the `raw` schema
├── streamlit/
│   └── app.py                # dashboard on top of the marts
└── dbt/                      # the dbt project
    ├── dbt_project.yml
    ├── profiles.yml          # reads credentials from env vars, safe to commit
    ├── seeds/
    ├── analyses/
    ├── macros/
    ├── tests/
    └── models/
        ├── staging/
        │   ├── _sources.yml
        │   ├── _staging.yml
        │   ├── stg_orders.sql
        │   ├── stg_customers.sql
        │   ├── stg_order_items.sql
        │   ├── stg_payments.sql
        │   ├── stg_reviews.sql
        │   ├── stg_products.sql
        │   └── stg_sellers.sql
        ├── intermediate/
        │   ├── int_order_payments_agg.sql
        │   └── int_order_reviews_dedup.sql
        └── marts/
            ├── dim_customers.sql
            ├── dim_products.sql
            ├── dim_sellers.sql
            ├── fct_orders.sql
            ├── monthly_revenue.sql
            ├── delivery_delay_by_state.sql
            └── top_sellers.sql
```

---

## 9. How to Run

```bash
# 1. Install
pip install dbt-postgres

# 2. Load raw CSVs into a `raw` schema in Postgres

# 3. Verify the connection
dbt debug

# 4. Build and test everything
dbt build

# 5. View docs and lineage graph
dbt docs generate
dbt docs serve
```

---

## 10. Learning Checklist

- [ ] Declare sources and use `source()` and `ref()`
- [ ] Build staging, intermediate, and marts layers
- [ ] Write generic tests in YAML
- [ ] Write one custom singular test
- [ ] Write one macro (for example `delivery_days(start, end)`)
- [ ] Build one incremental model
- [ ] Use Jinja `{% if %}` or `{% for %}` in a model
- [ ] Add column descriptions and generate docs
- [ ] Screenshot the lineage graph for the README
- [ ] Push to GitHub with a README that includes two or three business insights

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
