"""Data Integration bounded context — owned by ``data-integrator``.

Turns raw Fulfil sales + inventory into a clean, reconciled, product-level
``DataSnapshot`` (file-based CSV/Parquet — no database in v1, see ADR-0002),
and provides the anti-corruption layer that keeps Fulfil's model out of our
Ubiquitous Language (``docs/GLOSSARY.md``).

Aggregate root: ``DataSnapshot``. Emits ``SnapshotAggregated`` when a fresh,
clean snapshot is ready. No customer PII is carried past this boundary — the
snapshot is aggregated at the Product level (see the no-pii rule).

Scaffold only (BD-001). The Fulfil client landed in BD-005; data pulls and
aggregation land in later wave tickets: BD-008, BD-009, BD-011.
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

__all__ = [
    "FulfilClient",
    "FulfilAPIError",
    "FulfilConnectionError",
    "HEALTH_PATH",
    "DEFAULT_TIMEOUT",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_BACKOFF_SECONDS",
]
