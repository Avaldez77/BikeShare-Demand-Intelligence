# Capital Bikeshare Demand Intelligence

An end-to-end portfolio project that turns an attributable public mobility
dataset into a quality-checked analytical warehouse, demand insights, a
chronological forecast evaluation in R, and a dry-run operations report pack.
It is designed to be rerun locally and in CI without credentials or external
business-system access.

## The business question

How does hourly bicycle demand vary by time and season, and how well can a
calendar-based model forecast the next four weeks from historical demand?
The analysis separates observed outcomes from forecasts and compares the
forecast with an hour-of-week historical baseline.

## Pipeline

1. **Acquire and verify:** download the official UCI archive, verify its pinned
   SHA-256, and validate the hourly CSV schema.
2. **Engineer:** create DuckDB Bronze/Silver/Gold tables, quarantine records
   failing data-quality rules, and export hourly and daily analytical tables.
3. **Analyze:** create documented demand KPIs, hourly and daily charts, and an
   HTML briefing with pandas and matplotlib.
4. **Model:** use R to make a final-28-day chronological holdout, compare a
   calendar regression with an hour-of-week baseline, and report MAE, RMSE, and
   WAPE.
5. **Automate delivery:** build a checksum manifest, audit trail, and
   notification preview. No email is sent, orders are placed, or systems are
   changed.

## Data source, attribution, and license

Fanaee-T, H. (2013). *Bike Sharing* [Dataset]. UCI Machine Learning Repository.
https://doi.org/10.24432/C5W894

The UCI dataset describes hourly and daily bike rental counts from the Capital
Bikeshare system for 2011–2012. UCI lists the dataset under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The pipeline
downloads the original `hour.csv` from the UCI archive rather than asking
contributors to source or relabel records. The archive checksum is pinned in
the acquisition code so an upstream change fails visibly.

The dataset is historical and location-specific. It is suitable for
demonstrating methods, not for claiming current demand, causal weather effects,
or operational performance in another bike-share system.

## Requirements

- Python 3.12
- R 4.4.3 or newer with base/recommended packages
- Internet access for the first dataset download

Install and run from the repository root:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m bikeshare --output-dir build
```

The first run downloads the UCI archive (about 300 KB). The archive is cached under
`build/raw/`; remove that folder when you explicitly want to verify a fresh
download. Generated database, model, charts, and reports stay under `build/`
and are excluded from version control.

Run local tests without downloading the full dataset:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions also runs the test suite and the full pipeline against the
official UCI archive.

## Outputs

- `build/warehouse/warehouse.duckdb` — Bronze, Silver, quarantine, and Gold
  tables.
- `build/warehouse/hourly_demand.csv` and `daily_demand.csv` — validated
  analytical datasets.
- `build/analytics/` — KPI JSON, CSV breakdowns, PNG charts, and HTML briefing.
- `build/model/` — chronological holdout predictions and model-comparison
  metrics.
- `build/delivery/` — linked report, checksummed manifest, deterministic audit
  log, and unsent email preview.

## Portfolio connections

- [Data Analytics](https://github.com/Avaldez77/Data-Analytics-Portafolio)
  demonstrates KPI reporting and experiment analysis.
- [Data Engineering & Big Data](https://github.com/Avaldez77/Data-Engineering-Big-Data-Portafolio)
  demonstrates SQL and DuckDB quality pipelines.
- [Data Science](https://github.com/Avaldez77/Data-science-Portafolio)
  demonstrates statistical modeling, validation, and forecasting in R.
- [RPA & Process Automation](https://github.com/Avaldez77/RPAs-Portafolio)
  demonstrates dry-run reporting, auditing, and exception-safe automation.

This repository combines those practices in one runnable case. It does not
claim measured business impact or production deployment.
