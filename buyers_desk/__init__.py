"""Buyer's Desk — v1 package root.

An internal decision-support system that aggregates Fulfil sales & inventory
into reorder/assortment guidance and Excel reports published to SharePoint.
The system *recommends*; the human Buyer commits every order.

The package layout mirrors the bounded contexts in ``docs/context-map.md``;
each sub-package is owned by exactly one specialist agent (``.claude/agents/``):

* ``buyers_desk.data_integration`` — Data Integration (``data-integrator``);
  owns the ``DataSnapshot`` aggregate.
* ``buyers_desk.merchandising``    — Merchandising Intelligence
  (``merchandising-analyst``); owns ``ReorderPlan`` and ``AssortmentReview``.
* ``buyers_desk.reporting``        — Reporting & Publishing
  (``report-publisher``); owns the ``Report`` aggregate.

Cross-cutting orchestrator run-logging lives in the top-level ``observability``
package (see BD-000). This module is an intentionally empty scaffold (BD-001);
behaviour lands in later wave tickets.
"""

from __future__ import annotations

__version__ = "0.1.0"
