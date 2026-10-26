from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb


WAREHOUSE_DIR = Path(__file__).resolve().parent


def build_warehouse(input_csv: Path, output_dir: Path) -> dict[str, Any]:
    if not input_csv.is_file():
        raise FileNotFoundError(f"Hourly data file does not exist: {input_csv}")
    output_dir.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(output_dir / "warehouse.duckdb"))
    try:
        connection.execute(
            """
            CREATE OR REPLACE TABLE bronze_hourly AS
            SELECT ROW_NUMBER() OVER () AS source_row, *
            FROM read_csv(?, header = true, all_varchar = true)
            """,
            [str(input_csv.resolve())],
        )
        connection.execute(
            """
            CREATE OR REPLACE TABLE classified_hourly AS
            WITH typed AS (
                SELECT
                    source_row,
                    TRY_CAST(instant AS INTEGER) AS instant,
                    TRY_STRPTIME(dteday, '%Y-%m-%d')::DATE AS service_date,
                    TRY_CAST(season AS INTEGER) AS season,
                    TRY_CAST(yr AS INTEGER) AS year_code,
                    TRY_CAST(mnth AS INTEGER) AS month,
                    TRY_CAST(hr AS INTEGER) AS hour,
                    TRY_CAST(holiday AS INTEGER) AS holiday,
                    TRY_CAST(weekday AS INTEGER) AS weekday,
                    TRY_CAST(workingday AS INTEGER) AS workingday,
                    TRY_CAST(weathersit AS INTEGER) AS weather,
                    TRY_CAST(temp AS DOUBLE) AS temperature,
                    TRY_CAST(atemp AS DOUBLE) AS apparent_temperature,
                    TRY_CAST(hum AS DOUBLE) AS humidity,
                    TRY_CAST(windspeed AS DOUBLE) AS windspeed,
                    TRY_CAST(casual AS INTEGER) AS casual,
                    TRY_CAST(registered AS INTEGER) AS registered,
                    TRY_CAST(cnt AS INTEGER) AS count,
                    ROW_NUMBER() OVER (PARTITION BY instant ORDER BY source_row) AS row_rank
                FROM bronze_hourly
            )
            SELECT *,
                CASE
                    WHEN row_rank > 1 THEN 'duplicate_instant'
                    WHEN instant IS NULL OR service_date IS NULL
                      OR season IS NULL OR year_code IS NULL OR month IS NULL
                      OR hour IS NULL OR holiday IS NULL OR weekday IS NULL
                      OR workingday IS NULL OR weather IS NULL
                      OR temperature IS NULL OR apparent_temperature IS NULL
                      OR humidity IS NULL OR windspeed IS NULL
                      OR casual IS NULL OR registered IS NULL OR count IS NULL
                      THEN 'invalid_or_missing_value'
                    WHEN season NOT BETWEEN 1 AND 4 THEN 'invalid_season'
                    WHEN year_code NOT IN (0, 1) THEN 'invalid_year_code'
                    WHEN month NOT BETWEEN 1 AND 12 THEN 'invalid_month'
                    WHEN hour NOT BETWEEN 0 AND 23 THEN 'invalid_hour'
                    WHEN holiday NOT IN (0, 1) OR workingday NOT IN (0, 1) THEN 'invalid_calendar_flag'
                    WHEN weekday NOT BETWEEN 0 AND 6 THEN 'invalid_weekday'
                    WHEN weather NOT BETWEEN 1 AND 4 THEN 'invalid_weather'
                    WHEN temperature NOT BETWEEN 0 AND 1
                      OR apparent_temperature NOT BETWEEN 0 AND 1
                      OR humidity NOT BETWEEN 0 AND 1
                      OR windspeed NOT BETWEEN 0 AND 1 THEN 'invalid_normalized_weather'
                    WHEN casual < 0 OR registered < 0 OR count < 0 THEN 'negative_demand'
                    WHEN count <> casual + registered THEN 'inconsistent_demand_total'
                    ELSE NULL
                END AS rejection_reason
            FROM typed
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE TABLE quarantine AS
            SELECT source_row, instant, service_date, rejection_reason
            FROM classified_hourly
            WHERE rejection_reason IS NOT NULL
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE TABLE silver_hourly AS
            SELECT instant, service_date, season, year_code, month, hour, holiday,
                   weekday, workingday, weather, temperature, apparent_temperature,
                   humidity, windspeed, casual, registered, count
            FROM classified_hourly
            WHERE rejection_reason IS NULL
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE TABLE gold_daily AS
            SELECT
                service_date,
                season,
                year_code,
                SUM(count) AS total_rentals,
                SUM(casual) AS casual_rentals,
                SUM(registered) AS registered_rentals,
                AVG(temperature) AS mean_temperature,
                AVG(humidity) AS mean_humidity,
                COUNT(*) AS observed_hours
            FROM silver_hourly
            GROUP BY service_date, season, year_code
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE TABLE gold_hourly_profile AS
            SELECT weekday, hour, workingday,
                   AVG(count) AS mean_rentals,
                   MEDIAN(count) AS median_rentals,
                   COUNT(*) AS observed_hours
            FROM silver_hourly
            GROUP BY weekday, hour, workingday
            """
        )

        silver_count = connection.execute("SELECT COUNT(*) FROM silver_hourly").fetchone()[0]
        bronze_count = connection.execute("SELECT COUNT(*) FROM bronze_hourly").fetchone()[0]
        quarantine_rows = connection.execute(
            """
            SELECT rejection_reason, COUNT(*) AS rejected_rows
            FROM quarantine
            GROUP BY rejection_reason
            ORDER BY rejection_reason
            """
        ).fetchall()
        hourly = connection.execute(
            """
            SELECT instant, service_date, season, year_code, month, hour, holiday,
                   weekday, workingday, weather, temperature, apparent_temperature,
                   humidity, windspeed, casual, registered, count
            FROM silver_hourly
            ORDER BY instant
            """
        ).df()
        daily = connection.execute(
            "SELECT * FROM gold_daily ORDER BY service_date"
        ).df()
        hourly.to_csv(output_dir / "hourly_demand.csv", index=False, lineterminator="\n")
        daily.to_csv(output_dir / "daily_demand.csv", index=False, lineterminator="\n")
        summary = {
            "bronze_rows": bronze_count,
            "silver_rows": silver_count,
            "quarantined_rows": bronze_count - silver_count,
            "quality_status": "passed" if bronze_count == silver_count else "review_required",
            "rejection_reasons": [
                {"reason": reason, "rows": count} for reason, count in quarantine_rows
            ],
        }
        (output_dir / "quality_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )
        return summary
    finally:
        connection.close()
