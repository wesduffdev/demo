"""Observability tooling for the Buyer's Desk orchestrator (BD-000).

Exposes :class:`RunLogger`, the run-logging harness the Product Owner
(orchestrator) uses to record its actions, the agent hand-off sequence, and
per-agent token/time telemetry to a checked-in ``logs/`` folder.
"""

from .run_logger import RunLogger

__all__ = ["RunLogger"]
