import pytest
from econpipe.transform import DataQualityError, parse_observations, parse_countries


def row(value, country="IND", year="2021", indicator="NY.GDP.MKTP.CD"):
    return {"countryiso3code":country,"indicator":{"id":indicator},"date":year,"value":value,"obs_status":""}


def test_null_value_retained_and_duplicate_deduped():
    rows, dupes = parse_observations([row(None), row(None)], ("IND",), "NY.GDP.MKTP.CD",2020,2024)
    assert len(rows) == 1 and dupes == 1 and rows[0].value is None


def test_conflicting_duplicate_rejected():
    with pytest.raises(DataQualityError, match="Conflicting duplicate"):
        parse_observations([row(2),row(3)],("IND",),"NY.GDP.MKTP.CD",2020,2024)


def test_bogus_numeric_rejected():
    for n in [float("nan"), float("inf"), "123", True]:
        with pytest.raises(DataQualityError):
            parse_observations([row(n)],("IND",),"NY.GDP.MKTP.CD",2020,2024)


def test_out_of_scope_year_and_country_rejected():
    for bad in [row(3, year="2018"),row(3,country="USA")]:
        with pytest.raises(DataQualityError):
            parse_observations([bad],("IND",),"NY.GDP.MKTP.CD",2020,2024)


def test_aggregate_country_rejected():
    with pytest.raises(DataQualityError, match="aggregate"):
        parse_countries([{"id":"IND","iso2Code":"IN","name":"India",
                          "region":{"id":"NA","value":"Aggregates"}}],("IND",))
