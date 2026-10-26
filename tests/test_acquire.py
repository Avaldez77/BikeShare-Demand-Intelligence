from __future__ import annotations

import unittest

from bikeshare.acquire import REQUIRED_COLUMNS, validate_hourly_csv


class DatasetValidationTests(unittest.TestCase):
    def test_requires_all_source_fields(self) -> None:
        csv_content = b"instant,dteday\n1,2011-01-01\n"
        with self.assertRaisesRegex(ValueError, "missing columns"):
            validate_hourly_csv(csv_content)

    def test_rejects_unexpectedly_small_source(self) -> None:
        header = ",".join(sorted(REQUIRED_COLUMNS)).encode()
        with self.assertRaisesRegex(ValueError, "unexpectedly few rows"):
            validate_hourly_csv(header + b"\n1")


if __name__ == "__main__":
    unittest.main()
