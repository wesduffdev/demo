"""Shared, package-internal plumbing for the staging pulls (BD-024 refactor).

``sales_staging.py`` (BD-008) and ``inventory_staging.py`` (BD-009) each pull
paginated records from Fulfil and shape them into a typed row. The pagination
loop, the raw-record allow-list field lookup, and the page-payload coercion
were near byte-for-byte duplicated across both modules — a double-maintenance
hazard already proven by a Wave 4 bug (a non-finite float causing
``round()`` to raise ``OverflowError``) that had to be fixed in both copies.
This module is the single place that plumbing lives; each staging module
keeps its own record -> Row mapping (``SalesRow``/``InventoryRow`` and their
allow-listed field keys) and calls :func:`paginate` here to do the pull.

This module is package-internal (leading underscore): it is not re-exported
from :mod:`buyers_desk.data_integration` and callers outside the two staging
modules should not import it directly.

No customer PII, ever
----------------------
This module never reads a raw Fulfil record's fields itself beyond the
SKU/nested-product allow-list below (:data:`_SKU_KEYS`,
:data:`_NESTED_PRODUCT_KEY`) — the per-module allow-lists for name/quantity/
cost/supplier stay in each staging module, which is also solely responsible
for deciding what a "usable" record is via the ``map_record`` callable passed
to :func:`paginate`. This module never copies a record wholesale and never
logs record content in a warning (see ``.claude/rules/no-pii.md``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Mapping, Optional, Sequence

from buyers_desk.data_integration.fulfil_client import FulfilClient
from buyers_desk.data_integration.sku import normalize_sku

__all__ = [
    "PullResult",
    "paginate",
]

# Shared allow-list: only these keys (optionally nested one level under a
# "product" object) are ever read to resolve a record's SKU. Any other key
# present on the record is never inspected here — see the no-pii note above.
_SKU_KEYS: tuple[str, ...] = ("sku", "code", "product_code")
_NESTED_PRODUCT_KEY = "product"


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


@dataclass
class PullResult:
    """The raw outcome of one :func:`paginate` call: rows plus diagnostics.

    Deliberately holds no ``source_path``/``pulled_at``/``schema_version`` —
    those are per-module ``*StagingBatch`` concerns; the calling staging
    module wraps this result in its own batch dataclass.
    """

    rows: List[Any] = field(default_factory=list)
    skipped_count: int = 0
    warnings: List[str] = field(default_factory=list)


def paginate(
    client: FulfilClient,
    path: str,
    *,
    params: Optional[Mapping[str, Any]],
    page_size: int,
    max_pages: int,
    map_record: Callable[[Any], Optional[Any]],
    record_label: str,
) -> PullResult:
    """Pull bounded pages of raw records from Fulfil and map each to a row.

    Read-only: issues bounded ``GET`` calls via ``client.get`` only (see
    ``FulfilClient``'s read-only guarantee). Pagination is capped at
    ``max_pages`` pages of ``page_size`` records each — never an unbounded
    loop (see ``.claude/rules/external-services.md``). ``map_record`` is the
    caller's own record -> Row mapping (e.g. ``sales_staging.from_fulfil_record``);
    a record it maps to ``None`` is skipped/flagged, never raised for.
    ``record_label`` (e.g. ``"sales record"``) is used only in the resulting
    skip warnings' human-readable text and never echoes raw record content.
    ``FulfilAPIError``/``FulfilConnectionError`` from the client itself
    (auth/network failure) are intentionally left to propagate.
    """
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    if max_pages <= 0:
        raise ValueError("max_pages must be positive")

    result = PullResult()
    base_params = dict(params) if params else {}
    offset = 0

    for page_number in range(1, max_pages + 1):
        page_params = {**base_params, "limit": page_size, "offset": offset}
        payload = client.get(path, params=page_params)
        records = _coerce_page_records(payload)

        if records is None:
            result.warnings.append(
                f"page {page_number}: response was not a list or a recognized envelope "
                f"(type={type(payload).__name__}); stopped pulling further pages"
            )
            break

        if not records:
            break

        for index, record in enumerate(records):
            row = map_record(record)
            if row is None:
                result.skipped_count += 1
                result.warnings.append(
                    f"page {page_number} record {index}: skipped (not a usable {record_label})"
                )
                continue
            result.rows.append(row)

        if len(records) < page_size:
            break

        offset += page_size
    else:
        result.warnings.append(
            f"reached max_pages={max_pages} with a full last page; more data may remain"
        )

    return result
