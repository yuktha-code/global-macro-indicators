# Verification report — 10 October 2026

## What has been executed

**Offline tests:** 16 passed locally using Python 3.13 and on GitHub Actions using Python 3.11. Covers World Bank-style response pagination, validation failures, duplicate detection, missing values, transactional rollback, SQL warehouse loads, and idempotent replays.

- Offline workflow: https://github.com/yuktha-code/global-macro-indicators/actions/runs/38058036401
- Subsequent offline run: https://github.com/yuktha-code/global-macro-indicators/actions/runs/38058101459

**Artificial fixture results:** 8 accepted example observations, including one SQL NULL, loaded as 8 fact records; identical replay inserted 0 and updated 0. This is test data, not a real World Bank extract.

**Real World Bank API results:** A separate GitHub Actions workflow successfully requested data from the official World Bank Indicators API v2 for India, Brazil and USA, covering GDP in current USD and annual CPI inflation for 2021–2023. It obtained **18 real API observation records**, inserted **18 fact rows**, and verified an identical second load with **0 inserts**, **0 updates**, and **0 foreign-key orphan rows**.

- Live ingestion run: https://github.com/yuktha-code/global-macro-indicators/actions/runs/38058101437
- Machine-readable reports are available as an artifact on that workflow run. These are bounded live smoke-test results, not a claim of production deployment.

## Not yet verified

- Running this setup with PostgreSQL under Docker. The provided Compose file and SQLAlchemy PostgreSQL dialect integration are configuration, not verified deployment.
- Triggering the monthly Apache Airflow DAG using a configured scheduler.
- Large-scale cloud/distributed data workloads, Spark, Kafka or Hadoop.

## Data lineage

Official World Bank API v2, World Development Indicators. Endpoints and indicator codes are documented in [DATA_SOURCES.md](DATA_SOURCES.md). Annual values may be missing for some country/indicator/year combinations; NULL is preserved as NULL, not silently replaced by zero.

## Reproduce

Run `python -m pytest -q`, `python -m econpipe.cli demo`, and `python -m econpipe.cli run` in a Python 3.11+ environment. For a live run, use a reliable internet connection. See [README.md](README.md) and [WINDOWS_RUNBOOK.ps1](WINDOWS_RUNBOOK.ps1).
