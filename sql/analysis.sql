-- Works in SQLite and PostgreSQL after running the ETL.
-- Latest non-null observation for each country/indicator (year is not uniform)
SELECT country, indicator, year, value
FROM v_latest_available
ORDER BY country, indicator;

-- GDP history by country: values are current USD, not inflation-adjusted.
SELECT country, year, value AS gdp_current_usd
FROM v_country_indicator_long
WHERE indicator_code = 'NY.GDP.MKTP.CD' AND value IS NOT NULL
ORDER BY country, year;

-- Join GDP and inflation on the same country/year; missing values remain NULL.
SELECT g.country, g.year, g.value AS gdp_current_usd,
       p.value AS inflation_annual_pct
FROM v_country_indicator_long g
LEFT JOIN v_country_indicator_long p
 ON p.country_code=g.country_code AND p.year=g.year
 AND p.indicator_code='FP.CPI.TOTL.ZG'
WHERE g.indicator_code='NY.GDP.MKTP.CD'
ORDER BY g.country, g.year;

-- Audit most recent source processing; unchanged reruns should have inserted=0, updated=0.
SELECT run_id, mode, source_rows, duplicate_rows, missing_values,
       inserted, updated, unchanged, finished_at
FROM etl_run ORDER BY finished_at DESC;
