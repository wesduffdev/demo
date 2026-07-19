"""Pytest configuration: make the repo root importable.

The project has no package/build scaffolding yet (see ADR-0002 / BD-001), so
``observability`` is only importable if the repo root is on ``sys.path``. This
conftest inserts it once, before any test module in this directory imports
``observability.run_logger``.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
