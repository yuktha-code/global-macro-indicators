# Global Macroeconomic Indicators

**Python · World Bank Indicators API v2 · SQLAlchemy · SQLite/PostgreSQL · ETL · SQL marts · pytest · GitHub Actions**

A public-data research and analytics project designed to ingest macroeconomic indicators from the World Bank's official API, validate them, and maintain a queryable relational warehouse with source-level audit history. The project is sector-neutral: economic statistics, public-data pipelines and relational analytics are applicable to research, fintech, consulting and general data engineering.

**Execution status (10 Oct 2026):** 16 offline automated tests passed; a demonstration load and idempotent rerun completed successfully with an **artificial API-shaped fixture**. **The live World Bank download, PostgreSQL Docker execution and Airflow scheduling have not yet been executed and verified** in this environment because the live API is not network reachable here and Docker is unavailable. Those components and live row counts remain unverified until actually executed.

## Why this project

The World Bank API publishes country-level indicators under separate endpoints for country metadata, indicator metadata and time-series observations. Turning these records into a consistent analytical dataset involves paginated ingestion, schema harmonization, country/indicator reference tables, nullable values, incremental source revisions, duplicate handling and repeatable quality checks. These are transferable data-engineering problems, regardless of industry.

## Architecture

```mermaid
flowchart TD
    A[World Bank V2 API: countries / indicators / observations] --> B[HTTP retries and complete pagination]
    B --> C[Validate year, country, indicator, numeric values]
    C --> D{Batch meets quality contract?}
    D -->|No| E[Fail without loading incomplete batch]
    D -->|Yes| F[SQLAlchemy transaction]
    F --> G[dim_country / dim_indicator]
    G --> H[stg_indicator_observation + etl_run audit]
    H --> I[Upsert fact_country_indicator_year]
    I --> J[Foreign-key reconciliation]
    J --> K[SQL views / analytics queries / JSON run report]
```

## Real data sources

* Country metadata: `https://api.worldbank.org/v2/country/IND;BRA;USA;ZAF;DEU;JPN?format=json`
* Indicator metadata: `https://api.worldbank.org/v2/indicator/NY.GDP.MKTP.CD?source=2&format=json`
* Observation data: `https://api.worldbank.org/v2/country/IND;BRA;USA;ZAF;DEU;JPN/indicator/NY.GDP.MKTP.CD?date=2015:2024&source=2&format=json`

The client automatically iterates over all response pages; URLs above illustrate route structure, not a predownloaded repository dataset. A World Bank API key is not required. Full descriptions and links are in [DATA_SOURCES.md](DATA_SOURCES.md).

The configured indicators are **GDP (current US$)** (`NY.GDP.MKTP.CD`), **consumer price inflation (annual %)** (`FP.CPI.TOTL.ZG`), **unemployment (% of labor force)** (`SL.UEM.TOTL.ZS`), and **population total** (`SP.POP.TOTL`). The default ingest scope is six countries and calendar years 2015–2024. The API may return unavailable values as `null`; missing source data are **never invented or replaced with zero**.

## Run locally on Windows: no Docker required

From PowerShell in the extracted repository folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q

# Demonstration mode only: artificial API-shaped fixture; no internet required
.\.venv\Scripts\python.exe -m econpipe.cli demo --db-url sqlite:///data/demo_warehouse.sqlite
.\.venv\Scripts\python.exe -m econpipe.cli demo --db-url sqlite:///data/demo_warehouse.sqlite
.\.venv\Scripts\python.exe -m econpipe.cli report --db-url sqlite:///data/demo_warehouse.sqlite

