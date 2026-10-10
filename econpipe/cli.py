"""Example: python -m econpipe.cli run --db-url sqlite:///data/warehouse.sqlite"""
import argparse
import json
import os
from pathlib import Path

from .pipeline import Config, DemoClient, run
from .store import connect
from sqlalchemy import text


def main():
    parser = argparse.ArgumentParser(description="World Bank economic indicator ETL")
    sub = parser.add_subparsers(dest="action", required=True)
    for cmd in ["run", "demo", "report"]:
        p = sub.add_parser(cmd)
        p.add_argument("--db-url", default=os.getenv("DATABASE_URL", "sqlite:///data/economic_warehouse.sqlite"))
        p.add_argument("--output", default="results/last_run.json")
        if cmd == "run":
            p.add_argument("--countries", default="IND,BRA,USA,ZAF,DEU,JPN")
            p.add_argument("--indicators", default="NY.GDP.MKTP.CD,FP.CPI.TOTL.ZG,SL.UEM.TOTL.ZS,SP.POP.TOTL")
            p.add_argument("--first-year", type=int, default=2015)
            p.add_argument("--last-year", type=int, default=2024)
    args = parser.parse_args()
    if args.action == "report":
        engine = connect(args.db_url)
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT country, indicator, year, value "
                "FROM v_latest_available ORDER BY country, indicator")).mappings().all()
            print(json.dumps([dict(r) for r in rows], indent=2))
        engine.dispose()
        return
    if args.action == "demo":
        cfg = Config(countries=("IND", "BRA"),
                     indicators=("NY.GDP.MKTP.CD", "FP.CPI.TOTL.ZG"),
                     first_year=2021, last_year=2022, db_url=args.db_url, mode="demo")
        client = DemoClient(Path(__file__).resolve().parent.parent / "tests/fixtures/demo_api.json")
    else:
        cfg = Config(countries=tuple(x.strip().upper() for x in args.countries.split(",")),
                     indicators=tuple(x.strip() for x in args.indicators.split(",")),
                     first_year=args.first_year, last_year=args.last_year,
                     db_url=args.db_url, mode="live")
        client = None
    report = run(cfg, client)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
