from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from bikeshare.warehouse import build_warehouse


FIELDS = [
    "instant",
    "dteday",
    "season",
    "yr",
    "mnth",
    "hr",
    "holiday",
    "weekday",
    "workingday",
    "weathersit",
    "temp",
    "atemp",
    "hum",
    "windspeed",
    "casual",
    "registered",
    "cnt",
]


class WarehouseTests(unittest.TestCase):
    def test_builds_gold_tables_and_quarantines_inconsistent_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "hour.csv"
            rows = [
                [1, "2011-01-01", 1, 0, 1, 0, 0, 6, 0, 1, 0.24, 0.28, 0.81, 0.0, 3, 13, 16],
                [2, "2011-01-01", 1, 0, 1, 1, 0, 6, 0, 1, 0.22, 0.27, 0.80, 0.0, 8, 32, 40],
                [3, "2011-01-01", 1, 0, 1, 2, 0, 6, 0, 1, 0.22, 0.27, 0.80, 0.0, 8, 32, 99],
                [4, "not-a-date", 1, 0, 1, 3, 0, 6, 0, 1, 0.22, 0.27, 0.80, 0.0, 8, 32, 40],
            ]
            with source.open("w", newline="", encoding="utf-8") as target:
                writer = csv.writer(target)
                writer.writerow(FIELDS)
                writer.writerows(rows)

            summary = build_warehouse(source, root / "warehouse")

            self.assertEqual(summary["bronze_rows"], 4)
            self.assertEqual(summary["silver_rows"], 2)
            self.assertEqual(summary["quarantined_rows"], 2)
            self.assertEqual(summary["quality_status"], "review_required")
            self.assertEqual(
                summary["rejection_reasons"],
                [
                    {"reason": "inconsistent_demand_total", "rows": 1},
                    {"reason": "invalid_or_missing_value", "rows": 1},
                ],
            )
            self.assertTrue((root / "warehouse" / "warehouse.duckdb").is_file())
            with (root / "warehouse" / "hourly_demand.csv").open(
                newline="", encoding="utf-8"
            ) as source_file:
                hourly = list(csv.DictReader(source_file))
            self.assertEqual(len(hourly), 2)
            with (root / "warehouse" / "daily_demand.csv").open(
                newline="", encoding="utf-8"
            ) as source_file:
                daily = list(csv.DictReader(source_file))
            self.assertEqual(float(daily[0]["total_rentals"]), 56.0)


if __name__ == "__main__":
    unittest.main()
