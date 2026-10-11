# Global Macroeconomic Indicators

[![Offline Python and SQL checks](https://github.com/yuktha-code/global-macro-indicators/actions/workflows/ci.yml/badge.svg)](https://github.com/yuktha-code/global-macro-indicators/actions/workflows/ci.yml) [![Live World Bank ingestion](https://github.com/yuktha-code/global-macro-indicators/actions/workflows/live-api.yml/badge.svg)](https://github.com/yuktha-code/global-macro-indicators/actions/workflows/live-api.yml)

**Python · World Bank Indicators API v2 · SQLAlchemy · SQLite/PostgreSQL · ETL · SQL marts · pytest · GitHub Actions**

A public-data research and analytics project designed to ingest macroeconomic indicators from the World Bank's official API, validate them, and maintain a queryable relational warehouse with source-level audit history. The project is sector-neutral: economic statistics, public-data pipelines and relational analytics are applicable to research, fintech, consulting and general data engineering.

**Verified status (10 Oct 2026):** The 16 offline tests and fixture replay passed in GitHub Actions. A separate GitHub Actions [live API verification](https://github.com/yuktha-code/global-macro-indicators/actions/runs/38058101437) successfully downloaded 18 real World Bank indicator records for IND, BRA and USA (GDP and inflation, 2021–2023); 18 facts were inserted and an immediate rerun inserted 0 and updated 0, with 0 foreign-key orphans. PostgreSQL integration and an Airflow DAG execution are now independently verified in GitHub Actions using **artificial fixture data**; they are not production deployments.

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

Change local development credentials before using outside a private development machine. A PostgreSQL 16 service was independently exercised in GitHub Actions on 12 Oct 2026. This local Compose example remains optional and has not been separately verified on a personal computer. `dags/economic_indicators_etl.py` defines two dependent tasks and monthly scheduling. [The GitHub Actions DAG test](https://github.com/yuktha-code/global-macro-indicators/actions/runs/38178920480) executed both tasks successfully against the **artificial eight-row demo fixture** under Airflow 2.10.5. Real-world scheduling, monitoring and live-data production runs are not verified; use `ECON_PIPELINE_MODE=run` for a separately configured live environment.

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

* 18 tests passed in [core CI](https://github.com/yuktha-code/global-macro-indicators/actions/runs/38178920468), with the optional Parquet/DuckDB test skipped in the core-only environment, covering two-page API retrieval, incomplete/malformed/failed API responses, duplicate observations, missing values, out-of-scope records, chronological year bounds, source revisions, database rollback, full ETL load and repeat-load idempotence.
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
  dags/economic_indicators_etl.py    # two-task CI-executed DAG; no production deployment
  docker-compose.yml                # optional local PostgreSQL Compose; hosted Postgres separately tested
  pyproject.toml
  requirements.txt
  README.md
  DATA_SOURCES.md
  SCHEMA_AND_QUALITY.md
  .github/workflows/ci.yml
```

## Limitations and next engineering steps

1. **Live API ingestion, PostgreSQL integration and a two-task Airflow DAG smoke test are verified separately in GitHub Actions.** The PostgreSQL and Airflow checks use artificial fixtures, not a production source/scheduler. A personal-machine Docker Compose run and an unattended recurring Airflow deployment have not been verified.
2. This bounded dataset does not demonstrate Spark, Hadoop, cloud deployment or petabyte-scale workloads. A separate **eight-event Kafka broker integration test** is verified, not a production streaming system.
3. Data is annual, and latest record dates differ by indicator. GDP in current USD is not real GDP; no currency or inflation adjustment is performed.
4. The client retries transient HTTP errors and rejects incomplete pagination. A production pipeline would add raw payload archiving, source checksums, alerts, watermark strategy and concurrency-aware orchestration.
5. The `fact_country_indicator_year` table stores the latest ingested observation. It does not preserve every revision; per-run staging tables retain loaded snapshots but not arbitrary upstream request metadata or failed fetches.
6. World Bank country codes and classifications can evolve. Configured codes and reference metadata should be reviewed periodically.

**Not affiliated with the World Bank.**

## Optional streaming, partitioning and cloud-storage exercises (October 2026)

The [integration lab source](econpipe/integration_lab.py) and [automated checks](.github/workflows/integration-lab.yml) extend the public-indicators warehouse:

- **Apache Kafka:** Python `confluent-kafka` producer sends deterministic, keyed JSON observation events with delivery acknowledgements. [Broker integration CI](https://github.com/yuktha-code/global-macro-indicators/actions/runs/38086500899) verified **8 messages produced and consumed** against an actual Apache Kafka broker.
- **Hive-compatible Parquet:** PyArrow exports `year=YYYY` directories containing Parquet files. DuckDB checks confirmed **8 records in 2 year partitions** and an unchanged repeat export. [Hive external-table DDL](sql/hive_external_table.sql) is provided, but **Apache Hive itself has not been deployed or run**.
- **Azure Blob SDK:** The Python SDK uploaded and listed **2 Parquet blobs using Azurite**, the local Azure Storage emulator, in the same [passing CI run](https://github.com/yuktha-code/global-macro-indicators/actions/runs/38086500899). **No actual Azure cloud deployment is claimed.**

The core pipeline remains independent of these optional dependencies; [core CI](https://github.com/yuktha-code/global-macro-indicators/actions/runs/38086500875) passed **18 tests with one optional Parquet test skipped** in the core-only environment.

These are educational integrations and engineering tests, not a production cluster or end-to-end exactly-once Kafka/Azure/Hive system.


## Hosted PostgreSQL and Apache Airflow verification (12 Oct 2026)

A separately automated [GitHub Actions workflow](.github/workflows/postgres-airflow-verification.yml) produced these independently checked outcomes in [successful run 38178920480](https://github.com/yuktha-code/global-macro-indicators/actions/runs/38178920480):

- **PostgreSQL 16:** Eight **artificial fixture** facts inserted; zero foreign-key orphans; identical replay left eight facts unchanged with two run-audit records and zero duplicate fact rows.
- **Airflow 2.10.5:** `airflow dags test economic_indicators_etl 2026-10-01` executed both `fetch_validate_upsert` and `verify_sql_reporting` tasks to **SUCCESS**, and an assertion confirmed eight rows in the fixture SQL warehouse.
- **Runtime compatibility:** Airflow and the SQLAlchemy 2 ETL executable used isolated Python environments to prevent incompatible dependency resolution.

These checks verify real service behavior in ephemeral CI environments, **not a production system, cloud-hosted warehouse, or automatic live monthly execution**.
