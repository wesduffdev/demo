"""Data contract for the ``ReorderPlan`` aggregate (Merchandising Intelligence).

Owned by ``merchandising-analyst``. ``ReorderPlan`` carries reorder guidance —
which Product, how many units (driven by ``SalesVelocity`` + ``ReorderPoint``),
from which Supplier, and roughly when — as the Published Language consumed by
``report-publisher`` after the ``RecommendationsReady`` event (see
``docs/context-map.md``).

Advisory only
-------------
Every ``ReorderLine`` is a recommendation, never a placed order or committed
spend — the human Buyer commits every order (see the human-in-the-loop rule).
This contract intentionally has no field for order status, approval, or
spend commitment; that is out of scope here.

Versioning & additive evolution
--------------------------------
``ReorderPlan.SCHEMA_VERSION`` is the contract version for this aggregate.
``merchandising-analyst`` may add new **optional** fields (with a default) to
``ReorderPlan`` or ``ReorderLine`` later without breaking existing consumers
(``report-publisher``) — additive changes do not require a version bump.
Bump ``SCHEMA_VERSION`` only for a breaking change (removed/renamed field,
narrowed type, changed meaning).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import ClassVar


@dataclass(frozen=True)
class ReorderLine:
    """One Product's reorder suggestion — advisory, never auto-placed."""

    sku: str
    product_name: str
    suggested_order_qty: int
    reorder_point: int
    supplier: str | None = None
    needed_by: date | None = None
    sales_velocity_per_week: float | None = None
    rationale: str | None = None


@dataclass
class ReorderPlan:
    """Reorder guidance for a cycle. Aggregate root of Merchandising Intelligence.

    Consumed by ``report-publisher`` via the ``RecommendationsReady`` event.
    """

    SCHEMA_VERSION: ClassVar[int] = 1

    plan_id: str
    generated_at: datetime
    source_snapshot_id: str
    lines: list[ReorderLine] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION
