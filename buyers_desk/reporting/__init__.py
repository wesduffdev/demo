"""Reporting & Publishing bounded context — owned by ``report-publisher``.

Renders the recommendations into Excel-compatible reports (via openpyxl, see
ADR-0002) and publishes them to the correct SharePoint location. Publishing is
human-gated (human-in-the-loop rule): the send/publish step never runs on its
own initiative — reports are drafted/staged, then a human approves the send.

Aggregate root: ``Report``. Emits ``ReportPublished`` when a report has been
saved to SharePoint.

Scaffold only (BD-001). The Excel engine landed in BD-006; the SharePoint
publisher and the three reports land in later wave tickets: BD-007, BD-017,
BD-018, BD-019, BD-020.

BD-006 adds the reusable workbook engine (``build_workbook``/
``write_workbook`` and their styling primitives) that BD-017/018/019 render
through; see ``buyers_desk.reporting.workbook`` for details.
"""

from __future__ import annotations

from buyers_desk.reporting.workbook import (
    EMPTY_WORKBOOK_SHEET_NAME,
    FROZEN_HEADER_CELL,
    HEADER_ALIGNMENT,
    HEADER_FILL,
    HEADER_FONT,
    MAX_COLUMN_WIDTH,
    MIN_COLUMN_WIDTH,
    THOUSANDS_DECIMAL_NUMBER_FORMAT,
    THOUSANDS_NUMBER_FORMAT,
    build_workbook,
    write_workbook,
)

__all__ = [
    "EMPTY_WORKBOOK_SHEET_NAME",
    "FROZEN_HEADER_CELL",
    "HEADER_ALIGNMENT",
    "HEADER_FILL",
    "HEADER_FONT",
    "MAX_COLUMN_WIDTH",
    "MIN_COLUMN_WIDTH",
    "THOUSANDS_DECIMAL_NUMBER_FORMAT",
    "THOUSANDS_NUMBER_FORMAT",
    "build_workbook",
    "write_workbook",
]
