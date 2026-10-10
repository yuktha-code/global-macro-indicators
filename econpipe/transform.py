"""Fail-closed source validation; missing values are preserved as SQL NULL."""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any


class DataQualityError(ValueError):
    pass


@dataclass(frozen=True)
class Observation:
    country_code: str
    indicator_code: str
    year: int
    value: float | None
    status: str | None


def valid_code(code: str) -> str:
    code = code.upper().strip()
    if not re.fullmatch(r"[A-Z]{3}", code):
        raise DataQualityError(f"Invalid country code: {code!r}")
    return code


def parse_countries(items: list[dict], requested: tuple[str, ...]) -> list[dict]:
    valid = set(requested)
    found: dict[str, dict] = {}
    for item in items:
        code = valid_code(str(item.get("id", "")))
        if code not in valid:
            continue
        region = item.get("region", {})
        region_name = region.get("value") if isinstance(region, dict) else None
        if not region_name or (isinstance(region, dict) and region.get("id") == "NA"):
            raise DataQualityError(f"Country metadata missing/aggregate for {code}")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise DataQualityError(f"Country name missing: {code}")
        iso2 = item.get("iso2Code")
        if not isinstance(iso2, str) or len(iso2) != 2:
            raise DataQualityError(f"ISO-2 code missing: {code}")
        normalized = {"country_code": code, "iso2": iso2, "name": name,
                      "region": region_name,
                      "income_level": (item.get("incomeLevel") or {}).get("value", "Unknown")}
        if code in found and normalized != found[code]:
            raise DataQualityError(f"Conflicting country metadata: {code}")
        found[code] = normalized
    if set(found) != valid:
        raise DataQualityError(f"Missing countries: {sorted(valid - set(found))}")
    return [found[c] for c in sorted(found)]


def parse_indicators(items: list[dict], code: str) -> dict:
    found = [x for x in items if x.get("id") == code]
    if len(found) != 1 or not found[0].get("name"):
        raise DataQualityError(f"Missing/ambiguous indicator metadata: {code}")
    x = found[0]
    return {"indicator_code": code, "name": x["name"], "unit": x.get("unit") or "",
            "source": (x.get("source") or {}).get("value") or "World Development Indicators"}


def parse_observations(items: list[dict], codes: tuple[str, ...], indicator: str,
                       first_year: int, last_year: int) -> tuple[list[Observation], int]:
    deduped: dict[tuple[str, str, int], Observation] = {}
    duplicates = 0
    for raw in items:
        country = valid_code(str(raw.get("countryiso3code") or ""))
        if country not in codes:
            raise DataQualityError(f"Unexpected country: {country}")
        indicator_obj = raw.get("indicator") or {}
        if indicator_obj.get("id") != indicator:
            raise DataQualityError(f"Incorrect indicator for {country}: {indicator_obj}")
        try:
            year = int(raw["date"])
        except (ValueError, TypeError, KeyError) as exc:
            raise DataQualityError("Invalid date/year") from exc
        if not first_year <= year <= last_year:
            raise DataQualityError(f"Unexpected year: {year}")
        v = raw.get("value")
        if v is not None:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise DataQualityError("Non-numeric indicator value")
            v = float(v)
            if not math.isfinite(v):
                raise DataQualityError("Nonfinite indicator value")
        status = raw.get("obs_status") or None
        obj = Observation(country, indicator, year, v, status)
        key = (country, indicator, year)
        if key in deduped:
            if deduped[key] != obj:
                raise DataQualityError(f"Conflicting duplicate source observation: {key}")
            duplicates += 1
        else:
            deduped[key] = obj
    return sorted(deduped.values(), key=lambda a: (a.country_code, a.indicator_code, a.year)), duplicates
