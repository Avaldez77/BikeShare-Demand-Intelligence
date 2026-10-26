from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from bikeshare.analytics import append_forecast_results, build_analytics
from bikeshare.delivery import create_delivery


class AnalyticsAndDeliveryTests(unittest.TestCase):
    def test_builds_briefing_and_dry_run_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            warehouse_dir = root / "warehouse"
            analytics_dir = root / "analytics"
            model_dir = root / "model"
            warehouse_dir.mkdir()
            model_dir.mkdir()

            with (warehouse_dir / "daily_demand.csv").open(
                "w", newline="", encoding="utf-8"
            ) as target:
                writer = csv.DictWriter(
                    target,
                    fieldnames=[
                        "service_date",
                        "season",
                        "year_code",
                        "total_rentals",
                        "casual_rentals",
                        "registered_rentals",
                        "mean_temperature",
                        "mean_humidity",
                        "observed_hours",
                    ],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "service_date": "2011-01-01",
                            "season": 1,
                            "year_code": 0,
                            "total_rentals": 100,
                            "casual_rentals": 20,
                            "registered_rentals": 80,
                            "mean_temperature": 0.2,
                            "mean_humidity": 0.7,
                            "observed_hours": 24,
                        },
                        {
                            "service_date": "2011-01-02",
                            "season": 1,
                            "year_code": 0,
                            "total_rentals": 200,
                            "casual_rentals": 50,
                            "registered_rentals": 150,
                            "mean_temperature": 0.3,
                            "mean_humidity": 0.6,
                            "observed_hours": 24,
                        },
                    ]
                )
            with (warehouse_dir / "hourly_demand.csv").open(
                "w", newline="", encoding="utf-8"
            ) as target:
                writer = csv.DictWriter(
                    target,
                    fieldnames=["hour", "workingday", "count"],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {"hour": hour, "workingday": day_type, "count": hour * 10}
                        for day_type in (0, 1)
                        for hour in range(24)
                    ]
                )

            summary = build_analytics(warehouse_dir, analytics_dir)
            self.assertEqual(summary["total_rentals"], 300)
            self.assertEqual(summary["peak_demand_date"], "2011-01-02")
            self.assertTrue((analytics_dir / "briefing.html").is_file())
            self.assertTrue((analytics_dir / "daily_demand.png").is_file())

            (root / "warehouse" / "warehouse.duckdb").write_bytes(b"database")
            for name in (
                "quality_summary.json",
                "hourly_demand.csv",
            ):
                (warehouse_dir / name).write_text("fixture\n", encoding="utf-8")
            (analytics_dir / "season_breakdown.csv").write_text(
                "season_name\nWinter\n", encoding="utf-8"
            )
            (analytics_dir / "hourly_profile.csv").write_text(
                "hour\n0\n", encoding="utf-8"
            )
            (analytics_dir / "hourly_demand.png").write_bytes(b"chart")
            metrics_path = model_dir / "forecast_metrics.json"
            metrics_path.write_text(
                json.dumps(
                    {
                        "holdout_start": "2012-12-01",
                        "holdout_end": "2012-12-28",
                        "test_rows": 24,
                        "model": {"mae": 10.0, "rmse": 14.0, "wape": 0.1},
                        "baseline": {"mae": 12.0, "rmse": 15.0, "wape": 0.12},
                    }
                ),
                encoding="utf-8",
            )
            append_forecast_results(analytics_dir, metrics_path)
            briefing = (analytics_dir / "briefing.html").read_text(encoding="utf-8")
            self.assertIn('id="forecast-results"', briefing)
            self.assertIn("Hour-of-week baseline", briefing)
            (model_dir / "forecast_predictions.csv").write_text(
                "actual,prediction\n20,21\n", encoding="utf-8"
            )

            delivery = create_delivery(
                root,
                "source-hash",
                "csv-hash",
                {"quality_status": "passed", "bronze_rows": 2, "silver_rows": 2,
                 "quarantined_rows": 0},
                summary,
                metrics_path,
            )

            self.assertFalse(delivery["email_sent"])
            manifest = json.loads(Path(delivery["manifest_path"]).read_text())
            self.assertEqual(manifest["dataset_license"], "CC BY 4.0")
            self.assertTrue(all(len(item["sha256"]) == 64 for item in manifest["artifacts"]))
            audit = Path(delivery["audit_path"]).read_text(encoding="utf-8")
            self.assertIn('"email_sent": false', audit)
            self.assertIn("No email was sent", Path(
                delivery["notification_preview_path"]
            ).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
