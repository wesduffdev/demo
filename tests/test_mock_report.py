"""Tests for the mock report entry point (``buyers_desk.mock_report``).

No live network calls and no dependency on the real, git-ignored sample WAR
workbook: each test builds its own synthetic ``.xlsx`` fixture in a temp dir.
All fixture data is synthetic (fake SKUs/brands/numbers) — no customer PII and
no real company financials, per the no-pii rule.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook, load_workbook

from buyers_desk.contracts import ReportKind
from buyers_desk.mock_report import generate, load_mock_report, main


def _make_mock_workbook(path: Path) -> Path:
    """Write a small two-sheet synthetic workbook to ``path`` and return it."""
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Store Inventory"
    # A None header in a non-trailing column exercises header normalization.
    ws1.append(["SKU", None, "On Hand"])
    ws1.append(["SKU-001", "Salmon Dog Food", 340])
    ws1.append(["SKU-002", "Catnip Toy", 120])

    ws2 = wb.create_sheet("Sales")
    ws2.append(["SKU", "Units Sold"])
    ws2.append(["SKU-001", 1280])

    wb.save(path)
    return path


def test_load_mock_report_reads_all_sheets_and_normalizes_headers(tmp_path):
    source = _make_mock_workbook(tmp_path / "mock.xlsx")

    report = load_mock_report(source, report_date="2026-01-15")

    assert report.kind is ReportKind.SALES_PERFORMANCE
    assert report.report_id == "mock-2026-01-15"
    assert [sheet.name for sheet in report.sheets] == ["Store Inventory", "Sales"]

    store_sheet = report.sheets[0]
    # None header cell normalized to "" (not dropped, not None).
    assert store_sheet.headers == ["SKU", "", "On Hand"]
    assert store_sheet.rows[0] == ["SKU-001", "Salmon Dog Food", 340]
    assert report.sheets[1].rows[0] == ["SKU-001", 1280]


def test_generate_writes_workbook_to_output_dir(tmp_path):
    source = _make_mock_workbook(tmp_path / "mock.xlsx")
    out_dir = tmp_path / "output"

    out_path = generate(source=source, output_dir=out_dir, report_date="2026-01-15")

    assert out_path == out_dir / "WAR_2026-01-15.xlsx"
    assert out_path.is_file()

    # Re-open the generated file and confirm it faithfully rendered the source.
    produced = load_workbook(out_path, data_only=True)
    assert produced.sheetnames == ["Store Inventory", "Sales"]
    assert produced["Store Inventory"].cell(row=1, column=1).value == "SKU"
    assert produced["Store Inventory"].cell(row=2, column=3).value == 340


def test_generate_default_report_date_uses_today(tmp_path):
    source = _make_mock_workbook(tmp_path / "mock.xlsx")

    out_path = generate(source=source, output_dir=tmp_path / "out")

    assert re.fullmatch(r"WAR_\d{4}-\d{2}-\d{2}\.xlsx", out_path.name)
    # Matches today's UTC date (allowing for the tiny chance of a date rollover).
    assert out_path.name == f"WAR_{datetime.now(timezone.utc):%Y-%m-%d}.xlsx"


def test_main_success_returns_zero_and_reports_path(tmp_path, capsys):
    source = _make_mock_workbook(tmp_path / "mock.xlsx")
    out_dir = tmp_path / "output"

    code = main(
        ["--source", str(source), "--output-dir", str(out_dir), "--report-date", "2026-02-02"]
    )

    assert code == 0
    assert (out_dir / "WAR_2026-02-02.xlsx").is_file()
    assert "wrote" in capsys.readouterr().out


def test_main_missing_source_returns_one_without_writing(tmp_path, capsys):
    out_dir = tmp_path / "output"

    code = main(["--source", str(tmp_path / "does-not-exist.xlsx"), "--output-dir", str(out_dir)])

    assert code == 1
    assert "not found" in capsys.readouterr().err
    assert not out_dir.exists()
