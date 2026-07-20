"""Packaging/import smoke test for the BD-001 scaffold.

Guards that ``buyers_desk`` and its three bounded-context sub-packages
(``data_integration``, ``merchandising``, ``reporting``) import cleanly via
the editable install, and that ``buyers_desk.__version__`` is set. No
business logic lives here yet (BD-001 is scaffold-only) — this just protects
the package layout itself from silently breaking.
"""

from __future__ import annotations

import importlib

import pytest

SUB_PACKAGES = [
    "buyers_desk",
    "buyers_desk.data_integration",
    "buyers_desk.merchandising",
    "buyers_desk.reporting",
]


@pytest.mark.parametrize("module_name", SUB_PACKAGES)
def test_package_imports_without_error(module_name):
    module = importlib.import_module(module_name)
    assert module is not None


def test_version_is_a_non_empty_str():
    import buyers_desk

    assert isinstance(buyers_desk.__version__, str)
    assert buyers_desk.__version__ != ""
