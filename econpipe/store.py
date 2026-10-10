"""Transactional SQLAlchemy warehouse; supports SQLite locally and PostgreSQL."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from sqlalchemy import (MetaData, Table, Column, String, Integer, Float, ForeignKey,
                        ForeignKeyConstraint, PrimaryKeyConstraint, DateTime,
                        create_engine, event, select, insert, text)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

META = MetaData()
countries = Table("dim_country", META,
    Column("country_code", String(3), primary_key=True), Column("iso2", String(2), nullable=False),
    Column("name", String(160), nullable=False), Column("region", String(120), nullable=False),
    Column("income_level", String(80), nullable=False))
indicators = Table("dim_indicator", META,
    Column("indicator_code", String(32), primary_key=True), Column("name", String(200), nullable=False),
    Column("unit", String(80), nullable=False), Column("source", String(120), nullable=False))
runs = Table("etl_run", META,
    Column("run_id", String(36), primary_key=True), Column("mode", String(16), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=False),
    Column("source_rows", Integer, nullable=False), Column("duplicate_rows", Integer, nullable=False),
    Column("missing_values", Integer, nullable=False), Column("inserted", Integer, nullable=False),
    Column("updated", Integer, nullable=False), Column("unchanged", Integer, nullable=False))
staging = Table("stg_indicator_observation", META,
    Column("run_id", String(36), ForeignKey("etl_run.run_id"), nullable=False),
    Column("country_code", String(3), nullable=False), Column("indicator_code", String(32), nullable=False),
    Column("year", Integer, nullable=False), Column("value", Float, nullable=True),
    Column("status", String(40), nullable=True),
    PrimaryKeyConstraint("run_id", "country_code", "indicator_code", "year"))
facts = Table("fact_country_indicator_year", META,
    Column("country_code", String(3), ForeignKey("dim_country.country_code"), nullable=False),
    Column("indicator_code", String(32), ForeignKey("dim_indicator.indicator_code"), nullable=False),
    Column("year", Integer, nullable=False), Column("value", Float, nullable=True),
    Column("status", String(40), nullable=True),
    Column("last_run_id", String(36), ForeignKey("etl_run.run_id"), nullable=False),
    PrimaryKeyConstraint("country_code", "indicator_code", "year"))

MART_SQL = """
CREATE VIEW v_country_indicator_long AS
SELECT c.name AS country, c.region, c.income_level, f.country_code,
       i.name AS indicator, f.indicator_code, f.year, f.value, f.status
FROM fact_country_indicator_year AS f
JOIN dim_country AS c ON c.country_code = f.country_code
JOIN dim_indicator AS i ON i.indicator_code = f.indicator_code;
"""
LATEST_SQL = """
CREATE VIEW v_latest_available AS
SELECT * FROM (
 SELECT c.name AS country, f.country_code, i.name AS indicator, f.indicator_code,
        f.year, f.value,
        ROW_NUMBER() OVER (PARTITION BY f.country_code, f.indicator_code ORDER BY f.year DESC) AS rn
 FROM fact_country_indicator_year f
 JOIN dim_country c ON c.country_code = f.country_code
 JOIN dim_indicator i ON i.indicator_code = f.indicator_code
 WHERE f.value IS NOT NULL
) r WHERE rn=1;
"""


def connect(url: str):
    if url.startswith("sqlite:///"):
        path = url.removeprefix("sqlite:///")
        if path != ":memory:":
            Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, future=True, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def set_fk(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    if engine.dialect.name not in {"sqlite", "postgresql"}:
        raise ValueError("Supported database dialects: sqlite and postgresql")
    return engine


def _upsert(conn, table: Table, key: list[str], payload: dict, update_fields: list[str]) -> None:
    constructor = pg_insert if conn.dialect.name == "postgresql" else sqlite_insert
    statement = constructor(table).values(**payload)
    exc = statement.excluded
    conn.execute(statement.on_conflict_do_update(index_elements=key,
                 set_={field: getattr(exc, field) for field in update_fields}))


def persist(engine, mode: str, country_rows: list[dict], indicator_rows: list[dict],
            observations: list[Any], duplicate_rows: int, source_rows: int) -> dict:
    """Commit dimensions + stage + fact changes together; any exception rolls back."""
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    counter = {"inserted": 0, "updated": 0, "unchanged": 0}
    missing = sum(o.value is None for o in observations)
    META.create_all(engine)
    with engine.begin() as conn:
        for row in country_rows:
            _upsert(conn, countries, ["country_code"], row,
                    ["name", "iso2", "region", "income_level"])
        for row in indicator_rows:
            _upsert(conn, indicators, ["indicator_code"], row,
                    ["name", "unit", "source"])
        conn.execute(insert(runs).values(run_id=run_id, mode=mode, started_at=now,
            finished_at=datetime.now(timezone.utc), source_rows=source_rows,
            duplicate_rows=duplicate_rows, missing_values=missing,
            inserted=0, updated=0, unchanged=0))
        for row in observations:
            payload = asdict(row)
            conn.execute(insert(staging).values(run_id=run_id, **payload))
            key = {"country_code": row.country_code, "indicator_code": row.indicator_code, "year": row.year}
            previous = conn.execute(select(facts.c.value, facts.c.status).where(
                (facts.c.country_code == row.country_code) &
                (facts.c.indicator_code == row.indicator_code) &
                (facts.c.year == row.year))).first()
            if previous is None:
                counter["inserted"] += 1
            elif previous.value != row.value or previous.status != row.status:
                counter["updated"] += 1
            else:
                counter["unchanged"] += 1
                continue
            fact_payload = {**payload, "last_run_id": run_id}
            _upsert(conn, facts, ["country_code", "indicator_code", "year"], fact_payload,
                    ["value", "status", "last_run_id"])
        conn.execute(runs.update().where(runs.c.run_id == run_id).values(
            finished_at=datetime.now(timezone.utc), **counter))
        for view in ["v_country_indicator_long", "v_latest_available"]:
            conn.execute(text(f"DROP VIEW IF EXISTS {view}"))
        conn.execute(text(MART_SQL))
        conn.execute(text(LATEST_SQL))
        count = conn.execute(select(text("count(*)")).select_from(facts)).scalar_one()
        integrity = conn.execute(text("SELECT COUNT(*) FROM fact_country_indicator_year f "
            "LEFT JOIN dim_country c ON c.country_code = f.country_code "
            "LEFT JOIN dim_indicator i ON i.indicator_code = f.indicator_code "
            "WHERE c.country_code IS NULL OR i.indicator_code IS NULL")).scalar_one()
        if integrity:
            raise ValueError("Post-load foreign key reconciliation failed")
    return {"run_id": run_id, "mode": mode, "source_rows": source_rows,
            "valid_unique_rows": len(observations), "duplicate_source_rows": duplicate_rows,
            "missing_value_rows": missing, "warehouse_fact_rows": count,
            "inserted": counter["inserted"], "updated": counter["updated"],
            "unchanged": counter["unchanged"], "fk_orphan_rows": integrity}
