-- Example DDL for an Apache Hive cluster, not proof that HiveServer2 ran.
-- Provide macro_location at execution time (e.g. via --hivevar macro_location=...).
CREATE DATABASE IF NOT EXISTS macro_research;
USE macro_research;
CREATE EXTERNAL TABLE IF NOT EXISTS annual_macro_indicators (
  country_code STRING,
  indicator_code STRING,
  value DOUBLE,
  status STRING
) PARTITIONED BY (year INT)
STORED AS PARQUET
LOCATION '${hivevar:macro_location}';
MSCK REPAIR TABLE annual_macro_indicators;
SELECT year, indicator_code, COUNT(*) AS observations
FROM annual_macro_indicators
GROUP BY year, indicator_code
ORDER BY year, indicator_code;
