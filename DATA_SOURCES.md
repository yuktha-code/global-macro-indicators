# Data lineage and provenance

**Source:** World Bank, World Development Indicators (source ID 2), public API v2. Official developer documentation:

- https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
- https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures
- https://datahelpdesk.worldbank.org/knowledgebase/articles/898590-country-api-queries
- https://datahelpdesk.worldbank.org/knowledgebase/articles/898599-indicator-api-queries

A World Bank API key is not required. `econpipe/api.py` requests JSON (`format=json`), uses `per_page` and `page` until all records have been received, and raises an error if the number of records does not match the response's declared total. All errors stop the pipeline; there is no substitute/fake data fallback in `run` mode.

## Indicator catalog

| Code | Meaning | Units / caveats |
| --- | --- | --- |
| `NY.GDP.MKTP.CD` | GDP (current US$) | Nominal, not inflation-adjusted |
| `FP.CPI.TOTL.ZG` | Inflation, consumer prices | Annual percentage |
| `SL.UEM.TOTL.ZS` | Unemployment, total | % of labor force; source methodology should be checked before economic interpretation |
| `SP.POP.TOTL` | Population, total | Persons |

## Distinguishing data source from fixture

The file `tests/fixtures/demo_api.json` is intentionally constructed to resemble a typical World Bank API response. Its numeric values (e.g., 123.0 for India's 2021 GDP) are **not actual World Bank observations**. They exist only to exercise the database and quality contracts while disconnected from the internet. No results from demo mode may be presented as country statistics.

For real provenance, run `python -m econpipe.cli run`, save its JSON audit report and note execution date, requested countries, indicator codes and years. Live values remain managed by the publisher and may be revised over time.

## Country handling

The pipeline explicitly asks for six country codes, parses ISO3 and ISO2 country metadata, and rejects regional aggregates. Missing values remain SQL `NULL`. Modelled year is the source data year, not the date the API was queried.