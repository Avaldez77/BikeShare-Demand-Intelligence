from __future__ import annotations

import argparse
from pathlib import Path

from bikeshare.pipeline import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Capital Bikeshare demand-intelligence workflow."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("build"),
        help="Directory for downloaded data and generated outputs",
    )
    args = parser.parse_args()
    result = run_pipeline(args.output_dir)
    print(f"Pipeline completed. Report: {result['report_path']}")
    print(f"Demand model metrics: {result['model_metrics_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
