"""Merchandising Intelligence bounded context — owned by ``merchandising-analyst``.

The core subdomain. Computes per-SKU sales velocity and reorder points, and
produces reorder guidance plus slow-mover / overstock flags. All output is
advisory — the human Buyer commits every order (see the human-in-the-loop rule).

Aggregate roots: ``ReorderPlan`` and ``AssortmentReview``. Emits
``RecommendationsReady`` once guidance has been computed.

Scaffold only (BD-001). Velocity, reorder-point, and slow-mover/overstock logic
land in later wave tickets: BD-013, BD-014, BD-015.
"""

from __future__ import annotations
