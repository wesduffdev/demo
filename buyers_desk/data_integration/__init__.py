"""Data Integration bounded context — owned by ``data-integrator``.

Turns raw Fulfil sales + inventory into a clean, reconciled, product-level
``DataSnapshot`` (file-based CSV/Parquet — no database in v1, see ADR-0002),
and provides the anti-corruption layer that keeps Fulfil's model out of our
Ubiquitous Language (``docs/GLOSSARY.md``).

Aggregate root: ``DataSnapshot``. Emits ``SnapshotAggregated`` when a fresh,
clean snapshot is ready. No customer PII is carried past this boundary — the
snapshot is aggregated at the Product level (see the no-pii rule).

Scaffold only (BD-001). The Fulfil client landed in BD-005; the raw sales
staging pull landed in BD-008. The raw inventory staging pull (BD-009) and
the reconciled ``DataSnapshot`` build (BD-011) land in later wave tickets.
"""

from __future__ import annotations

from buyers_desk.data_integration.fulfil_client import (
    DEFAULT_BACKOFF_SECONDS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    HEALTH_PATH,
    FulfilAPIError,
    FulfilClient,
    FulfilConnectionError,
)
from buyers_desk.data_integration.sales_staging import (
    DEFAULT_MAX_PAGES,
    DEFAULT_PAGE_SIZE,
    SALES_PATH,
    SalesRow,
    SalesStagingBatch,
    from_fulfil_record,
    pull_sales_rows,
)
from buyers_desk.data_integration.sku import normalize_sku

__all__ = [
    "FulfilClient",
    "FulfilAPIError",
    "FulfilConnectionError",
    "HEALTH_PATH",
    "DEFAULT_TIMEOUT",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_BACKOFF_SECONDS",
    "SalesRow",
    "SalesStagingBatch",
    "from_fulfil_record",
    "pull_sales_rows",
    "SALES_PATH",
    "DEFAULT_PAGE_SIZE",
    "DEFAULT_MAX_PAGES",
    "normalize_sku",
]
