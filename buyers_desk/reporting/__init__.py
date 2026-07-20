"""Reporting & Publishing bounded context — owned by ``report-publisher``.

Renders the recommendations into Excel-compatible reports (via openpyxl, see
ADR-0002) and publishes them to the correct SharePoint location. Publishing is
human-gated (human-in-the-loop rule): the send/publish step never runs on its
own initiative — reports are drafted/staged, then a human approves the send.

Aggregate root: ``Report``. Emits ``ReportPublished`` when a report has been
saved to SharePoint.

Scaffold only (BD-001). The Excel engine landed in BD-006 and the SharePoint
publisher landed in BD-007; the three reports land in later wave tickets:
BD-017, BD-018, BD-019, BD-020.

BD-006 adds the reusable workbook engine (``build_workbook``/
``write_workbook`` and their styling primitives) that BD-017/018/019 render
through; see ``buyers_desk.reporting.workbook`` for details.

BD-007 adds ``SharePointPublisher``, the boundary write-client to SharePoint
via Microsoft Graph. It only stages/prepares (``stage_upload``, no network
call) or — on explicit human approval only — publishes (``publish``); see
``buyers_desk.reporting.publisher`` for the draft-vs-send contract. Wiring
the three real reports through it lands in BD-020.
"""

from __future__ import annotations

from buyers_desk.reporting.publisher import (
    DEFAULT_TIMEOUT,
    GRAPH_BASE_URL,
    GRAPH_DEFAULT_SCOPE,
    GRAPH_TOKEN_URL_TEMPLATE,
    XLSX_CONTENT_TYPE,
    PendingUpload,
    PublishNotApprovedError,
    PublishResult,
    SharePointAuthError,
    SharePointConnectionError,
    SharePointInvalidDestinationError,
    SharePointPublisher,
    SharePointPublishError,
)
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
    "DEFAULT_TIMEOUT",
    "GRAPH_BASE_URL",
    "GRAPH_DEFAULT_SCOPE",
    "GRAPH_TOKEN_URL_TEMPLATE",
    "XLSX_CONTENT_TYPE",
    "PendingUpload",
    "PublishNotApprovedError",
    "PublishResult",
    "SharePointAuthError",
    "SharePointConnectionError",
    "SharePointInvalidDestinationError",
    "SharePointPublisher",
    "SharePointPublishError",
]
