"""Tests for the shared aggregate data contracts (BD-004, ``buyers_desk.contracts``).

Covers all four aggregate roots from ``docs/context-map.md``: ``DataSnapshot``,
``ReorderPlan``, ``AssortmentReview``, and ``Report``. For each aggregate this
confirms: (a) it constructs from minimal valid data; (b) it carries a typed,
present schema version; (c) the additive-extension pattern holds — optional
fields default cleanly and can also be set afterwards via
``dataclasses.replace`` without touching the contract; and (d) field types
match what is declared. All sample data below is synthetic (fake SKUs/product
names/supplier names) — no customer PII, per the no-pii rule.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timezone

import pytest

from buyers_desk.contracts import (
    AssortmentFlag,
    AssortmentFlagType,
    AssortmentReview,
    DataSnapshot,
    ReorderLine,
    ReorderPlan,
    Report,
    ReportKind,
    ReportSheet,
    SnapshotRow,
)

FIXED_NOW = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)

# Forbidden field names per the no-pii rule: no aggregate or line item in
# this contract package may carry a customer-identifying field. Bare "name"
# is intentionally excluded — it legitimately names a Product/Report/sheet,
# never a person, on every dataclass in this package.
FORBIDDEN_FIELD_NAMES = {
    "customer_name",
    "customer_email",
    "customer_id",
    "email",
    "phone",
    "address",
    "ssn",
}

ALL_CONTRACT_DATACLASSES = [
    SnapshotRow,
    DataSnapshot,
    ReorderLine,
    ReorderPlan,
    AssortmentFlag,
    AssortmentReview,
    ReportSheet,
    Report,
]

AGGREGATE_ROOTS = [DataSnapshot, ReorderPlan, AssortmentReview, Report]


# ---------------------------------------------------------------------------
# Cross-cutting: schema versioning present + typed on every aggregate root;
# no customer-PII field names anywhere in the contract package.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("aggregate_cls", AGGREGATE_ROOTS)
def test_every_aggregate_root_has_a_typed_schema_version_constant(aggregate_cls):
    assert hasattr(aggregate_cls, "SCHEMA_VERSION")
    assert isinstance(aggregate_cls.SCHEMA_VERSION, int)
    assert aggregate_cls.SCHEMA_VERSION >= 1


@pytest.mark.parametrize("dataclass_type", ALL_CONTRACT_DATACLASSES)
def test_no_dataclass_in_the_contract_package_has_a_pii_field_name(dataclass_type):
    field_names = {f.name for f in dataclasses.fields(dataclass_type)}
    assert field_names.isdisjoint(FORBIDDEN_FIELD_NAMES)


# ---------------------------------------------------------------------------
# DataSnapshot / SnapshotRow
# ---------------------------------------------------------------------------


def test_data_snapshot_constructs_from_minimal_valid_data():
    row = SnapshotRow(sku="SKU-001", product_name="Test Snack", on_hand_units=40, units_sold=12)
    snapshot = DataSnapshot(
        snapshot_id="snap-001",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 18),
        captured_at=FIXED_NOW,
        rows=[row],
    )

    assert snapshot.snapshot_id == "snap-001"
    assert snapshot.rows == [row]
    assert snapshot.source_system == "fulfil"


def test_data_snapshot_schema_version_present_and_typed():
    snapshot = DataSnapshot(
        snapshot_id="snap-001",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 18),
        captured_at=FIXED_NOW,
    )
    assert isinstance(snapshot.schema_version, int)
    assert snapshot.schema_version == DataSnapshot.SCHEMA_VERSION


def test_snapshot_row_optional_fields_default_and_extend_additively():
    minimal = SnapshotRow(
        sku="SKU-002", product_name="Bare Bones Widget", on_hand_units=5, units_sold=1
    )
    assert minimal.unit_cost is None
    assert minimal.supplier is None

    extended = dataclasses.replace(minimal, unit_cost=2.50, supplier="Acme Test Supplier")
    assert extended.unit_cost == 2.50
    assert extended.supplier == "Acme Test Supplier"
    # Adding the optional fields did not require touching required fields.
    assert extended.sku == minimal.sku
    assert extended.product_name == minimal.product_name


def test_data_snapshot_field_types_match_declared_annotations():
    row = SnapshotRow(sku="SKU-003", product_name="Typed Toy", on_hand_units=3, units_sold=0)
    snapshot = DataSnapshot(
        snapshot_id="snap-002",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 18),
        captured_at=FIXED_NOW,
        rows=[row],
    )

    assert isinstance(snapshot.snapshot_id, str)
    assert isinstance(snapshot.period_start, date)
    assert isinstance(snapshot.period_end, date)
    assert isinstance(snapshot.captured_at, datetime)
    assert isinstance(snapshot.rows, list)
    assert all(isinstance(r, SnapshotRow) for r in snapshot.rows)
    assert isinstance(row.sku, str)
    assert isinstance(row.on_hand_units, int)
    assert isinstance(row.units_sold, int)


# ---------------------------------------------------------------------------
# ReorderPlan / ReorderLine
# ---------------------------------------------------------------------------


def test_reorder_plan_constructs_from_minimal_valid_data():
    line = ReorderLine(
        sku="SKU-010", product_name="Popular Snack", suggested_order_qty=48, reorder_point=20
    )
    plan = ReorderPlan(
        plan_id="plan-001",
        generated_at=FIXED_NOW,
        source_snapshot_id="snap-001",
        lines=[line],
    )

    assert plan.lines == [line]
    assert plan.source_snapshot_id == "snap-001"


def test_reorder_plan_schema_version_present_and_typed():
    plan = ReorderPlan(plan_id="plan-001", generated_at=FIXED_NOW, source_snapshot_id="snap-001")
    assert isinstance(plan.schema_version, int)
    assert plan.schema_version == ReorderPlan.SCHEMA_VERSION


def test_reorder_line_optional_fields_default_and_extend_additively():
    minimal = ReorderLine(
        sku="SKU-011", product_name="Bulk Item", suggested_order_qty=10, reorder_point=5
    )
    assert minimal.supplier is None
    assert minimal.needed_by is None
    assert minimal.sales_velocity_per_week is None
    assert minimal.rationale is None

    extended = dataclasses.replace(
        minimal,
        supplier="Test Supplier Co",
        needed_by=date(2026, 8, 1),
        sales_velocity_per_week=3.5,
        rationale="Below reorder point at current velocity",
    )
    assert extended.supplier == "Test Supplier Co"
    assert extended.needed_by == date(2026, 8, 1)
    assert extended.sales_velocity_per_week == 3.5
    assert extended.suggested_order_qty == minimal.suggested_order_qty


def test_reorder_plan_field_types_match_declared_annotations():
    line = ReorderLine(
        sku="SKU-012", product_name="Typed Line", suggested_order_qty=7, reorder_point=2
    )
    plan = ReorderPlan(
        plan_id="plan-002", generated_at=FIXED_NOW, source_snapshot_id="snap-002", lines=[line]
    )

    assert isinstance(plan.plan_id, str)
    assert isinstance(plan.generated_at, datetime)
    assert isinstance(plan.lines, list)
    assert all(isinstance(entry, ReorderLine) for entry in plan.lines)
    assert isinstance(line.suggested_order_qty, int)
    assert isinstance(line.reorder_point, int)


# ---------------------------------------------------------------------------
# AssortmentReview / AssortmentFlag
# ---------------------------------------------------------------------------


def test_assortment_review_constructs_from_minimal_valid_data():
    flag = AssortmentFlag(
        sku="SKU-020",
        product_name="Underperforming Toy",
        flag_type=AssortmentFlagType.SLOW_MOVER,
        reason="Below the performance bar for 8 consecutive weeks",
    )
    review = AssortmentReview(
        review_id="rev-001", generated_at=FIXED_NOW, source_snapshot_id="snap-001", flags=[flag]
    )

    assert review.flags == [flag]
    assert flag.flag_type is AssortmentFlagType.SLOW_MOVER


def test_assortment_review_schema_version_present_and_typed():
    review = AssortmentReview(
        review_id="rev-001", generated_at=FIXED_NOW, source_snapshot_id="snap-001"
    )
    assert isinstance(review.schema_version, int)
    assert review.schema_version == AssortmentReview.SCHEMA_VERSION


def test_assortment_flag_optional_fields_default_and_extend_additively():
    minimal = AssortmentFlag(
        sku="SKU-021",
        product_name="Bare Flag",
        flag_type=AssortmentFlagType.OVERSTOCK,
        reason="On hand far exceeds forecasted demand",
    )
    assert minimal.on_hand_units is None
    assert minimal.sales_velocity_per_week is None
    assert minimal.suggested_action is None

    extended = dataclasses.replace(minimal, on_hand_units=500, suggested_action="Discount 20%")
    assert extended.on_hand_units == 500
    assert extended.suggested_action == "Discount 20%"
    assert extended.reason == minimal.reason


def test_assortment_review_field_types_match_declared_annotations():
    flag = AssortmentFlag(
        sku="SKU-022",
        product_name="Typed Flag",
        flag_type=AssortmentFlagType.SLOW_MOVER,
        reason="Test reason",
    )
    review = AssortmentReview(
        review_id="rev-002", generated_at=FIXED_NOW, source_snapshot_id="snap-002", flags=[flag]
    )

    assert isinstance(review.review_id, str)
    assert isinstance(review.flags, list)
    assert all(isinstance(entry, AssortmentFlag) for entry in review.flags)
    assert isinstance(flag.flag_type, AssortmentFlagType)
    assert isinstance(flag.flag_type, str)  # str Enum: usable wherever a str is expected
    assert isinstance(flag.reason, str)


# ---------------------------------------------------------------------------
# Report / ReportSheet
# ---------------------------------------------------------------------------


def test_report_constructs_from_minimal_valid_data():
    sheet = ReportSheet(name="Reorder", headers=["SKU", "Suggested Qty"], rows=[["SKU-030", 24]])
    report = Report(
        report_id="rpt-001",
        kind=ReportKind.LOW_STOCK_REORDER,
        generated_at=FIXED_NOW,
        sheets=[sheet],
    )

    assert report.sheets == [sheet]
    # A fresh Report is a draft: never published on its own initiative.
    assert report.published_to is None
    assert report.published_at is None


def test_report_schema_version_present_and_typed():
    report = Report(report_id="rpt-001", kind=ReportKind.SALES_PERFORMANCE, generated_at=FIXED_NOW)
    assert isinstance(report.schema_version, int)
    assert report.schema_version == Report.SCHEMA_VERSION


def test_report_sheet_rows_default_and_extend_additively():
    minimal = ReportSheet(name="Empty Sheet", headers=["SKU"])
    assert minimal.rows == ()

    extended = dataclasses.replace(minimal, rows=[["SKU-031"]])
    assert extended.rows == [["SKU-031"]]
    assert extended.name == minimal.name


def test_report_stays_draft_until_publish_fields_are_explicitly_set():
    report = Report(
        report_id="rpt-002", kind=ReportKind.SLOW_MOVER_OVERSTOCK, generated_at=FIXED_NOW
    )
    assert report.published_to is None
    assert report.published_at is None

    published = dataclasses.replace(
        report,
        published_to="SharePoint/Buyer Reports/2026-07-19",
        published_at=FIXED_NOW,
    )
    assert published.published_to == "SharePoint/Buyer Reports/2026-07-19"
    assert published.published_at == FIXED_NOW


def test_report_field_types_match_declared_annotations():
    sheet = ReportSheet(name="Typed Sheet", headers=["A"], rows=[["1"]])
    report = Report(
        report_id="rpt-003",
        kind=ReportKind.SALES_PERFORMANCE,
        generated_at=FIXED_NOW,
        sheets=[sheet],
    )

    assert isinstance(report.report_id, str)
    assert isinstance(report.kind, ReportKind)
    assert isinstance(report.generated_at, datetime)
    assert isinstance(report.sheets, list)
    assert all(isinstance(entry, ReportSheet) for entry in report.sheets)
