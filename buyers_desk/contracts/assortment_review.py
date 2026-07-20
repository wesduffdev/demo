"""Data contract for the ``AssortmentReview`` aggregate (Merchandising Intelligence).

Owned by ``merchandising-analyst``. ``AssortmentReview`` carries SlowMover and
Overstock flags — Products that are candidates to pull or discount, each with
a stated reason — as the Published Language consumed by ``report-publisher``
after the ``RecommendationsReady`` event (see ``docs/context-map.md``).

Advisory only
-------------
Every ``AssortmentFlag`` is a candidate for a human decision, never an
automatic delist/discount action (see the human-in-the-loop rule).

Versioning & additive evolution
--------------------------------
``AssortmentReview.SCHEMA_VERSION`` is the contract version for this
aggregate. ``merchandising-analyst`` may add new **optional** fields (with a
default) to ``AssortmentReview`` or ``AssortmentFlag`` later without breaking
existing consumers (``report-publisher``) — additive changes do not require a
version bump. Bump ``SCHEMA_VERSION`` only for a breaking change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import ClassVar


class AssortmentFlagType(str, Enum):
    """Why a Product was flagged — mirrors the SlowMover / Overstock glossary terms."""

    SLOW_MOVER = "slow_mover"
    OVERSTOCK = "overstock"


@dataclass(frozen=True)
class AssortmentFlag:
    """One Product flagged as a SlowMover or Overstock pull/discount candidate."""

    sku: str
    product_name: str
    flag_type: AssortmentFlagType
    reason: str
    on_hand_units: int | None = None
    sales_velocity_per_week: float | None = None
    suggested_action: str | None = None


@dataclass
class AssortmentReview:
    """SlowMover/Overstock guidance for a cycle. Aggregate root of Merchandising Intelligence.

    Consumed by ``report-publisher`` via the ``RecommendationsReady`` event.
    """

    SCHEMA_VERSION: ClassVar[int] = 1

    review_id: str
    generated_at: datetime
    source_snapshot_id: str
    flags: list[AssortmentFlag] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION
