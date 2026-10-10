import json
from pathlib import Path
from econpipe.integration_lab import kafka_event,warehouse_rows,export_hive_partitions
from econpipe.pipeline import run, Config, DemoClient

def _demo(tmp_path):
    db="sqlite:///"+str(tmp_path/"macro.sqlite")
    fixture=Path(__file__).parent/"fixtures"/"demo_api.json"
    config=Config(countries=("IND","BRA"),indicators=("NY.GDP.MKTP.CD","FP.CPI.TOTL.ZG"),
                  first_year=2021,last_year=2022,db_url=db,mode="demo")
    run(config,DemoClient(fixture))
    return db

def test_kafka_event_repeatable_null():
    row={"country_code":"IND","indicator_code":"NY.GDP.MKTP.CD",
         "year":2022,"value":None,"status":None}
    k,v=kafka_event(row)
    assert k=="IND|NY.GDP.MKTP.CD|2022"
    assert json.loads(v)["value"] is None
    assert kafka_event(row)==(k,v)

def test_warehouse_read_and_hive_export(tmp_path):
    import pytest
    pytest.importorskip('duckdb')
    pytest.importorskip('pyarrow')
    import duckdb
    db=_demo(tmp_path)
    assert len(warehouse_rows(db))==8
    path=tmp_path/"hive"
    report=export_hive_partitions(db,path)
    assert report["partition_count"]==2 and report["total_rows"]==8
    con=duckdb.connect()
    q="select count(*), count(distinct year) from read_parquet(?, hive_partitioning=true)"
    result=con.execute(q,[str(path/"*"/"*.parquet")]).fetchone()
    assert result==(8,2)
    export_hive_partitions(db,path)
    assert con.execute(q,[str(path/"*"/"*.parquet")]).fetchone()==result

def test_hive_external_table_ddl():
    ddl=(Path(__file__).parent.parent/"sql"/"hive_external_table.sql").read_text()
    assert "PARTITIONED BY (year INT)" in ddl
    assert "STORED AS PARQUET" in ddl
    assert "MSCK REPAIR TABLE" in ddl
