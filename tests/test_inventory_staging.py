"""Tests for BD-009 raw inventory staging pull
(``buyers_desk/data_integration/inventory_staging.py``).

No live network calls: ``FulfilClient.get`` is replaced with a fake/mock
(no ``requests`` session is ever exercised here — that is BD-005's own test
file). All fixture data is synthetic (fake SKUs/product names/supplier
names), and no fixture ever carries a customer/order-identity field or a
supplier contact field, per the no-pii rule.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from buyers_desk.data_integration import (
    DEFAULT_MAX_PAGES,
    DEFAULT_PAGE_SIZE,
    InventoryRow,
    InventoryStagingBatch,
    SalesRow,
    inventory_from_fulfil_record,
    normalize_sku,
    pull_inventory_rows,
)
from buyers_desk.data_integration.fulfil_client import (
    FulfilAPIError,
    FulfilClient,
    FulfilConnectionError,
)
from buyers_desk.data_integration.sales_staging import (
    from_fulfil_record as sales_from_fulfil_record,
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
    row = inventory_from_fulfil_record(
        {
            "sku": "abc-123",
            "product_name": "Fake Snack",
            "quantity": 40,
            "unit_cost": 2.5,
            "supplier": "Acme Test Supplier",
        }
    )

    assert row == InventoryRow(
        sku="ABC-123",
        on_hand_units=40,
        product_name="Fake Snack",
        unit_cost=2.5,
        supplier="Acme Test Supplier",
    )


def test_from_fulfil_record_accepts_nested_product_object():
    row = inventory_from_fulfil_record(
        {"product": {"code": "sku-9", "name": "Nested Widget"}, "quantity_on_hand": 12}
    )

    assert row is not None
    assert row.sku == "SKU-9"
    assert row.product_name == "Nested Widget"
    assert row.on_hand_units == 12


def test_from_fulfil_record_accepts_nested_supplier_object_name_only():
    row = inventory_from_fulfil_record(
        {
            "sku": "SKU-10",
            "quantity": 5,
            "supplier": {
                "name": "Fake Vendor Co",
                # Contact fields on a nested supplier object must never be
                # read, even though they are present on the raw record.
                "email": "rep@example.com",
                "phone": "555-0100",
                "contact_name": "Jane Doe",
            },
        }
    )

    assert row is not None
    assert row.supplier == "Fake Vendor Co"
    assert not hasattr(row, "email")
    assert not hasattr(row, "phone")
    assert not hasattr(row, "contact_name")


def test_from_fulfil_record_ignores_unknown_and_customer_fields():
    row = inventory_from_fulfil_record(
        {
            "sku": "SKU-1",
            "quantity": 10,
            # None of these are on the allow-list; they must never surface
            # on the resulting InventoryRow (no-pii rule).
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
    assert set(vars(row)) == {"sku", "on_hand_units", "product_name", "unit_cost", "supplier"}


def test_from_fulfil_record_returns_none_for_non_mapping():
    assert inventory_from_fulfil_record("not-a-record") is None
    assert inventory_from_fulfil_record(["also", "not", "a", "record"]) is None
    assert inventory_from_fulfil_record(None) is None


def test_from_fulfil_record_returns_none_when_sku_missing():
    assert inventory_from_fulfil_record({"product_name": "No SKU Here", "quantity": 3}) is None


def test_from_fulfil_record_returns_none_when_sku_blank():
    assert inventory_from_fulfil_record({"sku": "   ", "quantity": 3}) is None


def test_from_fulfil_record_returns_none_when_on_hand_missing():
    assert inventory_from_fulfil_record({"sku": "SKU-2", "product_name": "No Qty"}) is None


def test_from_fulfil_record_returns_none_when_on_hand_not_numeric():
    assert inventory_from_fulfil_record({"sku": "SKU-3", "quantity": "a-lot"}) is None


@pytest.mark.parametrize("bad_quantity", [float("inf"), float("-inf"), float("nan")])
def test_from_fulfil_record_returns_none_for_non_finite_on_hand(bad_quantity):
    # json.loads accepts Infinity/-Infinity/NaN tokens by default, so these
    # can arrive straight out of a Fulfil response body. round(float('inf'))
    # raises OverflowError (not caught by the TypeError/ValueError guard),
    # which must never propagate out of this "never raises for bad data"
    # module — the record is skipped, exactly like any other bad quantity.
    assert inventory_from_fulfil_record({"sku": "SKU-3", "quantity": bad_quantity}) is None


def test_from_fulfil_record_treats_infinite_unit_cost_as_unusable():
    # inf survives float() without raising, so it doesn't crash — but it is
    # not a usable cost value; treat it the same as any other bad unit_cost
    # (record kept, unit_cost left None) for data-quality consistency.
    row = inventory_from_fulfil_record({"sku": "SKU-9", "quantity": 3, "unit_cost": float("inf")})

    assert row is not None
    assert row.on_hand_units == 3
    assert row.unit_cost is None


def test_from_fulfil_record_returns_none_for_boolean_on_hand():
    # bool is a subclass of int in Python; must not be treated as a quantity.
    assert inventory_from_fulfil_record({"sku": "SKU-4", "quantity": True}) is None


def test_from_fulfil_record_tolerates_missing_optional_fields():
    row = inventory_from_fulfil_record({"sku": "SKU-5", "quantity": 7})

    assert row == InventoryRow(
        sku="SKU-5", on_hand_units=7, product_name=None, unit_cost=None, supplier=None
    )


def test_from_fulfil_record_rounds_fractional_on_hand():
    row = inventory_from_fulfil_record({"sku": "SKU-6", "quantity": 2.6})

    assert row is not None
    assert row.on_hand_units == 3
    assert isinstance(row.on_hand_units, int)


def test_from_fulfil_record_preserves_negative_on_hand_as_a_raw_fact():
    # A negative on-hand count (e.g. an oversold/backorder state in Fulfil)
    # is a legitimate raw fact; clamping/netting is a later (BD-011)
    # decision, not this staging layer's job.
    row = inventory_from_fulfil_record({"sku": "SKU-7", "quantity": -2})

    assert row is not None
    assert row.on_hand_units == -2


def test_from_fulfil_record_ignores_non_numeric_unit_cost_but_keeps_record():
    row = inventory_from_fulfil_record({"sku": "SKU-8", "quantity": 3, "unit_cost": "n/a"})

    assert row is not None
    assert row.on_hand_units == 3
    assert row.unit_cost is None


def test_from_fulfil_record_ignores_boolean_unit_cost():
    row = inventory_from_fulfil_record({"sku": "SKU-8", "quantity": 3, "unit_cost": True})

    assert row is not None
    assert row.unit_cost is None


def test_from_fulfil_record_tolerates_blank_supplier():
    row = inventory_from_fulfil_record({"sku": "SKU-8", "quantity": 3, "supplier": "   "})

    assert row is not None
    assert row.supplier is None


# ---------------------------------------------------------------------------
# SKU key normalization (must match BD-008's sales staging exactly)
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
    row = inventory_from_fulfil_record({"sku": "  sku-42  ", "quantity": 1})

    assert row is not None
    assert row.sku == normalize_sku("  sku-42  ")


def test_inventory_and_sales_staging_produce_the_same_sku_key_for_the_same_raw_input():
    """Reconciliation contract (acceptance criterion #2): BD-008 and BD-009
    MUST key identically on the same raw SKU value, otherwise BD-011's join
    silently drops rows. This asserts both staging modules resolve the same
    raw, oddly-cased/whitespace-padded SKU to the identical normalized key.
    """
    raw_sku = "  wid-Get-99  "

    sales_row = sales_from_fulfil_record({"sku": raw_sku, "quantity": 1})
    inventory_row = inventory_from_fulfil_record({"sku": raw_sku, "quantity": 5})

    assert sales_row is not None
    assert inventory_row is not None
    assert sales_row.sku == inventory_row.sku == normalize_sku(raw_sku)
    assert isinstance(sales_row, SalesRow)
    assert isinstance(inventory_row, InventoryRow)


def test_inventory_and_sales_staging_agree_on_nested_product_sku():
    """Same contract as above, exercised through each module's nested
    ``"product"`` object path (a Fulfil shape both modules independently
    document as an assumption)."""
    nested = {"product": {"code": "  nested-Sku-1  "}}

    sales_row = sales_from_fulfil_record({**nested, "quantity": 1})
    inventory_row = inventory_from_fulfil_record({**nested, "quantity": 5})

    assert sales_row is not None
    assert inventory_row is not None
    assert sales_row.sku == inventory_row.sku == "NESTED-SKU-1"


# ---------------------------------------------------------------------------
# pull_inventory_rows: happy path
# ---------------------------------------------------------------------------


def test_pull_inventory_rows_happy_path_maps_well_formed_records():
    client = _fake_client(
        [
            [
                {
                    "sku": "SKU-100",
                    "product_name": "Fake Widget",
                    "quantity": 25,
                    "unit_cost": 4.2,
                    "supplier": "Fake Supplier A",
                },
                {"sku": "sku-101", "product_name": "Fake Gadget", "quantity": 0},
            ]
        ]
    )

    batch = pull_inventory_rows(client, page_size=50)

    assert isinstance(batch, InventoryStagingBatch)
    assert batch.rows == [
        InventoryRow(
            sku="SKU-100",
            on_hand_units=25,
            product_name="Fake Widget",
            unit_cost=4.2,
            supplier="Fake Supplier A",
        ),
        InventoryRow(sku="SKU-101", on_hand_units=0, product_name="Fake Gadget"),
    ]
    assert batch.skipped_count == 0
    assert batch.warnings == []
    assert isinstance(batch.pulled_at, datetime)
    assert batch.schema_version == InventoryRow.SCHEMA_VERSION


def test_pull_inventory_rows_stops_after_a_short_page_without_a_second_call():
    client = _fake_client([[{"sku": "SKU-1", "quantity": 1}]])

    pull_inventory_rows(client, page_size=50)

    assert client.get.call_count == 1


def test_pull_inventory_rows_uses_bounded_limit_offset_params():
    client = _fake_client([[{"sku": "SKU-1", "quantity": 1}] * 3, []])

    pull_inventory_rows(client, page_size=3, max_pages=5)

    first_call_kwargs = client.get.call_args_list[0].kwargs
    second_call_kwargs = client.get.call_args_list[1].kwargs
    assert first_call_kwargs["params"]["limit"] == 3
    assert first_call_kwargs["params"]["offset"] == 0
    assert second_call_kwargs["params"]["offset"] == 3


# ---------------------------------------------------------------------------
# pull_inventory_rows: empty responses handled without crashing
# ---------------------------------------------------------------------------


def test_pull_inventory_rows_handles_none_response():
    client = _fake_client([None])

    batch = pull_inventory_rows(client)

    assert batch.rows == []
    assert batch.skipped_count == 0
    assert batch.warnings == []


def test_pull_inventory_rows_handles_empty_list_response():
    client = _fake_client([[]])

    batch = pull_inventory_rows(client)

    assert batch.rows == []
    assert batch.skipped_count == 0


def test_pull_inventory_rows_handles_empty_envelope_dict():
    client = _fake_client([{"records": []}])

    batch = pull_inventory_rows(client)

    assert batch.rows == []


# ---------------------------------------------------------------------------
# pull_inventory_rows: partial / malformed responses handled without crashing
# ---------------------------------------------------------------------------


def test_pull_inventory_rows_skips_malformed_records_and_keeps_good_ones():
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

    batch = pull_inventory_rows(client, page_size=50)

    assert [row.sku for row in batch.rows] == ["SKU-1", "SKU-3"]
    assert batch.skipped_count == 3
    assert len(batch.warnings) == 3
    # Warnings are structural, never echoing raw record content.
    assert all("SKU-1" not in warning for warning in batch.warnings)


def test_pull_inventory_rows_skips_non_finite_on_hand_without_crashing():
    # Regression: round(float('inf')) raises OverflowError, which is NOT in
    # the (TypeError, ValueError) tuple _extract_on_hand_units used to catch.
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

    batch = pull_inventory_rows(client, page_size=50)

    assert [row.sku for row in batch.rows] == ["SKU-1", "SKU-2"]
    assert batch.skipped_count == 3
    assert len(batch.warnings) == 3


def test_pull_inventory_rows_handles_malformed_non_list_non_envelope_response():
    client = _fake_client(["totally-unexpected-string-response"])

    batch = pull_inventory_rows(client)

    assert batch.rows == []
    assert batch.skipped_count == 0
    assert len(batch.warnings) == 1
    assert "page 1" in batch.warnings[0]


def test_pull_inventory_rows_recovers_from_a_malformed_page_after_a_good_one():
    client = _fake_client(
        [
            [{"sku": "SKU-1", "quantity": 1}] * 5,  # full page -> keep paginating
            12345,  # malformed second page -> stop, but keep page 1's rows
        ]
    )

    batch = pull_inventory_rows(client, page_size=5, max_pages=5)

    assert len(batch.rows) == 5
    assert any("page 2" in warning for warning in batch.warnings)


# ---------------------------------------------------------------------------
# pull_inventory_rows: pagination is bounded
# ---------------------------------------------------------------------------


def test_pull_inventory_rows_never_requests_more_than_max_pages():
    full_page = [{"sku": "SKU-1", "quantity": 1}] * 2
    client = _fake_client([full_page] * 10)

    batch = pull_inventory_rows(client, page_size=2, max_pages=3)

    assert client.get.call_count == 3
    assert len(batch.rows) == 6
    assert any("max_pages" in warning for warning in batch.warnings)


def test_pull_inventory_rows_defaults_are_bounded_constants():
    assert DEFAULT_PAGE_SIZE > 0
    assert DEFAULT_MAX_PAGES > 0


def test_pull_inventory_rows_rejects_non_positive_page_size():
    client = _fake_client([])

    with pytest.raises(ValueError):
        pull_inventory_rows(client, page_size=0)


def test_pull_inventory_rows_rejects_non_positive_max_pages():
    client = _fake_client([])

    with pytest.raises(ValueError):
        pull_inventory_rows(client, max_pages=0)


# ---------------------------------------------------------------------------
# pull_inventory_rows: client errors (auth/network) are intentionally NOT
# swallowed — they must propagate, per the module/function docstrings.
# ---------------------------------------------------------------------------


def test_pull_inventory_rows_propagates_fulfil_api_error():
    client = MagicMock(spec=FulfilClient)
    client.get.side_effect = FulfilAPIError(500, "/api/v2/model/product.product")

    with pytest.raises(FulfilAPIError):
        pull_inventory_rows(client)


def test_pull_inventory_rows_propagates_fulfil_connection_error():
    client = MagicMock(spec=FulfilClient)
    client.get.side_effect = FulfilConnectionError("connection refused")

    with pytest.raises(FulfilConnectionError):
        pull_inventory_rows(client)


# ---------------------------------------------------------------------------
# No customer PII / supplier contact PII ever reaches InventoryRow / batch
# ---------------------------------------------------------------------------


def test_inventory_row_has_no_pii_shaped_field_names():
    forbidden = {
        "customer_name",
        "customer_email",
        "email",
        "phone",
        "address",
        "order_id",
        "contact_name",
    }
    field_names = {f.name for f in InventoryRow.__dataclass_fields__.values()}

    assert field_names.isdisjoint(forbidden)


def test_pull_inventory_rows_never_carries_customer_or_supplier_contact_fields_through():
    client = _fake_client(
        [
            [
                {
                    "sku": "SKU-1",
                    "quantity": 1,
                    "customer_name": "Jane Doe",
                    "customer_email": "jane.doe@example.com",
                    "supplier": {
                        "name": "Fake Vendor Co",
                        "email": "rep@example.com",
                        "phone": "555-0100",
                    },
                }
            ]
        ]
    )

    batch = pull_inventory_rows(client)

    rendered = repr(batch.rows)
    assert "Jane Doe" not in rendered
    assert "jane.doe@example.com" not in rendered
    assert "rep@example.com" not in rendered
    assert "555-0100" not in rendered
    assert "Fake Vendor Co" in rendered
