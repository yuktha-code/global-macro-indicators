"""Optional Airflow DAG. Requires Airflow installed separately (not CI-tested)."""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

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
        bash_command="cd /opt/airflow/project && python -m econpipe.cli run",
        env={"DATABASE_URL": "{{ var.value.get('ECON_DATABASE_URL', 'sqlite:////tmp/economic_warehouse.sqlite') }}"},
        append_env=True,
    )
    summarize = BashOperator(
        task_id="verify_sql_reporting",
        bash_command="cd /opt/airflow/project && python -m econpipe.cli report",
        env={"DATABASE_URL": "{{ var.value.get('ECON_DATABASE_URL', 'sqlite:////tmp/economic_warehouse.sqlite') }}"},
        append_env=True,
    )
    load >> summarize
