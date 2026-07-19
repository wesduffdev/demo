"""Reporting & Publishing bounded context — owned by ``report-publisher``.

Renders the recommendations into Excel-compatible reports (via openpyxl, see
ADR-0002) and publishes them to the correct SharePoint location. Publishing is
human-gated (human-in-the-loop rule): the send/publish step never runs on its
own initiative — reports are drafted/staged, then a human approves the send.

Aggregate root: ``Report``. Emits ``ReportPublished`` when a report has been
saved to SharePoint.

Scaffold only (BD-001). The Excel engine, the SharePoint publisher, and the
three reports land in later wave tickets: BD-006, BD-007, BD-017, BD-018,
BD-019, BD-020.
"""

from __future__ import annotations
