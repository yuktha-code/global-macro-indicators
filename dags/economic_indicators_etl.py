"""Monthly World Bank ETL with an optional deterministic demo mode for integration tests.

Operational requirements: install Apache Airflow, install this project, provide
DATABASE_URL and set ECON_PIPELINE_MODE=run for real data. The CI smoke test
uses ECON_PIPELINE_MODE=demo and artificial fixtures; it is not a production run.
"""
from datetime import datetime, timedelta
import os
from pathlib import Path
import shlex
from airflow import DAG
from airflow.operators.bash import BashOperator

ROOT = Path(__file__).resolve().parents[1]
MODE = os.getenv("ECON_PIPELINE_MODE", "run")
if MODE not in {"run", "demo"}:
    raise ValueError("ECON_PIPELINE_MODE must be run or demo")
PIPELINE_PYTHON = shlex.quote(os.getenv("ECON_PYTHON_EXECUTABLE", "python"))
RUN = f"cd {shlex.quote(str(ROOT))} && {PIPELINE_PYTHON} -m econpipe.cli {MODE}"
REPORT = f"cd {shlex.quote(str(ROOT))} && {PIPELINE_PYTHON} -m econpipe.cli report"

with DAG(
    dag_id="economic_indicators_etl",
    start_date=datetime(2026, 1, 1),
    schedule="@monthly",
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["public-data", "economic-indicators", "data-engineering"],
) as dag:
    load = BashOperator(
        task_id="fetch_validate_upsert",
        bash_command=RUN,
        append_env=True,
    )
    summarize = BashOperator(
        task_id="verify_sql_reporting",
        bash_command=REPORT,
        append_env=True,
    )
    load >> summarize
