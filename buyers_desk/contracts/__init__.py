"""Shared domain contracts (BD-004) — typed, versioned schemas for the four
aggregate roots defined in ``docs/context-map.md``.

This package exists so producers and consumers agree on shape BEFORE
implementation lands: ``data-integrator`` produces ``DataSnapshot``;
``merchandising-analyst`` consumes it and produces ``ReorderPlan`` and
``AssortmentReview``; ``report-publisher`` consumes those and produces
``Report``. Each aggregate lives in its own module and owns its own
``SCHEMA_VERSION`` (see each module's docstring for the versioning and
additive-evolution rules that apply to it).

Built with stdlib ``dataclasses`` + ``typing`` + ``enum`` only (no third-party
schema library) per ADR-0002 (stdlib-first). Line items (``SnapshotRow``,
``ReorderLine``, ``AssortmentFlag``, ``ReportSheet``) are frozen value objects;
aggregates are plain (mutable) typed containers that can be built up
incrementally by their owning agent.

No customer PII on any contract here — see ``data_snapshot.py`` for the
specific no-PII note on ``DataSnapshot``/``SnapshotRow`` (no-pii rule).

This module defines TYPES/SHAPES only: no extraction, aggregation, velocity,
reorder-point, or reporting logic lives here (that is later wave tickets).
"""

from __future__ import annotations

from buyers_desk.contracts.assortment_review import (
    AssortmentFlag,
    AssortmentFlagType,
    AssortmentReview,
)
from buyers_desk.contracts.data_snapshot import DataSnapshot, SnapshotRow
from buyers_desk.contracts.reorder_plan import ReorderLine, ReorderPlan
from buyers_desk.contracts.report import Report, ReportKind, ReportSheet

__all__ = [
    "AssortmentFlag",
    "AssortmentFlagType",
    "AssortmentReview",
    "DataSnapshot",
    "Report",
    "ReportKind",
    "ReportSheet",
    "ReorderLine",
    "ReorderPlan",
    "SnapshotRow",
]
