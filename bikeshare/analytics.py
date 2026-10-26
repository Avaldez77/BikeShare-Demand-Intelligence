from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


SEASONS = {1: "Winter", 2: "Spring", 3: "Summer", 4: "Fall"}


def build_analytics(warehouse_dir: Path, output_dir: Path) -> dict[str, Any]:
    daily_path = warehouse_dir / "daily_demand.csv"
    hourly_path = warehouse_dir / "hourly_demand.csv"
    if not daily_path.is_file() or not hourly_path.is_file():
        raise FileNotFoundError("Warehouse daily and hourly exports must both exist")
    output_dir.mkdir(parents=True, exist_ok=True)

    daily = pd.read_csv(daily_path, parse_dates=["service_date"])
    hourly = pd.read_csv(hourly_path)
    if daily.empty or hourly.empty:
        raise ValueError("Warehouse exports must contain validated demand records")

    total_rentals = int(daily["total_rentals"].sum())
    peak_day = daily.loc[daily["total_rentals"].idxmax()]
    season = (
        daily.groupby("season", as_index=False)
        .agg(total_rentals=("total_rentals", "sum"), mean_daily_rentals=("total_rentals", "mean"))
        .sort_values("season")
    )
    season["season_name"] = season["season"].map(SEASONS)
    season["share_of_rentals"] = season["total_rentals"] / total_rentals
    season.to_csv(output_dir / "season_breakdown.csv", index=False, lineterminator="\n")

    hourly_profile = (
        hourly.groupby(["hour", "workingday"], as_index=False)
        .agg(mean_rentals=("count", "mean"), median_rentals=("count", "median"))
        .sort_values(["workingday", "hour"])
    )
    hourly_profile["day_type"] = hourly_profile["workingday"].map(
        {0: "Non-working day", 1: "Working day"}
    )
    hourly_profile.to_csv(
        output_dir / "hourly_profile.csv",
        index=False,
        lineterminator="\n",
    )

    segment_share = daily[["casual_rentals", "registered_rentals"]].sum()
    summary = {
        "dataset": "UCI Bike Sharing hourly data",
        "observed_date_start": daily["service_date"].min().date().isoformat(),
        "observed_date_end": daily["service_date"].max().date().isoformat(),
        "observed_days": int(daily["service_date"].nunique()),
        "hourly_records": len(hourly),
        "total_rentals": total_rentals,
        "mean_daily_rentals": float(daily["total_rentals"].mean()),
        "peak_demand_date": peak_day["service_date"].date().isoformat(),
        "peak_demand_rentals": int(peak_day["total_rentals"]),
        "casual_rental_share": float(segment_share["casual_rentals"] / total_rentals),
        "registered_rental_share": float(segment_share["registered_rentals"] / total_rentals),
        "season_with_highest_total": str(
            season.loc[season["total_rentals"].idxmax(), "season_name"]
        ),
    }
    (output_dir / "kpi_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    figure, axis = plt.subplots(figsize=(11, 4.5), constrained_layout=True)
    axis.plot(daily["service_date"], daily["total_rentals"], color="#176B87", linewidth=0.8)
    axis.set(title="Daily bike rentals", xlabel="Date", ylabel="Rentals")
    axis.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    axis.grid(axis="y", alpha=0.25)
    figure.savefig(output_dir / "daily_demand.png", dpi=140)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(9, 4.5), constrained_layout=True)
    for workingday, label, color in (
        (1, "Working day", "#176B87"),
        (0, "Non-working day", "#E07A5F"),
    ):
        profile = hourly_profile[hourly_profile["workingday"] == workingday]
        axis.plot(profile["hour"], profile["mean_rentals"], label=label, color=color)
    axis.set(title="Mean hourly demand by day type", xlabel="Hour of day", ylabel="Mean rentals")
    axis.set_xticks(range(0, 24, 2))
    axis.grid(alpha=0.25)
    axis.legend(frameon=False)
    figure.savefig(output_dir / "hourly_demand.png", dpi=140)
    plt.close(figure)

    safe_start = html.escape(summary["observed_date_start"])
    safe_end = html.escape(summary["observed_date_end"])
    season_table = season[
        ["season_name", "total_rentals", "mean_daily_rentals", "share_of_rentals"]
    ].to_html(index=False, float_format=lambda value: f"{value:,.3f}")
    document = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Capital Bikeshare demand briefing</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#20303c}}
img{{max-width:100%}}table{{border-collapse:collapse}}th,td{{padding:.45rem;border:1px solid #ccd5dc}}
.note{{background:#f0f5f7;padding:1rem}}</style></head>
<body><h1>Capital Bikeshare demand briefing</h1>
<p>Observed window: {safe_start} through {safe_end}. Source: UCI Bike Sharing Dataset.</p>
<div class="note"><strong>Interpretation:</strong> these are historical observations
from the Capital Bikeshare system in 2011-2012. They are not current service-level
forecasts or a causal estimate.</div>
<h2>Demand overview</h2><ul>
<li>Total observed rentals: {summary["total_rentals"]:,}</li>
<li>Mean rentals per observed day: {summary["mean_daily_rentals"]:,.1f}</li>
<li>Highest-demand observed day: {summary["peak_demand_date"]} ({summary["peak_demand_rentals"]:,})</li>
<li>Registered-user share: {summary["registered_rental_share"]:.1%}</li>
<li>Season with highest total: {html.escape(summary["season_with_highest_total"])}</li>
</ul><h2>Daily trend</h2><img src="daily_demand.png" alt="Daily rental counts over the observation period">
<h2>Hourly profile</h2><img src="hourly_demand.png" alt="Mean hourly demand by day type">
<h2>Season breakdown</h2>{season_table}
<p>Methods, source attribution, license, validation, and limitations are documented
in the project README.</p></body></html>
"""
    (output_dir / "briefing.html").write_text(document, encoding="utf-8")
    return summary


def append_forecast_results(analytics_dir: Path, metrics_path: Path) -> None:
    report_path = analytics_dir / "briefing.html"
    if not report_path.is_file() or not metrics_path.is_file():
        raise FileNotFoundError("Analytics briefing and forecast metrics are required")
    report = report_path.read_text(encoding="utf-8")
    if "</body>" not in report or "id=\"forecast-results\"" in report:
        raise ValueError("Briefing is malformed or already contains forecast results")

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    forecast = f"""<h2 id="forecast-results">Forecast evaluation</h2>
<p>Chronological holdout: {html.escape(metrics["holdout_start"])} to
{html.escape(metrics["holdout_end"])} ({metrics["test_rows"]:,} observed hours).
The calendar model uses hour, weekday, season, and working-day indicators.
Weather readings and contemporaneous rider counts are excluded because they
may not be available when planning demand.</p>
<table><thead><tr><th>Method</th><th>MAE</th><th>RMSE</th><th>WAPE</th></tr></thead>
<tbody><tr><td>Calendar regression</td><td>{metrics["model"]["mae"]:.2f}</td>
<td>{metrics["model"]["rmse"]:.2f}</td><td>{metrics["model"]["wape"]:.1%}</td></tr>
<tr><td>Hour-of-week baseline</td><td>{metrics["baseline"]["mae"]:.2f}</td>
<td>{metrics["baseline"]["rmse"]:.2f}</td><td>{metrics["baseline"]["wape"]:.1%}</td></tr>
</tbody></table>
<p>These errors describe only the historical holdout in this dataset. They do
not guarantee future accuracy in another period or operating context.</p>
"""
    report_path.write_text(report.replace("</body>", forecast + "</body>"), encoding="utf-8")
