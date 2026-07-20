"""Raw inventory staging pull from Fulfil (BD-009).

Scope
-----
This module pulls raw stock-on-hand / inventory attribute data via the
read-only :class:`~buyers_desk.data_integration.fulfil_client.FulfilClient`
and shapes each usable Fulfil record into a typed, versioned
:class:`InventoryRow` — the **staged**, per-source-record form. It
deliberately does **not** reconcile with sales or build the
:class:`~buyers_desk.contracts.DataSnapshot` (that is BD-011). Unlike sales
(where one SKU may span many order-line records), an inventory pull is
expected to carry at most one usable record per SKU per warehouse/location;
any per-SKU de-duplication across locations is part of BD-011's
reconcile+aggregate step, not this one.

No customer PII, ever
----------------------
Fields are read from each raw Fulfil record via an explicit **allow-list**
(:data:`_SKU_KEYS`, :data:`_NAME_KEYS`, :data:`_ON_HAND_KEYS`,
:data:`_COST_KEYS`, :data:`_SUPPLIER_KEYS`) — never by copying the record
wholesale. A supplier *business* name is an allowed product/business
attribute (matches :class:`~buyers_desk.contracts.SnapshotRow.supplier`),
but a nested supplier object is only ever read for a business-name sub-field
(:data:`_SUPPLIER_NAME_SUBKEYS`); a supplier's contact fields (email, phone,
a rep's personal name) are structurally never read, even if present on the
raw record. No customer/order-identity field is ever read either.
``InventoryRow`` has exactly the fields listed below and no field for any
person identity is ever added here (see ``.claude/rules/no-pii.md``).

SKU key convention (must match BD-008)
---------------------------------------
``sku`` is normalized via
:func:`buyers_desk.data_integration.sku.normalize_sku` (the same function
BD-008's sales staging imports), so both staged datasets key identically
(``str(raw).strip().upper()``; unusable input normalizes to ``None`` and the
record is skipped) for BD-011's reconciliation join.

Fulfil response shape — labeled assumption
--------------------------------------------
There is no live Fulfil connection in this environment, so the exact
inventory endpoint/response shape is a **documented assumption**, not a
confirmed contract (mirrors BD-008's sales assumption):

* Default path (:data:`INVENTORY_PATH`) assumes a product/stock-quantity
  model (``/api/v2/model/product.product``), matching Fulfil's generic
  ``/api/v2/model/<model_name>`` REST scheme also used by
  :data:`~buyers_desk.data_integration.fulfil_client.HEALTH_PATH` and
  :data:`~buyers_desk.data_integration.sales_staging.SALES_PATH`. Callers
  may override ``path`` once a real Fulfil connection confirms the model
  name. (Whether that connection is sandbox or production is controlled by
  ``FULFIL_BASE_URL``/config, not by anything in this module — see
  ``buyers_desk/config.py``.)
* Each record is assumed to be a JSON object exposing the SKU/code under one
  of :data:`_SKU_KEYS` (optionally nested one level under a ``"product"``
  object), a display name under one of :data:`_NAME_KEYS`, an on-hand
  quantity under one of :data:`_ON_HAND_KEYS`, and optionally a unit cost
  under one of :data:`_COST_KEYS` and a supplier under one of
  :data:`_SUPPLIER_KEYS` (a plain string, or a nested object read only for a
  business-name sub-field). Unknown/extra fields are ignored; a record
  missing a usable SKU or on-hand quantity is skipped, not raised — cost and
  supplier are optional and simply left ``None`` when absent/unusable.
* Pagination is assumed to follow the same generic ``limit``/``offset``
  convention as BD-008 and is bounded the same way: at most
  :data:`DEFAULT_MAX_PAGES` pages of at most ``page_size`` records each are
  ever requested per call to :func:`pull_inventory_rows` (see
  ``.claude/rules/external-services.md``).

Partial / empty / malformed responses never crash the pull: they are
recorded as human-readable, content-free diagnostics on
``InventoryStagingBatch.warnings`` (never echoing raw record content) and
the pull returns whatever was already collected. Network/auth failures from
the client itself (:class:`FulfilAPIError`, :class:`FulfilConnectionError`)
are **not** swallowed here — those mean Fulfil could not be reached /
rejected the request at all, which should abort the cycle loudly rather than
silently returning an empty snapshot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, List, Mapping, Optional, Sequence

from buyers_desk.data_integration.fulfil_client import FulfilClient
from buyers_desk.data_integration.sku import normalize_sku

__all__ = [
    "INVENTORY_PATH",
    "DEFAULT_PAGE_SIZE",
    "DEFAULT_MAX_PAGES",
    "InventoryRow",
    "InventoryStagingBatch",
    "from_fulfil_record",
    "pull_inventory_rows",
]

#: Assumed Fulfil model endpoint for product/stock records — see the module
#: docstring's "labeled assumption" section. Override via
#: ``pull_inventory_rows``'s ``path`` argument once a real Fulfil connection
#: confirms the model name (sandbox vs. production is a config/
#: ``FULFIL_BASE_URL`` choice, not this module's).
INVENTORY_PATH = "/api/v2/model/product.product"

#: Bounded pagination defaults (external-services rule: never an unbounded
#: loop of paid API calls). ``pull_inventory_rows`` requests at most
#: ``DEFAULT_MAX_PAGES`` pages of at most ``DEFAULT_PAGE_SIZE`` records.
DEFAULT_PAGE_SIZE = 500
DEFAULT_MAX_PAGES = 20

# Allow-lists: only these keys are ever read off a raw Fulfil record. Any
# other key present on the record (including a customer/order-identity
# field or a supplier contact field) is never inspected, copied, or logged
# — see the no-pii note above.
_SKU_KEYS: tuple[str, ...] = ("sku", "code", "product_code")
_NAME_KEYS: tuple[str, ...] = ("product_name", "name", "description")
_ON_HAND_KEYS: tuple[str, ...] = (
    "on_hand_units",
    "quantity_on_hand",
    "quantity",
    "qty",
    "stock_quantity",
)
_COST_KEYS: tuple[str, ...] = ("unit_cost", "cost", "average_cost", "cost_price")
_SUPPLIER_KEYS: tuple[str, ...] = ("supplier", "supplier_name", "vendor", "vendor_name")
# When a supplier field is a nested object rather than a plain string, only
# ever read a business-name sub-field from it — never a contact field
# (email, phone, a rep's personal name). See module docstring's no-pii note.
_SUPPLIER_NAME_SUBKEYS: tuple[str, ...] = ("name", "supplier_name", "company_name")
_NESTED_PRODUCT_KEY = "product"


@dataclass(frozen=True)
class InventoryRow:
    """One staged inventory fact for one Fulfil record. Product/SKU-level only.

    Field names deliberately match
    :class:`buyers_desk.contracts.SnapshotRow` where they overlap (``sku``,
    ``product_name``, ``on_hand_units``, ``unit_cost``, ``supplier``) so
    BD-011's reconciliation is a straight rename/merge, not a re-mapping.
    """

    SCHEMA_VERSION: ClassVar[int] = 1

    sku: str
    on_hand_units: int
    product_name: Optional[str] = None
    unit_cost: Optional[float] = None
    supplier: Optional[str] = None


@dataclass
class InventoryStagingBatch:
    """The result of one :func:`pull_inventory_rows` call.

    ``rows`` is the staged, per-record inventory data; ``skipped_count`` and
    ``warnings`` surface partial/malformed input without ever raising for
    it. ``schema_version`` travels with the batch so a later file-based
    write (BD-011) can record which shape produced it.
    """

    source_path: str
    pulled_at: datetime
    rows: List[InventoryRow] = field(default_factory=list)
    skipped_count: int = 0
    warnings: List[str] = field(default_factory=list)
    schema_version: int = InventoryRow.SCHEMA_VERSION


def _first_present(record: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None:
            return value
    return None


def _nested_product(record: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    nested = record.get(_NESTED_PRODUCT_KEY)
    return nested if isinstance(nested, Mapping) else None


def _extract_sku(record: Mapping[str, Any]) -> Optional[str]:
    raw = _first_present(record, _SKU_KEYS)
    if raw is None:
        nested = _nested_product(record)
        if nested is not None:
            raw = _first_present(nested, _SKU_KEYS)
    return normalize_sku(raw)


def _extract_product_name(record: Mapping[str, Any]) -> Optional[str]:
    raw = _first_present(record, _NAME_KEYS)
    if raw is None:
        nested = _nested_product(record)
        if nested is not None:
            raw = _first_present(nested, _NAME_KEYS)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _extract_on_hand_units(record: Mapping[str, Any]) -> Optional[int]:
    """Coerce the record's on-hand quantity field to an ``int``, or ``None``
    if unusable.

    Rounds with Python's built-in :func:`round`, which uses banker's
    rounding (round-half-to-even) — e.g. ``round(2.5) == 2``, not 3. Callers
    (BD-011) should not assume round-half-up.
    """
    raw = _first_present(record, _ON_HAND_KEYS)
    # bool is a subclass of int in Python; a stray True/False is not a
    # legitimate quantity even though float(True) would otherwise "work".
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    # `json.loads` accepts `Infinity`/`-Infinity`/`NaN` tokens by default, so
    # a value that survives the float() coercion above may still be
    # non-finite. round(float('inf')) raises OverflowError (not TypeError/
    # ValueError), which would otherwise crash the whole pull on one bad
    # record — treat non-finite the same as any other unusable quantity.
    if not math.isfinite(value):
        return None
    return round(value)


def _extract_unit_cost(record: Mapping[str, Any]) -> Optional[float]:
    raw = _first_present(record, _COST_KEYS)
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    # A non-finite cost (inf/-inf/nan) is not a usable unit cost even though
    # float() happily accepts it — treat it as unusable, consistent with the
    # on-hand-quantity guard above.
    if not math.isfinite(value):
        return None
    return value


def _extract_supplier(record: Mapping[str, Any]) -> Optional[str]:
    raw = _first_present(record, _SUPPLIER_KEYS)
    if isinstance(raw, Mapping):
        # Nested supplier object: only ever read a business-name field —
        # never a contact field. See the module docstring's no-pii note.
        raw = _first_present(raw, _SUPPLIER_NAME_SUBKEYS)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def from_fulfil_record(record: Any) -> Optional[InventoryRow]:
    """Map one raw, untrusted Fulfil record to an :class:`InventoryRow`.

    Tolerant by design: a record that is not a mapping, or is missing a
    usable SKU or a numeric on-hand quantity, is **skipped** (returns
    ``None``) rather than raising. ``unit_cost`` and ``supplier`` are
    optional and simply left ``None`` when absent/unusable — they never
    cause the whole record to be skipped. Extra/unknown fields on the
    record — including any customer/order-identity field or supplier
    contact field — are silently ignored; only the allow-listed keys
    documented on this module are ever read.
    """
    if not isinstance(record, Mapping):
        return None

    sku = _extract_sku(record)
    if sku is None:
        return None

    on_hand_units = _extract_on_hand_units(record)
    if on_hand_units is None:
        return None

    return InventoryRow(
        sku=sku,
        on_hand_units=on_hand_units,
        product_name=_extract_product_name(record),
        unit_cost=_extract_unit_cost(record),
        supplier=_extract_supplier(record),
    )


def _coerce_page_records(payload: Any) -> Optional[list[Any]]:
    """Normalize one page's raw JSON payload to a list of raw records.

    Returns ``[]`` for an empty/``None`` body (nothing more to read, not an
    error). Returns ``None`` when ``payload`` is not a list and not a
    recognized ``{"records": [...]}``-style envelope — a genuinely malformed
    page the caller should stop on rather than misinterpret.
    """
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, Mapping):
        for key in ("records", "result", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return None


def pull_inventory_rows(
    client: FulfilClient,
    *,
    path: str = INVENTORY_PATH,
    params: Optional[Mapping[str, Any]] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> InventoryStagingBatch:
    """Pull raw inventory records from Fulfil and stage them as ``InventoryRow``s.

    Read-only: issues bounded ``GET`` calls via ``client.get`` only (see
    ``FulfilClient``'s read-only guarantee). Pagination is capped at
    ``max_pages`` pages of ``page_size`` records each — never an unbounded
    loop. A malformed page, an empty page, or an individual malformed record
    is handled by skipping/flagging (via ``skipped_count``/``warnings``) —
    this function never raises for bad *data*. ``FulfilAPIError`` and
    ``FulfilConnectionError`` from the client itself (auth/network failure)
    are intentionally left to propagate — see the module docstring.
    """
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    if max_pages <= 0:
        raise ValueError("max_pages must be positive")

    batch = InventoryStagingBatch(source_path=path, pulled_at=datetime.now(timezone.utc))
    base_params = dict(params) if params else {}
    offset = 0

    for page_number in range(1, max_pages + 1):
        page_params = {**base_params, "limit": page_size, "offset": offset}
        payload = client.get(path, params=page_params)
        records = _coerce_page_records(payload)

        if records is None:
            batch.warnings.append(
                f"page {page_number}: response was not a list or a recognized envelope "
                f"(type={type(payload).__name__}); stopped pulling further pages"
            )
            break

        if not records:
            break

        for index, record in enumerate(records):
            row = from_fulfil_record(record)
            if row is None:
                batch.skipped_count += 1
                batch.warnings.append(
                    f"page {page_number} record {index}: skipped (not a usable inventory record)"
                )
                continue
            batch.rows.append(row)

        if len(records) < page_size:
            break

        offset += page_size
    else:
        batch.warnings.append(
            f"reached max_pages={max_pages} with a full last page; more data may remain"
        )

    return batch
