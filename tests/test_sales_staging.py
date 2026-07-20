"""Tests for BD-008 raw sales staging pull (``buyers_desk/data_integration/sales_staging.py``).

No live network calls: ``FulfilClient.get`` is replaced with a fake/mock
(no ``requests`` session is ever exercised here — that is BD-005's own test
file). All fixture data is synthetic (fake SKUs/product names), and no
fixture ever carries a customer/order-identity field, per the no-pii rule.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from buyers_desk.data_integration import (
    DEFAULT_MAX_PAGES,
    DEFAULT_PAGE_SIZE,
    SalesRow,
    SalesStagingBatch,
    from_fulfil_record,
    normalize_sku,
    pull_sales_rows,
)
from buyers_desk.data_integration.fulfil_client import (
    FulfilAPIError,
    FulfilClient,
    FulfilConnectionError,
)


def _fake_client(responses: list[Any]) -> FulfilClient:
    """A ``FulfilClient``-shaped stub whose ``get`` returns each of
    ``responses`` in turn (one per call), without touching the network."""
    client = MagicMock(spec=FulfilClient)
    client.get.side_effect = responses
    return client


# ---------------------------------------------------------------------------
# from_fulfil_record: happy path + tolerance for missing/extra/bad fields
# ---------------------------------------------------------------------------


def test_from_fulfil_record_maps_a_well_formed_record():
    row = from_fulfil_record({"sku": "abc-123", "product_name": "Fake Snack", "quantity": 4})

    assert row == SalesRow(sku="ABC-123", units_sold=4, product_name="Fake Snack")


def test_from_fulfil_record_accepts_nested_product_object():
    row = from_fulfil_record(
        {"product": {"code": "sku-9", "name": "Nested Widget"}, "quantity_sold": 2}
    )

    assert row is not None
    assert row.sku == "SKU-9"
    assert row.product_name == "Nested Widget"
    assert row.units_sold == 2


def test_from_fulfil_record_ignores_unknown_and_customer_fields():
    row = from_fulfil_record(
        {
            "sku": "SKU-1",
            "quantity": 1,
            # None of these are on the allow-list; they must never surface
            # on the resulting SalesRow (no-pii rule).
            "customer_name": "Jane Doe",
            "customer_email": "jane.doe@example.com",
            "shipping_address": "123 Fake St",
            "order_id": "SO-99999",
        }
    )

    assert row is not None
    assert not hasattr(row, "customer_name")
    assert not hasattr(row, "customer_email")
    assert not hasattr(row, "shipping_address")
    assert not hasattr(row, "order_id")
    assert set(vars(row)) == {"sku", "units_sold", "product_name"}


def test_from_fulfil_record_returns_none_for_non_mapping():
    assert from_fulfil_record("not-a-record") is None
    assert from_fulfil_record(["also", "not", "a", "record"]) is None
    assert from_fulfil_record(None) is None


def test_from_fulfil_record_returns_none_when_sku_missing():
    assert from_fulfil_record({"product_name": "No SKU Here", "quantity": 3}) is None


def test_from_fulfil_record_returns_none_when_sku_blank():
    assert from_fulfil_record({"sku": "   ", "quantity": 3}) is None


def test_from_fulfil_record_returns_none_when_quantity_missing():
    assert from_fulfil_record({"sku": "SKU-2", "product_name": "No Qty"}) is None


def test_from_fulfil_record_returns_none_when_quantity_not_numeric():
    assert from_fulfil_record({"sku": "SKU-3", "quantity": "a-lot"}) is None


@pytest.mark.parametrize("bad_quantity", [float("inf"), float("-inf"), float("nan")])
def test_from_fulfil_record_returns_none_for_non_finite_quantity(bad_quantity):
    # json.loads accepts Infinity/-Infinity/NaN tokens by default, so these
    # can arrive straight out of a Fulfil response body. round(float('inf'))
    # raises OverflowError (not caught by the TypeError/ValueError guard),
    # which must never propagate out of this "never raises for bad data"
    # module — the record is skipped, exactly like any other bad quantity.
    assert from_fulfil_record({"sku": "SKU-3", "quantity": bad_quantity}) is None


def test_from_fulfil_record_returns_none_for_boolean_quantity():
    # bool is a subclass of int in Python; must not be treated as a quantity.
    assert from_fulfil_record({"sku": "SKU-4", "quantity": True}) is None


def test_from_fulfil_record_tolerates_missing_product_name():
    row = from_fulfil_record({"sku": "SKU-5", "quantity": 7})

    assert row == SalesRow(sku="SKU-5", units_sold=7, product_name=None)


def test_from_fulfil_record_rounds_fractional_quantity():
    row = from_fulfil_record({"sku": "SKU-6", "quantity": 2.6})

    assert row is not None
    assert row.units_sold == 3
    assert isinstance(row.units_sold, int)


def test_from_fulfil_record_preserves_negative_quantity_as_a_raw_fact():
    # A return/refund line is a legitimate raw sales fact; clamping/netting
    # is a later (BD-011) decision, not this staging layer's job.
    row = from_fulfil_record({"sku": "SKU-7", "quantity": -2})

    assert row is not None
    assert row.units_sold == -2


# ---------------------------------------------------------------------------
# SKU key normalization (the exact convention BD-009 must match)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("abc-123", "ABC-123"),
        ("  SKU-1  ", "SKU-1"),
        ("sku-1", "SKU-1"),
        (12345, "12345"),
    ],
)
def test_normalize_sku_produces_canonical_form(raw, expected):
    assert normalize_sku(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_normalize_sku_returns_none_for_unusable_input(raw):
    assert normalize_sku(raw) is None


def test_from_fulfil_record_uses_normalize_sku_for_the_sku_field():
    row = from_fulfil_record({"sku": "  sku-42  ", "quantity": 1})

    assert row is not None
    assert row.sku == normalize_sku("  sku-42  ")


# ---------------------------------------------------------------------------
# pull_sales_rows: happy path
# ---------------------------------------------------------------------------


def test_pull_sales_rows_happy_path_maps_well_formed_records():
    client = _fake_client(
        [
            [
                {"sku": "SKU-100", "product_name": "Fake Widget", "quantity": 5},
                {"sku": "sku-101", "product_name": "Fake Gadget", "quantity": 2},
            ]
        ]
    )

    batch = pull_sales_rows(client, page_size=50)

    assert isinstance(batch, SalesStagingBatch)
    assert batch.rows == [
        SalesRow(sku="SKU-100", units_sold=5, product_name="Fake Widget"),
        SalesRow(sku="SKU-101", units_sold=2, product_name="Fake Gadget"),
    ]
    assert batch.skipped_count == 0
    assert batch.warnings == []
    assert isinstance(batch.pulled_at, datetime)
    assert batch.schema_version == SalesRow.SCHEMA_VERSION


def test_pull_sales_rows_stops_after_a_short_page_without_a_second_call():
    client = _fake_client([[{"sku": "SKU-1", "quantity": 1}]])

    pull_sales_rows(client, page_size=50)

    assert client.get.call_count == 1


def test_pull_sales_rows_uses_bounded_limit_offset_params():
    client = _fake_client([[{"sku": "SKU-1", "quantity": 1}] * 3, []])

    pull_sales_rows(client, page_size=3, max_pages=5)

    first_call_kwargs = client.get.call_args_list[0].kwargs
    second_call_kwargs = client.get.call_args_list[1].kwargs
    assert first_call_kwargs["params"]["limit"] == 3
    assert first_call_kwargs["params"]["offset"] == 0
    assert second_call_kwargs["params"]["offset"] == 3


# ---------------------------------------------------------------------------
# pull_sales_rows: empty responses handled without crashing
# ---------------------------------------------------------------------------


def test_pull_sales_rows_handles_none_response():
    client = _fake_client([None])

    batch = pull_sales_rows(client)

    assert batch.rows == []
    assert batch.skipped_count == 0
    assert batch.warnings == []


def test_pull_sales_rows_handles_empty_list_response():
    client = _fake_client([[]])

    batch = pull_sales_rows(client)

    assert batch.rows == []
    assert batch.skipped_count == 0


def test_pull_sales_rows_handles_empty_envelope_dict():
    client = _fake_client([{"records": []}])

    batch = pull_sales_rows(client)

    assert batch.rows == []


# ---------------------------------------------------------------------------
# pull_sales_rows: partial / malformed responses handled without crashing
# ---------------------------------------------------------------------------


def test_pull_sales_rows_skips_malformed_records_and_keeps_good_ones():
    client = _fake_client(
        [
            [
                {"sku": "SKU-1", "quantity": 1},
                {"product_name": "Missing SKU"},
                "not-a-record",
                {"sku": "SKU-2", "quantity": "not-numeric"},
                {"sku": "SKU-3", "quantity": 9},
            ]
        ]
    )

    batch = pull_sales_rows(client, page_size=50)

    assert [row.sku for row in batch.rows] == ["SKU-1", "SKU-3"]
    assert batch.skipped_count == 3
    assert len(batch.warnings) == 3
    # Warnings are structural, never echoing raw record content.
    assert all("SKU-1" not in warning for warning in batch.warnings)


def test_pull_sales_rows_skips_non_finite_quantities_without_crashing():
    # Regression: round(float('inf')) raises OverflowError, which is NOT in
    # the (TypeError, ValueError) tuple _extract_units_sold used to catch.
    # A single such record must not abort the whole batch/pull.
    client = _fake_client(
        [
            [
                {"sku": "SKU-1", "quantity": 1},
                {"sku": "SKU-INF", "quantity": float("inf")},
                {"sku": "SKU-NEG-INF", "quantity": float("-inf")},
                {"sku": "SKU-NAN", "quantity": float("nan")},
                {"sku": "SKU-2", "quantity": 9},
            ]
        ]
    )

    batch = pull_sales_rows(client, page_size=50)

    assert [row.sku for row in batch.rows] == ["SKU-1", "SKU-2"]
    assert batch.skipped_count == 3
    assert len(batch.warnings) == 3


def test_pull_sales_rows_handles_malformed_non_list_non_envelope_response():
    client = _fake_client(["totally-unexpected-string-response"])

    batch = pull_sales_rows(client)

    assert batch.rows == []
    assert batch.skipped_count == 0
    assert len(batch.warnings) == 1
    assert "page 1" in batch.warnings[0]


def test_pull_sales_rows_recovers_from_a_malformed_page_after_a_good_one():
    client = _fake_client(
        [
            [{"sku": "SKU-1", "quantity": 1}] * 5,  # full page -> keep paginating
            12345,  # malformed second page -> stop, but keep page 1's rows
        ]
    )

    batch = pull_sales_rows(client, page_size=5, max_pages=5)

    assert len(batch.rows) == 5
    assert any("page 2" in warning for warning in batch.warnings)


# ---------------------------------------------------------------------------
# pull_sales_rows: pagination is bounded
# ---------------------------------------------------------------------------


def test_pull_sales_rows_never_requests_more_than_max_pages():
    full_page = [{"sku": "SKU-1", "quantity": 1}] * 2
    client = _fake_client([full_page] * 10)

    batch = pull_sales_rows(client, page_size=2, max_pages=3)

    assert client.get.call_count == 3
    assert len(batch.rows) == 6
    assert any("max_pages" in warning for warning in batch.warnings)


def test_pull_sales_rows_defaults_are_bounded_constants():
    assert DEFAULT_PAGE_SIZE > 0
    assert DEFAULT_MAX_PAGES > 0


def test_pull_sales_rows_rejects_non_positive_page_size():
    client = _fake_client([])

    with pytest.raises(ValueError):
        pull_sales_rows(client, page_size=0)


def test_pull_sales_rows_rejects_non_positive_max_pages():
    client = _fake_client([])

    with pytest.raises(ValueError):
        pull_sales_rows(client, max_pages=0)


# ---------------------------------------------------------------------------
# pull_sales_rows: client errors (auth/network) are intentionally NOT
# swallowed — they must propagate, per the module/function docstrings.
# ---------------------------------------------------------------------------


def test_pull_sales_rows_propagates_fulfil_api_error():
    client = MagicMock(spec=FulfilClient)
    client.get.side_effect = FulfilAPIError(500, "/api/v2/model/sale.line")

    with pytest.raises(FulfilAPIError):
        pull_sales_rows(client)


def test_pull_sales_rows_propagates_fulfil_connection_error():
    client = MagicMock(spec=FulfilClient)
    client.get.side_effect = FulfilConnectionError("connection refused")

    with pytest.raises(FulfilConnectionError):
        pull_sales_rows(client)


# ---------------------------------------------------------------------------
# No customer PII ever reaches SalesRow / SalesStagingBatch
# ---------------------------------------------------------------------------


def test_sales_row_has_no_pii_shaped_field_names():
    forbidden = {"customer_name", "customer_email", "email", "phone", "address", "order_id"}
    field_names = {f.name for f in SalesRow.__dataclass_fields__.values()}

    assert field_names.isdisjoint(forbidden)


def test_pull_sales_rows_never_carries_customer_fields_through():
    client = _fake_client(
        [
            [
                {
                    "sku": "SKU-1",
                    "quantity": 1,
                    "customer_name": "Jane Doe",
                    "customer_email": "jane.doe@example.com",
                }
            ]
        ]
    )

    batch = pull_sales_rows(client)

    rendered = repr(batch.rows)
    assert "Jane Doe" not in rendered
    assert "jane.doe@example.com" not in rendered
