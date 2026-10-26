from __future__ import annotations

from pathlib import Path
from typing import Any

from bikeshare.acquire import acquire_dataset
from bikeshare.analytics import append_forecast_results, build_analytics
from bikeshare.delivery import create_delivery
from bikeshare.model import run_forecast
from bikeshare.warehouse import build_warehouse


def run_pipeline(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    raw_path, archive_hash, source_file_hash, source_rows = acquire_dataset(
        output_dir / "raw"
    )
    quality = build_warehouse(raw_path, output_dir / "warehouse")
    if quality["quality_status"] != "passed":
        raise ValueError(
            "Quality gate failed: "
            f"{quality['quarantined_rows']} of {quality['bronze_rows']} records "
            "were quarantined; review warehouse/quality_summary.json"
        )
    analytics = build_analytics(output_dir / "warehouse", output_dir / "analytics")
    model = run_forecast(
        output_dir / "warehouse" / "hourly_demand.csv",
        output_dir / "model",
    )
    append_forecast_results(
        output_dir / "analytics",
        Path(model["metrics_path"]),
    )
    delivery = create_delivery(
        output_dir,
        archive_hash,
        source_file_hash,
        quality,
        analytics,
        Path(model["metrics_path"]),
    )
    return {
        "source_rows": source_rows,
        "quality": quality,
        "analytics": analytics,
        "model_metrics_path": model["metrics_path"],
        "report_path": delivery["report_path"],
        "delivery": delivery,
    }
