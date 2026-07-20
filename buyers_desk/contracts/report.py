"""Data contract for the ``Report`` aggregate (Reporting & Publishing).

Owned by ``report-publisher``. ``Report`` is the Excel-compatible workbook
contract (sales performance, low-stock/reorder, slow-mover/overstock) that
gets published to SharePoint after the ``ReportPublished`` event (see
``docs/context-map.md``).

Draft vs. published
--------------------
``published_to`` and ``published_at`` are ``None`` while a ``Report`` is
staged/drafted. They are only set once a human has explicitly approved the
publish step (see the human-in-the-loop and external-services rules) —
``report-publisher`` must never populate them on its own initiative.

No customer PII
----------------
``Report`` renders recommendations and snapshot facts that are already
Product/aggregate level (see ``DataSnapshot``'s no-PII note in
``data_snapshot.py``); do not add a customer-identifying field to a
``ReportSheet`` row.

Versioning & additive evolution
--------------------------------
``Report.SCHEMA_VERSION`` is the contract version for this aggregate.
``report-publisher`` may add new **optional** fields (with a default) to
``Report`` or ``ReportSheet`` later without breaking existing producers
(``merchandising-analyst``, ``data-integrator``) — additive changes do not
require a version bump. Bump ``SCHEMA_VERSION`` only for a breaking change.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import ClassVar


class ReportKind(str, Enum):
    """Which of the three v1 report types this workbook is."""

    SALES_PERFORMANCE = "sales_performance"
    LOW_STOCK_REORDER = "low_stock_reorder"
    SLOW_MOVER_OVERSTOCK = "slow_mover_overstock"


@dataclass(frozen=True)
class ReportSheet:
    """One worksheet/tab: a name plus a header row and data rows."""

    name: str
    headers: Sequence[str]
    rows: Sequence[Sequence[object]] = field(default_factory=tuple)


@dataclass
class Report:
    """The Excel-compatible workbook contract. Aggregate root of Reporting & Publishing."""

    SCHEMA_VERSION: ClassVar[int] = 1

    report_id: str
    kind: ReportKind
    generated_at: datetime
    sheets: list[ReportSheet] = field(default_factory=list)
    published_to: str | None = None
    published_at: datetime | None = None
    schema_version: int = SCHEMA_VERSION
