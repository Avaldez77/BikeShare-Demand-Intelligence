from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DATASET_DOI = "https://doi.org/10.24432/C5W894"
DATASET_LICENSE = "CC BY 4.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_delivery(
    output_dir: Path,
    archive_hash: str,
    source_file_hash: str,
    quality: dict[str, Any],
    analytics: dict[str, Any],
    model_metrics_path: Path,
) -> dict[str, Any]:
    delivery_dir = output_dir / "delivery"
    delivery_dir.mkdir(parents=True, exist_ok=True)
    model_metrics = json.loads(model_metrics_path.read_text(encoding="utf-8"))
    report_path = output_dir / "analytics" / "briefing.html"
    artifacts = [
        output_dir / "warehouse" / "warehouse.duckdb",
        output_dir / "warehouse" / "hourly_demand.csv",
        output_dir / "warehouse" / "daily_demand.csv",
        output_dir / "warehouse" / "quality_summary.json",
        output_dir / "analytics" / "kpi_summary.json",
        output_dir / "analytics" / "season_breakdown.csv",
        output_dir / "analytics" / "hourly_profile.csv",
        output_dir / "analytics" / "daily_demand.png",
        output_dir / "analytics" / "hourly_demand.png",
        report_path,
        model_metrics_path,
        model_metrics_path.parent / "forecast_predictions.csv",
    ]
    missing = [str(path) for path in artifacts if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Cannot package missing pipeline outputs: {', '.join(missing)}")

    manifest = {
        "dataset_doi": DATASET_DOI,
        "dataset_license": DATASET_LICENSE,
        "source_archive_sha256": archive_hash,
        "hourly_csv_sha256": source_file_hash,
        "quality_status": quality["quality_status"],
        "artifacts": [
            {"path": str(path.relative_to(output_dir)), "sha256": _sha256(path)}
            for path in artifacts
        ],
    }
    manifest_path = delivery_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    audit_events = [
        {
            "event_id": "01-acquire",
            "stage": "acquire",
            "status": "completed",
            "source_archive_sha256": archive_hash,
            "hourly_csv_sha256": source_file_hash,
        },
        {
            "event_id": "02-quality",
            "stage": "quality_gate",
            "status": quality["quality_status"],
            "bronze_rows": quality["bronze_rows"],
            "silver_rows": quality["silver_rows"],
            "quarantined_rows": quality["quarantined_rows"],
        },
        {
            "event_id": "03-analytics",
            "stage": "analytics",
            "status": "completed",
            "observed_days": analytics["observed_days"],
            "total_rentals": analytics["total_rentals"],
        },
        {
            "event_id": "04-forecast",
            "stage": "forecast",
            "status": "completed",
            "holdout_start": model_metrics["holdout_start"],
            "forecast_rows": model_metrics["test_rows"],
        },
        {
            "event_id": "05-delivery",
            "stage": "dry_run_delivery",
            "status": "preview_created",
            "email_sent": False,
            "manifest": str(manifest_path.relative_to(output_dir)),
        },
    ]
    audit_path = delivery_dir / "audit.jsonl"
    audit_path.write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in audit_events),
        encoding="utf-8",
    )
    email_path = delivery_dir / "notification_preview.eml"
    email_path.write_text(
        "\n".join(
            [
                "To: portfolio-review@example.invalid",
                "Subject: Capital Bikeshare demand report (dry run)",
                "MIME-Version: 1.0",
                "Content-Type: text/plain; charset=utf-8",
                "",
                "This is a local notification preview. No email was sent.",
                f"Report: {report_path.relative_to(output_dir)}",
                f"Forecast metrics: {model_metrics_path.relative_to(output_dir)}",
                f"Manifest: {manifest_path.relative_to(output_dir)}",
                f"Forecast holdout begins: {model_metrics['holdout_start']}",
                f"Model MAE: {model_metrics['model']['mae']:.2f}",
                f"Hour-of-week baseline MAE: {model_metrics['baseline']['mae']:.2f}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    summary = {
        "delivery_status": "preview_created",
        "email_sent": False,
        "report_path": str(report_path),
        "manifest_path": str(manifest_path),
        "audit_path": str(audit_path),
        "notification_preview_path": str(email_path),
    }
    (delivery_dir / "delivery_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary
