"""Optional public-data Kafka, Hive-compatible Parquet and Azure Blob exercises.
The core batch pipeline does not require these optional services.
"""
import hashlib
import json
from pathlib import Path
from sqlalchemy import text
from .store import connect

def warehouse_rows(db_url):
    db=connect(db_url)
    try:
        with db.connect() as c:
            return [dict(r) for r in c.execute(text(
                "SELECT country_code,indicator_code,year,value,status "
                "FROM fact_country_indicator_year ORDER BY year,country_code,indicator_code"
            )).mappings()]
    finally:
        db.dispose()

def kafka_event(row):
    """Deterministic event ID and stable business key; no PII."""
    key=f"{row['country_code']}|{row['indicator_code']}|{row['year']}"
    body={"schema_version":1,"source":"world-bank-wdi","key":key,
          "country_code":row["country_code"],"indicator_code":row["indicator_code"],
          "year":int(row["year"]),"value":row["value"],"status":row["status"]}
    canonical=json.dumps(body,sort_keys=True,separators=(",",":"),allow_nan=False)
    body["event_id"]=hashlib.sha256(canonical.encode()).hexdigest()
    return key, json.dumps(body,sort_keys=True,allow_nan=False).encode()

def publish_kafka(db_url, bootstrap="localhost:9092", topic="macro-observations"):
    """Kafka producer delivery acknowledgements; not exactly-once processing."""
    from confluent_kafka import Producer
    records=warehouse_rows(db_url)
    if not records: raise ValueError("Empty SQL warehouse")
    producer=Producer({"bootstrap.servers":bootstrap,"enable.idempotence":True,
                       "acks":"all","message.timeout.ms":25000})
    failures=[]
    acknowledged=[]
    def delivered(err,msg):
        if err: failures.append(str(err))
        else: acknowledged.append(msg.key())
    for record in records:
        key,data=kafka_event(record)
        producer.produce(topic,key=key.encode(),value=data,on_delivery=delivered)
        producer.poll(0)
    outstanding=producer.flush(40)
    if failures or outstanding or len(acknowledged)!=len(records):
        raise RuntimeError(f"Delivery failures={failures}; outstanding={outstanding}")
    return {"topic":topic,"acknowledged":len(acknowledged),
            "semantics":"idempotent producer, not end-to-end exactly once"}

def export_hive_partitions(db_url, destination):
    """Real Parquet files with year=YYYY folders. Does not execute Apache Hive."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    rows=warehouse_rows(db_url)
    if not rows: raise ValueError("Empty SQL warehouse")
    target=Path(destination)
    groups={}
    for r in rows:
        r=dict(r)
        year=int(r.pop("year"))
        groups.setdefault(year,[]).append(r)
    schema=pa.schema([("country_code",pa.string()),("indicator_code",pa.string()),
                      ("value",pa.float64()),("status",pa.string())])
    for year,content in sorted(groups.items()):
        folder=target/f"year={year}"
        folder.mkdir(parents=True,exist_ok=True)
        pq.write_table(pa.Table.from_pylist(content,schema=schema),
                       folder/"observations.parquet",compression="snappy")
    return {"total_rows":len(rows),"years":sorted(groups),"partition_count":len(groups),
            "format":"Parquet with Hive partition naming"}

def azure_upload_parquet(directory, connection_string, container="macro-indicators",
                         prefix="world-bank-wdi"):
    """Azure Blob SDK. Use Azurite locally; a real Azure account needs credentials."""
    from azure.storage.blob import BlobServiceClient
    from azure.core.exceptions import ResourceExistsError
    source=Path(directory)
    if not source.is_dir(): raise ValueError("Source directory missing")
    paths=sorted(source.rglob("*.parquet"))
    if not paths: raise ValueError("No Parquet files found")
    client=BlobServiceClient.from_connection_string(connection_string)
    cc=client.get_container_client(container)
    try: cc.create_container()
    except ResourceExistsError: pass
    for path in paths:
        with path.open("rb") as f:
            cc.upload_blob(prefix.strip("/")+"/"+path.relative_to(source).as_posix(),
                           f,overwrite=True)
    return {"uploaded":len(paths),"container":container,"api":"Azure Blob SDK"}
