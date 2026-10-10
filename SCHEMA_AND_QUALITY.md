# Data model and quality contract

## Primary and foreign keys

- `dim_country`: PK `country_code` (ISO3); metadata contains `iso2`, `name`, `region`, `income_level`.
- `dim_indicator`: PK `indicator_code` (official World Bank code).
- `etl_run`: PK `run_id` (UUID), with success-run counters and timestamps.
- `stg_indicator_observation`: PK `(run_id, country_code, indicator_code, year)`. Separate staged snapshots are persisted on every successful execution.
- `fact_country_indicator_year`: PK `(country_code, indicator_code, year)`, with FKs to both dimensions and most recent successful run ID.

## Validation sequence

1. **Input bounds:** country list unique and three-letter uppercase; indicators from a supported catalog; year range valid.
2. **HTTP protocol:** require complete page enumeration, coherent page numbering, API JSON list-of-two response, and full reported record count. Configured retry attempts for transient HTTP failures.
3. **Country metadata:** country codes match the requested set; reject aggregate regions and missing names/ISO2 codes.
4. **Indicator metadata:** requested code exactly matches one result, with a nonempty indicator label.
5. **Fact records:** country in scope, correct indicator, integer year in range, numeric finite value or explicit missing (`null`).
6. **Duplicate keys:** identical duplicates are counted and collapsed; conflicting duplicates are rejected instead of choosing arbitrary records.
7. **Transactional load:** dimensions, run audit, staging snapshot and fact updates are committed together, or none are committed.
8. **Post-load reconciliation:** count rows referring to missing country or indicator dimensions; abort commit if nonzero.

## Incremental/replay semantics

A second run with identical values does not insert duplicate facts. If upstream values change, fact values are updated, and the prior successful snapshot remains in the staging table. The `updated` counter increments for a changed value/status. Missing values (`NULL`) are not zero and may be superseded by future nonmissing source corrections. This is a *source-refresh upsert*, not CDC streaming.

## SQL semantics

- `v_country_indicator_long` joins the fact table with reference metadata.
- `v_latest_available` uses `ROW_NUMBER() OVER (PARTITION BY country_code, indicator_code ORDER BY year DESC)` after removing missing values.
- `sql/analysis.sql` contains nominal GDP series, same-year joins with inflation, and audit queries.
- Source indicators have different units and frequencies; any cross-indicator chart must label units and disclose missing data.

## Known scope limits

No source snapshot archiving for failed API calls; no alerting or cloud object-store lake; no ingestion benchmark; no end-to-end PostgreSQL/Airflow validation in the current execution environment. For a production system, add immutable raw sources/checksums, lineage catalog, retention policy, authentication, secrets manager, partitioning, source-update tests and data observability.