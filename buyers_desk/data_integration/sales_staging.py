"""Raw sales staging pull from Fulfil (BD-008).

Scope
-----
This module pulls raw sales/transaction data via the read-only
:class:`~buyers_desk.data_integration.fulfil_client.FulfilClient` and shapes
each usable Fulfil record into a typed, versioned :class:`SalesRow` — the
**staged**, per-source-record form. It deliberately does **not** reconcile
with inventory or build the :class:`~buyers_desk.contracts.DataSnapshot`
(that is BD-011). A single SKU may appear on multiple ``SalesRow`` entries
(one Fulfil sales record can be one order line among many for that product);
summing ``units_sold`` per ``sku`` to get a single per-product total is part
of BD-011's reconcile+aggregate step, not this one.

No customer PII, ever
----------------------
Fields are read from each raw Fulfil record via an explicit **allow-list**
(:data:`_SKU_KEYS`, :data:`_NAME_KEYS`, :data:`_QUANTITY_KEYS`) — never by
copying the record wholesale. Any customer/order-identity field a Fulfil
sales record happens to carry (customer name, email, address, order/party
id, etc.) is structurally never read and therefore never reaches a
``SalesRow``, satisfying the no-pii rule by construction rather than by a
denylist that could be incomplete. ``SalesRow`` has exactly three fields —
``sku``, ``units_sold``, ``product_name`` — and no field for any
person/order identity is ever added here (see ``.claude/rules/no-pii.md``).

SKU key convention (BD-009 must match)
---------------------------------------
``sku`` is normalized via :func:`buyers_desk.data_integration.sku.normalize_sku`
(``str(raw).strip().upper()``). BD-009's inventory staging pull MUST use the
same function so the two staged datasets reconcile on identical keys in
BD-011.

Fulfil response shape — labeled assumption
--------------------------------------------
There is no live Fulfil connection in this environment, so the exact sales
endpoint/response shape is a **documented assumption**, not a confirmed
contract:

* Default path (:data:`SALES_PATH`) assumes a sale *line* model
  (``/api/v2/model/sale.line``) so each record already carries a
  product-level quantity, matching Fulfil's generic
  ``/api/v2/model/<model_name>`` REST scheme also used by
  :data:`~buyers_desk.data_integration.fulfil_client.HEALTH_PATH`. Callers
  may override ``path`` once a real Fulfil connection confirms the model
  name. (Whether that connection is sandbox or production is controlled by
  ``FULFIL_BASE_URL``/config, not by anything in this module — see
  ``buyers_desk/config.py``.)
* Each record is assumed to be a JSON object exposing the SKU/code under one
  of :data:`_SKU_KEYS` (optionally nested one level under a ``"product"``
  object), a display name under one of :data:`_NAME_KEYS`, and a numeric
  quantity under one of :data:`_QUANTITY_KEYS`. Unknown/extra fields are
  ignored; a record missing a usable SKU or quantity is skipped, not raised.
* Pagination is assumed to follow a generic ``limit``/``offset`` convention.
  It is always bounded: at most :data:`DEFAULT_MAX_PAGES` pages of at most
  ``page_size`` records each are ever requested per call to
  :func:`pull_sales_rows`, so a single pull can never become an unbounded
  loop of paid API calls (see ``.claude/rules/external-services.md``).

Partial / empty / malformed responses never crash the pull: they are
recorded as human-readable, content-free diagnostics on
``SalesStagingBatch.warnings`` (never echoing raw record content, so a
warning can never itself leak a stray PII-shaped value) and the pull returns
whatever was already collected. Network/auth failures from the client
itself (:class:`FulfilAPIError`, :class:`FulfilConnectionError`) are **not**
swallowed here — those mean Fulfil could not be reached / rejected the
request at all, which should abort the cycle loudly rather than silently
returning an empty snapshot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, List, Mapping, Optional, Sequence

from buyers_desk.data_integration.fulfil_client import FulfilClient
from buyers_desk.data_integration.sku import normalize_sku

__all__ = [
    "SALES_PATH",
    "DEFAULT_PAGE_SIZE",
    "DEFAULT_MAX_PAGES",
    "SalesRow",
    "SalesStagingBatch",
    "from_fulfil_record",
    "pull_sales_rows",
]

#: Assumed Fulfil model endpoint for sale line items — see the module
#: docstring's "labeled assumption" section. Override via ``pull_sales_rows``'s
#: ``path`` argument once a real Fulfil connection confirms the model name
#: (sandbox vs. production is a config/``FULFIL_BASE_URL`` choice, not this
#: module's).
SALES_PATH = "/api/v2/model/sale.line"

#: Bounded pagination defaults (external-services rule: never an unbounded
#: loop of paid API calls). ``pull_sales_rows`` requests at most
#: ``DEFAULT_MAX_PAGES`` pages of at most ``DEFAULT_PAGE_SIZE`` records.
DEFAULT_PAGE_SIZE = 500
DEFAULT_MAX_PAGES = 20

# Allow-lists: only these keys are ever read off a raw Fulfil record. Any
# other key present on the record (including a customer/order-identity
# field) is never inspected, copied, or logged — see the no-pii note above.
_SKU_KEYS: tuple[str, ...] = ("sku", "code", "product_code")
_NAME_KEYS: tuple[str, ...] = ("product_name", "name", "description")
_QUANTITY_KEYS: tuple[str, ...] = ("units_sold", "quantity_sold", "quantity", "qty")
_NESTED_PRODUCT_KEY = "product"


@dataclass(frozen=True)
class SalesRow:
    """One staged sales fact for one Fulfil record. Product/SKU-level only.

    Field names deliberately match :class:`buyers_desk.contracts.SnapshotRow`
    where they overlap (``sku``, ``product_name``, ``units_sold``) so BD-011's
    reconciliation is a straight rename/sum, not a re-mapping.
    """

    SCHEMA_VERSION: ClassVar[int] = 1

    sku: str
    units_sold: int
    product_name: Optional[str] = None


@dataclass
class SalesStagingBatch:
    """The result of one :func:`pull_sales_rows` call.

    ``rows`` is the staged, per-record sales data; ``skipped_count`` and
    ``warnings`` surface partial/malformed input without ever raising for
    it. ``schema_version`` travels with the batch so a later file-based
    write (BD-011) can record which shape produced it.
    """

    source_path: str
    pulled_at: datetime
    rows: List[SalesRow] = field(default_factory=list)
    skipped_count: int = 0
    warnings: List[str] = field(default_factory=list)
    schema_version: int = SalesRow.SCHEMA_VERSION


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


def _extract_units_sold(record: Mapping[str, Any]) -> Optional[int]:
    """Coerce the record's quantity field to an ``int``, or ``None`` if unusable.

    Rounds with Python's built-in :func:`round`, which uses banker's
    rounding (round-half-to-even) — e.g. ``round(2.5) == 2``, not 3. Callers
    (BD-011) should not assume round-half-up.
    """
    raw = _first_present(record, _QUANTITY_KEYS)
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


def from_fulfil_record(record: Any) -> Optional[SalesRow]:
    """Map one raw, untrusted Fulfil record to a :class:`SalesRow`.

    Tolerant by design: a record that is not a mapping, or is missing a
    usable SKU or a numeric quantity, is **skipped** (returns ``None``)
    rather than raising. Extra/unknown fields on the record — including any
    customer/order-identity field — are silently ignored; only the
    allow-listed keys documented on this module are ever read.
    """
    if not isinstance(record, Mapping):
        return None

    sku = _extract_sku(record)
    if sku is None:
        return None

    units_sold = _extract_units_sold(record)
    if units_sold is None:
        return None

    return SalesRow(sku=sku, units_sold=units_sold, product_name=_extract_product_name(record))


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


def pull_sales_rows(
    client: FulfilClient,
    *,
    path: str = SALES_PATH,
    params: Optional[Mapping[str, Any]] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> SalesStagingBatch:
    """Pull raw sales records from Fulfil and stage them as ``SalesRow``s.

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

    batch = SalesStagingBatch(source_path=path, pulled_at=datetime.now(timezone.utc))
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
                    f"page {page_number} record {index}: skipped (not a usable sales record)"
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
