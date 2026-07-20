"""Data contract for the ``DataSnapshot`` aggregate (Data Integration).

Owned by ``data-integrator``. ``DataSnapshot`` is the point-in-time, reconciled
pull of Fulfil sales + inventory that every downstream computation (velocity,
reorder points, slow-mover/overstock, reports) is derived from — the
Published Language between Data Integration and Merchandising Intelligence
(see ``docs/context-map.md``, event ``SnapshotAggregated``).

No customer PII, ever
----------------------
``DataSnapshot`` and its ``SnapshotRow`` line items are Product/SKU-level
only. There is intentionally NO field for a customer name, email, address,
phone number, government ID, or order-level identity anywhere on this
contract (see the no-pii rule and BD-011). Do not add one — aggregate at the
Product level before a fact reaches a snapshot row.

Versioning & additive evolution
--------------------------------
``DataSnapshot.SCHEMA_VERSION`` is the contract version for this aggregate.
``data-integrator`` may add new **optional** fields (with a default) to
``DataSnapshot`` or ``SnapshotRow`` in a later ticket without breaking
existing consumers (``merchandising-analyst``) — that is an additive,
non-breaking change and does not require a version bump. Only bump
``SCHEMA_VERSION`` for a breaking change: removing/renaming a field,
narrowing a type, or changing the meaning of an existing field. Consumers
should treat an absent optional field as its declared default rather than
assuming presence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import ClassVar


@dataclass(frozen=True)
class SnapshotRow:
    """One Product's sales + inventory facts for the snapshot period.

    Product/SKU-level only — see the module docstring's no-PII note. Do not
    add a customer-identifying field here.
    """

    sku: str
    product_name: str
    on_hand_units: int
    units_sold: int
    unit_cost: float | None = None
    supplier: str | None = None


@dataclass
class DataSnapshot:
    """The reconciled, point-in-time Fulfil pull. Aggregate root of Data Integration.

    Consumed by ``merchandising-analyst`` via the ``SnapshotAggregated`` event.
    """

    SCHEMA_VERSION: ClassVar[int] = 1

    snapshot_id: str
    period_start: date
    period_end: date
    captured_at: datetime
    rows: list[SnapshotRow] = field(default_factory=list)
    source_system: str = "fulfil"
    schema_version: int = SCHEMA_VERSION
