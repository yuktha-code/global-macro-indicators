import json
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import text

from econpipe.pipeline import Config, DemoClient, run
from econpipe.store import connect
from econpipe.transform import DataQualityError

FIXTURE = Path(__file__).parent / "fixtures" / "demo_api.json"


def config(tmp_path):
    return Config(countries=("IND","BRA"), indicators=("NY.GDP.MKTP.CD","FP.CPI.TOTL.ZG"),
                  first_year=2021,last_year=2022,db_url=f"sqlite:///{tmp_path / 'test.sqlite'}",mode="demo")


def test_full_load_missing_value_audit_and_views(tmp_path):
    cfg = config(tmp_path)
    report = run(cfg, DemoClient(FIXTURE))
    assert report["source_rows"] == 8
    assert report["valid_unique_rows"] == 8
    assert report["missing_value_rows"] == 1
    assert report["inserted"] == 8
    assert report["warehouse_fact_rows"] == 8
    assert report["fk_orphan_rows"] == 0
    engine = connect(cfg.db_url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM v_country_indicator_long")).scalar_one() == 8
        assert conn.execute(text("SELECT count(*) FROM v_latest_available")).scalar_one() == 4
        assert conn.execute(text("SELECT value FROM fact_country_indicator_year WHERE country_code='BRA' AND year=2022 AND indicator_code='NY.GDP.MKTP.CD'")).scalar_one_or_none() is None
        assert conn.execute(text("SELECT count(*) FROM stg_indicator_observation")).scalar_one() == 8
    engine.dispose()


def test_idempotent_rerun_with_full_source_audit(tmp_path):
    cfg = config(tmp_path)
    run(cfg, DemoClient(FIXTURE))
    second = run(cfg, DemoClient(FIXTURE))
    assert (second["inserted"],second["updated"],second["unchanged"]) == (0,0,8)
    engine = connect(cfg.db_url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM etl_run")).scalar_one() == 2
        assert conn.execute(text("SELECT count(*) FROM stg_indicator_observation")).scalar_one() == 16
    engine.dispose()


def test_source_revision_updates_existing_value(tmp_path):
    cfg = config(tmp_path)
    run(cfg, DemoClient(FIXTURE))
    client = DemoClient(FIXTURE)
    client.fixture["observations"]["NY.GDP.MKTP.CD"][0]["value"] = 999.0
    revised = run(cfg, client)
    assert revised["updated"] == 1 and revised["unchanged"] == 7


def test_validation_failure_writes_no_partial_rows(tmp_path):
    cfg = config(tmp_path)
    client = DemoClient(FIXTURE)
    client.fixture["observations"]["FP.CPI.TOTL.ZG"][0]["countryiso3code"] = "USA"
    with pytest.raises(DataQualityError):
        run(cfg, client)
    assert not (tmp_path / "test.sqlite").exists()


def test_db_failure_rolls_back_entire_warehouse_update(tmp_path):
    cfg = config(tmp_path)
    run(cfg, DemoClient(FIXTURE))
    client = DemoClient(FIXTURE)
    client.fixture["observations"]["NY.GDP.MKTP.CD"][0]["value"] = 999
    # Schema corruption to force a transaction error prior to successful commit
    with sqlite3.connect(tmp_path / "test.sqlite") as c:
        c.execute("DROP TABLE stg_indicator_observation")
        c.execute("CREATE TABLE stg_indicator_observation (bad_column TEXT)")
    with pytest.raises(Exception):
        run(cfg, client)
    engine = connect(cfg.db_url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM etl_run")).scalar_one() == 1
        assert conn.execute(text("SELECT value FROM fact_country_indicator_year WHERE country_code='IND' AND year=2021 AND indicator_code='NY.GDP.MKTP.CD'")).scalar_one() == 123
    engine.dispose()


def test_config_rejects_duplicates_and_bad_years(tmp_path):
    with pytest.raises(ValueError):
        Config(countries=("IND","IND")).validate()
    with pytest.raises(ValueError):
        Config(first_year=2028,last_year=2025).validate()
