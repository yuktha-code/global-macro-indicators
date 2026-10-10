"""Ingest bounded World Bank country/indicator/year data into audited SQL warehouse."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .api import WorldBankClient
from .store import connect, persist
from .transform import (DataQualityError, parse_countries,
                        parse_indicators, parse_observations, valid_code)

INDICATORS = {
    "NY.GDP.MKTP.CD": "GDP (current US$)",
    "FP.CPI.TOTL.ZG": "Inflation, consumer prices (annual %)",
    "SL.UEM.TOTL.ZS": "Unemployment, total (% of labor force)",
    "SP.POP.TOTL": "Population, total",
}

@dataclass(frozen=True)
class Config:
    countries: tuple[str, ...] = ("IND", "BRA", "USA", "ZAF", "DEU", "JPN")
    indicators: tuple[str, ...] = tuple(INDICATORS)
    first_year: int = 2015
    last_year: int = 2024
    db_url: str = "sqlite:///data/economic_warehouse.sqlite"
    mode: str = "live"

    def validate(self) -> None:
        if not self.countries or len(set(self.countries)) != len(self.countries):
            raise ValueError("Country list must be nonempty and unique")
        for country in self.countries:
            if valid_code(country) != country:
                raise ValueError("Country ISO3 codes must be uppercase")
        if not self.indicators or len(set(self.indicators)) != len(self.indicators):
            raise ValueError("Indicator list must be nonempty and unique")
        if any(code not in INDICATORS for code in self.indicators):
            raise ValueError("Unsupported indicator code")
        if not (1960 <= self.first_year <= self.last_year <= 2100):
            raise ValueError("Invalid year range")


def run(config: Config, client=None) -> dict:
    """Validate *all* API data before touching the database."""
    config.validate()
    client = client or WorldBankClient()
    country_rows = parse_countries(client.countries(config.countries), config.countries)
    indicator_rows = []
    observations = []
    duplicate_rows = source_rows = 0
    for code in config.indicators:
        indicator_rows.append(parse_indicators(client.indicator(code), code))
        raw = client.observations(config.countries, code, config.first_year, config.last_year)
        rows, duplicates = parse_observations(raw, config.countries, code,
                                              config.first_year, config.last_year)
        source_rows += len(raw)
        duplicate_rows += duplicates
        observations.extend(rows)
    if not observations:
        raise DataQualityError("No usable observations returned; nothing loaded")
    engine = connect(config.db_url)
    try:
        report = persist(engine, config.mode, country_rows, indicator_rows,
                         observations, duplicate_rows, source_rows)
    finally:
        engine.dispose()
    return {**report, "countries": list(config.countries),
            "indicators": list(config.indicators),
            "year_range": [config.first_year, config.last_year],
            "source": "World Bank Indicators API v2",
            "data_kind": "illustrative offline fixture" if config.mode == "demo" else "live API",
            "note": "NULL represents upstream missing value, not zero."}


class DemoClient:
    """Fixture response adapter; DEMO VALUES ARE ARTIFICIAL, NOT WORLD BANK DATA."""
    def __init__(self, filename: str | Path):
        self.fixture = json.loads(Path(filename).read_text(encoding="utf-8"))
    def countries(self, codes):
        return self.fixture["countries"]
    def indicator(self, code):
        return self.fixture["indicators"][code]
    def observations(self, codes, indicator, first_year, last_year):
        return self.fixture["observations"][indicator]
