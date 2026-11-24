import csv
import json
import tempfile
import unittest
import zipfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from analysis.household_power import (
    EXPECTED_COLUMNS,
    expected_minutes_for_date,
    open_source_member,
    parse_power,
    parse_timestamp,
    read_daily,
    run_analysis,
    write_daily_csv,
    write_hourly_csv,
)


def observation(day: str, clock: str, power: str) -> str:
    return ";".join(
        (day, clock, power, "0,000", "230,000", "0,000", "0", "0", "0")
    )


def create_archive(path: Path, rows: list[str], name: str = "household_power_consumption.txt") -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, ";".join(EXPECTED_COLUMNS) + "\n" + "\n".join(rows) + "\n")


class HouseholdPowerTests(unittest.TestCase):
    def test_minute_average_kw_converts_to_kwh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "input.zip"
            create_archive(
                archive,
                [
                    observation("01/01/2020", "00:00:00", "1,000"),
                    observation("01/01/2020", "00:01:00", "2,000"),
                ],
            )
            daily, quality = read_daily(archive)
            output = root / "daily.csv"
            rows = write_daily_csv(
                output,
                daily,
                datetime.fromisoformat(str(quality["first_timestamp"])),
                datetime.fromisoformat(str(quality["last_timestamp"])),
            )
            self.assertEqual(rows[0]["daily_energy_kwh"], "0.050000")
            self.assertEqual(
                daily[date(2020, 1, 1)].active_power_sum_kw / Decimal(60),
                Decimal("0.05"),
            )

    def test_partial_boundary_expected_minutes_and_missing_power(self) -> None:
        first = datetime(2020, 1, 1, 23, 58)
        last = datetime(2020, 1, 2, 0, 1)
        self.assertEqual(expected_minutes_for_date(date(2020, 1, 1), first, last), 2)
        self.assertEqual(expected_minutes_for_date(date(2020, 1, 2), first, last), 2)
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "input.zip"
            create_archive(
                archive,
                [
                    observation("01/01/2020", "23:58:00", "1,000"),
                    observation("01/01/2020", "23:59:00", "?"),
                    observation("02/01/2020", "00:00:00", "2,000"),
                    observation("02/01/2020", "00:01:00", "2,000"),
                ],
            )
            daily, quality = read_daily(archive)
            self.assertEqual(quality["missing_active_power_minutes"], 1)
            self.assertEqual(daily[date(2020, 1, 1)].missing_power_minutes, 1)
            self.assertEqual(daily[date(2020, 1, 1)].valid_power_minutes, 1)

    def test_hourly_summary_applies_ninety_percent_valid_coverage_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, powers, expected_complete, expected_mean in (
                ("complete.zip", ["1,000"] * 9 + ["?"], "true", "1.000000"),
                ("incomplete.zip", ["1,000"] * 8 + ["?", "?"], "false", ""),
            ):
                archive = root / name
                create_archive(
                    archive,
                    [
                        observation("01/01/2020", f"00:{minute:02d}:00", power)
                        for minute, power in enumerate(powers)
                    ],
                )
                daily, quality = read_daily(archive)
                rows = write_hourly_csv(
                    root / f"{name}.csv",
                    daily,
                    datetime.fromisoformat(str(quality["first_timestamp"])),
                    datetime.fromisoformat(str(quality["last_timestamp"])),
                )
                hour_zero = rows[0]
                self.assertEqual(hour_zero["expected_minutes"], 10)
                self.assertEqual(hour_zero["valid_power_minutes"], 9 if expected_complete == "true" else 8)
                self.assertEqual(hour_zero["valid_coverage_pct"], "90.000" if expected_complete == "true" else "80.000")
                self.assertEqual(hour_zero["complete_hour"], expected_complete)
                self.assertEqual(hour_zero["mean_active_power_kw"], expected_mean)
                self.assertEqual(rows[1]["expected_minutes"], 0)
                self.assertEqual(rows[1]["complete_hour"], "false")

    def test_calendar_day_without_rows_is_exported_with_zero_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "input.zip"
            create_archive(
                archive,
                [
                    observation("01/01/2020", "23:59:00", "1,000"),
                    observation("03/01/2020", "00:00:00", "2,000"),
                ],
            )
            daily, quality = read_daily(archive)
            rows = write_daily_csv(
                root / "daily.csv",
                daily,
                datetime.fromisoformat(str(quality["first_timestamp"])),
                datetime.fromisoformat(str(quality["last_timestamp"])),
            )
            missing_day = rows[1]
            self.assertEqual(missing_day["date"], "2020-01-02")
            self.assertEqual(missing_day["expected_minutes"], 1440)
            self.assertEqual(missing_day["observed_minutes"], 0)
            self.assertEqual(missing_day["valid_coverage_pct"], "0.000")
            self.assertEqual(missing_day["complete_day"], "false")
            self.assertEqual(quality["skipped_minute_slots"], 1440)

    def test_rejects_bad_timestamp_and_active_power(self) -> None:
        with self.assertRaisesRegex(ValueError, "Malformed timestamp"):
            parse_timestamp("31/02/2020", "00:00:00")
        with self.assertRaisesRegex(ValueError, "Invalid active-power"):
            parse_power("NaN", 2)
        with self.assertRaisesRegex(ValueError, "Invalid active-power"):
            parse_power("-1,000", 2)

    def test_rejects_duplicate_and_malformed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            duplicate = root / "duplicate.zip"
            create_archive(
                duplicate,
                [
                    observation("01/01/2020", "00:00:00", "1,000"),
                    observation("01/01/2020", "00:00:00", "1,000"),
                ],
            )
            with self.assertRaisesRegex(ValueError, "Duplicate or out-of-order"):
                read_daily(duplicate)
            malformed = root / "malformed.zip"
            create_archive(malformed, ["01/01/2020;00:00:00;1,000"])
            with self.assertRaisesRegex(ValueError, "Malformed row"):
                read_daily(malformed)

    def test_archive_member_must_be_exact_and_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("../household_power_consumption.txt", "nested/household_power_consumption.txt"):
                archive_path = root / "unsafe.zip"
                create_archive(archive_path, [], name=name)
                with self.assertRaises(ValueError):
                    archive, _member = open_source_member(archive_path)
                    archive.close()
            archive_path = root / "extra.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("household_power_consumption.txt", "data")
                archive.writestr("extra.txt", "unexpected")
            with self.assertRaisesRegex(ValueError, "exactly one"):
                open_source_member(archive_path)

    def test_end_to_end_exports_match_computed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "input.zip"
            create_archive(
                archive,
                [
                    observation("01/01/2020", "00:00:00", "1,000"),
                    observation("01/01/2020", "00:01:00", "1,000"),
                ],
            )
            with patch(
                "analysis.household_power.git_provenance",
                return_value={
                    "input_commit": "test-commit",
                    "input_blob_sha": "test-blob",
                    "analysis_revision": "test-revision",
                },
            ):
                result = run_analysis(archive, root / "outputs")
            with (root / "outputs" / "daily_consumption.csv").open(
                encoding="utf-8", newline=""
            ) as source:
                rows = list(csv.DictReader(source))
            self.assertEqual(rows[0]["daily_energy_kwh"], "0.033333")
            svg = (root / "outputs" / "daily_consumption.svg").read_text(
                encoding="utf-8"
            )
            self.assertIn("Partial / lower coverage", svg)
            self.assertIn(
                'data-date="2020-01-01" data-daily-energy-kwh="0.033333"',
                svg,
            )
            hourly_csv = root / "outputs" / "hourly_active_power.csv"
            with hourly_csv.open(encoding="utf-8", newline="") as source:
                hourly_rows = list(csv.DictReader(source))
            self.assertEqual(len(hourly_rows), 24)
            self.assertEqual(hourly_rows[0]["mean_active_power_kw"], "1.000000")
            self.assertEqual(hourly_rows[0]["valid_power_minutes"], "2")
            hourly_svg = (root / "outputs" / "hourly_active_power.svg").read_text(
                encoding="utf-8"
            )
            self.assertIn('role="img" aria-labelledby="title desc"', hourly_svg)
            self.assertIn("timezone-naive", hourly_svg)
            metadata = json.loads(
                (root / "outputs" / "export_metadata.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIsNone(metadata["publication_date"])
            self.assertEqual(result["rows"][0]["daily_energy_kwh"], rows[0]["daily_energy_kwh"])
            self.assertEqual(metadata["outputs"]["daily_csv"], "outputs/daily_consumption.csv")
            self.assertEqual(
                metadata["outputs"]["hourly_csv"], "outputs/hourly_active_power.csv"
            )
            self.assertEqual(metadata["method"]["hourly_summary"].count("90%"), 1)
        self.assertEqual(parse_power("4.216", 2), Decimal("4.216"))


if __name__ == "__main__":
    unittest.main()
