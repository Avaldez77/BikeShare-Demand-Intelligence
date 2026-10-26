from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd


MODEL_SCRIPT = Path(__file__).resolve().parent.parent / "R" / "forecast.R"


def run_forecast(hourly_csv: Path, output_dir: Path) -> dict[str, str]:
    if not hourly_csv.is_file():
        raise FileNotFoundError(f"Validated hourly data does not exist: {hourly_csv}")
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "Rscript",
        str(MODEL_SCRIPT),
        str(hourly_csv.resolve()),
        str(output_dir.resolve()),
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    if result.returncode:
        raise subprocess.CalledProcessError(
            result.returncode,
            command,
            output=result.stdout,
            stderr=result.stderr,
        )
    scores_path = output_dir / "forecast_scores.csv"
    if not scores_path.is_file():
        raise RuntimeError("R forecast completed without creating forecast_scores.csv")
    scores = pd.read_csv(scores_path).set_index("method")
    required_methods = {"calendar_lm", "hour_of_week_baseline"}
    if not required_methods.issubset(scores.index):
        raise ValueError("R forecast output is missing required model comparisons")
    predictions_path = output_dir / "forecast_predictions.csv"
    predictions = pd.read_csv(predictions_path)
    if predictions.empty:
        raise ValueError("R forecast did not produce holdout predictions")
    model_score = scores.loc["calendar_lm"]
    baseline_score = scores.loc["hour_of_week_baseline"]
    metrics = {
        "target": "hourly rental count",
        "split_method": "chronological final-window holdout",
        "holdout_days": 28,
        "train_rows": int(model_score["train_rows"]),
        "test_rows": int(model_score["test_rows"]),
        "train_end": str(model_score["train_end"]),
        "holdout_start": str(model_score["holdout_start"]),
        "holdout_end": str(model_score["holdout_end"]),
        "features": ["hour", "weekday", "season", "workingday"],
        "excluded_features": [
            "temperature",
            "apparent_temperature",
            "humidity",
            "windspeed",
            "weather",
            "casual",
            "registered",
        ],
        "model": model_score[["mae", "rmse", "wape"]].to_dict(),
        "baseline": baseline_score[["mae", "rmse", "wape"]].to_dict(),
        "lower_mae_than_baseline": bool(
            model_score["mae"] < baseline_score["mae"]
        ),
    }
    metrics["model"] = {
        key: float(value) for key, value in metrics["model"].items()
    }
    metrics["baseline"] = {
        key: float(value) for key, value in metrics["baseline"].items()
    }
    metrics_path = output_dir / "forecast_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return {
        "metrics_path": str(metrics_path),
        "predictions_path": str(predictions_path),
        "holdout_start": str(metrics["holdout_start"]),
    }
