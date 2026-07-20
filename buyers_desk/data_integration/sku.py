"""Canonical SKU key normalization, shared across staging pulls (BD-008/BD-009).

Sales staging (BD-008, ``sales_staging.py``) and inventory staging (BD-009,
``inventory_staging.py``) are pulled from two different Fulfil endpoints and
must reconcile on the SAME product key in BD-011. This module is the single
place that normalization lives so both staging pulls import the exact same
function rather than each inventing their own (slightly different) rule.

Canonical form: ``str(raw).strip().upper()``. Rationale:

* ``str(...)`` tolerates a SKU that Fulfil serializes as a number (e.g. a
  purely-numeric product code) as well as the common string case.
* ``.strip()`` absorbs incidental leading/trailing whitespace from manual
  entry or export/import round-trips.
* ``.upper()`` makes the key case-insensitive, since SKUs are conventionally
  treated as case-insensitive codes and Fulfil/Excel round-trips are not
  guaranteed to preserve case consistently.

``None``, and anything that normalizes to an empty string, is unusable as a
key and normalizes to ``None`` — callers must treat that as "skip/flag this
record", never as a valid (empty-string) SKU.
"""

from __future__ import annotations

from typing import Optional

__all__ = ["normalize_sku"]


def normalize_sku(raw: object) -> Optional[str]:
    """Return the canonical SKU key for ``raw``, or ``None`` if unusable.

    BD-009's inventory staging MUST call this same function on its own raw
    Fulfil records so both staged datasets key identically for BD-011's
    reconciliation join.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    return text.upper() if text else None