# LIVE SOURCE: downloads World Bank data; requires internet connectivity
.\.venv\Scripts\python.exe -m econpipe.cli run --db-url sqlite:///data/economic_warehouse.sqlite
.\.venv\Scripts\python.exe -m econpipe.cli report --db-url sqlite:///data/economic_warehouse.sqlite
```

To ingest another supported subset:

```powershell
.\.venv\Scripts\python.exe -m econpipe.cli run --countries IND,USA,BRA --first-year 2018 --last-year 2024 --db-url sqlite:///data/economic_warehouse.sqlite
```

Run the **live** command twice against the same warehouse and verify the second JSON report has `inserted: 0` and `updated: 0`, unless the upstream source has changed between requests. Outputs are written to `results/last_run.json`, and the SQL warehouse to `data/economic_warehouse.sqlite` (not committed).

## Optional PostgreSQL: development-only configuration

Install Docker Desktop and ensure the Docker Engine is running:

```powershell
docker compose up -d postgres
.\.venv\Scripts\python.exe -m pip install psycopg2-binary
$env:DATABASE_URL = 'postgresql+psycopg2://econ_dev:local_dev_only_change_me@localhost:5433/economic_data'
.\.venv\Scripts\python.exe -m econpipe.cli run
.\.venv\Scripts\python.exe -m econpipe.cli report
```

Change local development credentials before using outside a private development machine. Do not claim this Postgres option was deployed until you run it successfully. `dags/economic_indicators_etl.py` is an **optional Airflow DAG definition** with monthly scheduling and retries; you must install/configure Airflow and mount the project before triggering it. No Airflow run is included here.

## Warehouse model

| Table or view | Grain / function |
| --- | --- |
| `dim_country` | One country with metadata and income classification |
| `dim_indicator` | One indicator with name, units and official source |
| `etl_run` | One run ID, timing and counts for every successful load |
| `stg_indicator_observation` | Every accepted country–indicator–year observation **per run** |
| `fact_country_indicator_year` | Latest recorded value for each country–indicator–year key |
| `v_country_indicator_long` | Analyst-ready long table with joined dimensions |
| `v_latest_available` | Latest non-null recorded value for each country/indicator |

The warehouse uses composite keys, reference integrity and an all-or-nothing load transaction. A replay of unchanged data records a new audit run and staging snapshot but **does not add duplicate fact rows**. Source revisions can update the affected fact rows. See [SCHEMA_AND_QUALITY.md](SCHEMA_AND_QUALITY.md).

## Verified engineering checks

Executed in an offline environment with `python -m pytest -q`:

* 16 tests passed, covering two-page API retrieval, incomplete/malformed/failed API responses, duplicate observations, missing values, out-of-scope records, chronological year bounds, source revisions, database rollback, full ETL load and repeat-load idempotence.
* Artificial fixture demo: 8 source rows, 1 null value, 8 inserted facts; second run: 0 inserted, 0 updated and 8 unchanged.
* Foreign-key orphan count after load: 0. These counts are **illustrative test results**, not World Bank observations.

## Repository structure

```text
global-macro-indicators/
  econpipe/
    api.py             # complete paginated HTTP client, bounded retry
    transform.py       # country/indicator/year and numeric data contracts
    store.py           # transactional SQLAlchemy warehouse and marts
    pipeline.py        # ingest orchestrator and artificial demo adapter
    cli.py             # commands: run / demo / report
  tests/
    fixtures/demo_api.json   # ARTIFICIAL fixture, not a real data dump
    test_api.py
    test_transform.py
    test_pipeline.py
  sql/analysis.sql
  dags/economic_indicators_etl.py    # optional; not deployed
  docker-compose.yml                # optional PostgreSQL; not verified here
  pyproject.toml
  requirements.txt
  README.md
  DATA_SOURCES.md
  SCHEMA_AND_QUALITY.md
  .github/workflows/ci.yml
```

## Limitations and next engineering steps

1. **Live API, Docker/PostgreSQL and Airflow need independent verification** before describing the components as verified. CI runs offline so its success does not establish those deployments.
2. This bounded portfolio dataset does not demonstrate Spark, Kafka, Hadoop, cloud deployment or petabyte-scale workloads.
3. Data is annual, and latest record dates differ by indicator. GDP in current USD is not real GDP; no currency or inflation adjustment is performed.
4. The client retries transient HTTP errors and rejects incomplete pagination. A production pipeline would add raw payload archiving, source checksums, alerts, watermark strategy and concurrency-aware orchestration.
5. The `fact_country_indicator_year` table stores the latest ingested observation. It does not preserve every revision; per-run staging tables retain loaded snapshots but not arbitrary upstream request metadata or failed fetches.
6. World Bank country codes and classifications can evolve. Configured codes and reference metadata should be reviewed periodically.

**Not affiliated with the World Bank.**