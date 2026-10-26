from __future__ import annotations

import csv
import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path


DATASET_URL = "https://archive.ics.uci.edu/static/public/275/bike+sharing+dataset.zip"
DATASET_SHA256 = "b70182d0d0508e9abbb79306ce5c0cec34869000f8220175ac83d11dbe845401"
REQUIRED_COLUMNS = {
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
}


def validate_hourly_csv(content: bytes) -> int:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("UCI hourly CSV is not valid UTF-8") from error

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("UCI hourly CSV is missing its header")
    missing = sorted(REQUIRED_COLUMNS - set(reader.fieldnames))
    if missing:
        raise ValueError(f"UCI hourly CSV is missing columns: {', '.join(missing)}")
    row_count = sum(1 for _ in reader)
    if row_count < 17000:
        raise ValueError(f"UCI hourly CSV has unexpectedly few rows: {row_count}")
    return row_count


def acquire_dataset(raw_dir: Path) -> tuple[Path, str, str, int]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / "hour.csv"
    archive_path = raw_dir / "uci-bike-sharing-dataset.zip"
    if archive_path.is_file():
        archive_bytes = archive_path.read_bytes()
    else:
        request = urllib.request.Request(
            DATASET_URL,
            headers={"User-Agent": "Avaldez77-BikeShare-Demand-Intelligence/1.0"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            archive_bytes = response.read()
    archive_digest = hashlib.sha256(archive_bytes).hexdigest()
    if archive_digest != DATASET_SHA256:
        raise ValueError(
            "UCI dataset archive checksum mismatch; refusing changed source "
            f"(expected {DATASET_SHA256}, received {archive_digest})"
        )
    archive_path.write_bytes(archive_bytes)

    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            try:
                content = archive.read("hour.csv")
            except KeyError as error:
                raise ValueError("UCI archive does not contain hour.csv") from error
    except zipfile.BadZipFile as error:
        raise ValueError("UCI dataset download is not a valid ZIP archive") from error

    row_count = validate_hourly_csv(content)
    if target.is_file() and target.read_bytes() != content:
        raise ValueError("Cached hour.csv does not match the checksum-verified UCI archive")
    target.write_bytes(content)
    return target, archive_digest, hashlib.sha256(content).hexdigest(), row_count
