"""Config & credential loading for external services (BD-003).

Fulfil (the ERP system of record) and SharePoint (the publish target) are the
only two external services Buyer's Desk talks to (see ``docs/adr/0002``).
This module is the single place credentials for both are read from the
environment, validated, and turned into typed config objects for the rest of
the codebase — no other module should call ``os.environ`` for these values.

Security posture (see ``.claude/rules/security-secrets.md``):

* Credentials are read from ``os.environ`` only — never hardcoded, never read
  from a committed file. ``.env.example`` documents the variable names with
  fake placeholder values; a real ``.env`` (gitignored) or a secrets manager
  populating the process environment is how real values reach this module.
* A missing required variable fails fast via :class:`MissingConfigError`,
  which reports the variable NAMES only — never a value, and never a hint
  derived from a value.
* Every config dataclass is frozen and defines its own ``__repr__`` that
  redacts secret fields (``api_key``, ``client_secret``). Non-secret
  identifiers (subdomain, tenant/client/site ids, base URLs) are shown as-is
  since they are not credentials and are useful for diagnostics.
* :func:`config_presence` reports presence (set / not set) only, as booleans
  — it never returns or logs an actual value. Use it for healthchecks/diagnostics.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Environment variable names — the single source of truth for what this
# module reads. Keep in sync with ``.env.example``.
# ---------------------------------------------------------------------------

FULFIL_REQUIRED_VARS: Tuple[str, ...] = (
    "FULFIL_API_KEY",
    "FULFIL_SUBDOMAIN",
)
FULFIL_OPTIONAL_VARS: Tuple[str, ...] = (
    # Overrides the subdomain-derived URL; useful for a sandbox/test endpoint
    # (see .claude/rules/external-services.md).
    "FULFIL_BASE_URL",
)

SHAREPOINT_REQUIRED_VARS: Tuple[str, ...] = (
    "SHAREPOINT_TENANT_ID",
    "SHAREPOINT_CLIENT_ID",
    "SHAREPOINT_CLIENT_SECRET",
    "SHAREPOINT_SITE_ID",
)
SHAREPOINT_OPTIONAL_VARS: Tuple[str, ...] = (
    # The document library to publish into, if the site has more than one.
    "SHAREPOINT_DRIVE_ID",
)

_FULFIL_SERVICE = "Fulfil"
_SHAREPOINT_SERVICE = "SharePoint"


class MissingConfigError(RuntimeError):
    """Raised when one or more required environment variables are unset.

    Reports the MISSING VARIABLE NAMES (and which service each belongs to)
    only. Never carries, logs, or embeds a secret value — a variable that is
    missing has no value to leak, and this exception never inspects the
    values of variables that ARE set.
    """

    def __init__(self, missing: Sequence[Tuple[str, str]]) -> None:
        self.missing: Tuple[Tuple[str, str], ...] = tuple(missing)
        described = ", ".join(f"{name} ({service})" for name, service in self.missing)
        super().__init__(
            "Missing required configuration: "
            f"{described}. Set these environment variables (see .env.example) "
            "before continuing — values are never logged."
        )


def _missing_vars(
    env: Mapping[str, str], names: Sequence[str], service: str
) -> list[Tuple[str, str]]:
    """Return ``(name, service)`` for each name in ``names`` unset/blank in ``env``.

    Presence check only: this function never reads or returns a value, only
    whether one is present and non-blank.
    """
    missing: list[Tuple[str, str]] = []
    for name in names:
        raw = env.get(name)
        if raw is None or raw.strip() == "":
            missing.append((name, service))
    return missing


@dataclass(frozen=True)
class FulfilConfig:
    """Credentials + endpoint for Fulfil's REST API (read-only by default).

    ``api_key`` is a secret; ``__repr__`` redacts it. ``subdomain`` and
    ``base_url`` are not credentials and are shown as-is for diagnostics.
    """

    api_key: str
    subdomain: str
    base_url: str

    def __repr__(self) -> str:  # pragma: no cover - trivial, exercised by tests
        return (
            f"FulfilConfig(subdomain={self.subdomain!r}, base_url={self.base_url!r}, "
            "api_key=<redacted>)"
        )


@dataclass(frozen=True)
class SharePointConfig:
    """Credentials + target site for publishing via Microsoft Graph.

    ``client_secret`` is a secret; ``__repr__`` redacts it. The tenant/client
    ids and site/drive ids are not secrets and are shown as-is.
    """

    tenant_id: str
    client_id: str
    client_secret: str
    site_id: str
    drive_id: Optional[str] = None

    def __repr__(self) -> str:  # pragma: no cover - trivial, exercised by tests
        return (
            f"SharePointConfig(tenant_id={self.tenant_id!r}, client_id={self.client_id!r}, "
            f"site_id={self.site_id!r}, drive_id={self.drive_id!r}, "
            "client_secret=<redacted>)"
        )


@dataclass(frozen=True)
class AppConfig:
    """Top-level config: every external service Buyer's Desk talks to."""

    fulfil: FulfilConfig
    sharepoint: SharePointConfig


def load_fulfil_config(env: Optional[Mapping[str, str]] = None) -> FulfilConfig:
    """Load & validate Fulfil config from ``env`` (default: ``os.environ``).

    Raises :class:`MissingConfigError` naming any missing required variable.
    """
    source: Mapping[str, str] = env if env is not None else os.environ
    missing = _missing_vars(source, FULFIL_REQUIRED_VARS, _FULFIL_SERVICE)
    if missing:
        raise MissingConfigError(missing)

    subdomain = source["FULFIL_SUBDOMAIN"]
    base_url = source.get("FULFIL_BASE_URL") or f"https://{subdomain}.fulfil.io"
    return FulfilConfig(
        api_key=source["FULFIL_API_KEY"],
        subdomain=subdomain,
        base_url=base_url,
    )


def load_sharepoint_config(env: Optional[Mapping[str, str]] = None) -> SharePointConfig:
    """Load & validate SharePoint config from ``env`` (default: ``os.environ``).

    Raises :class:`MissingConfigError` naming any missing required variable.
    """
    source: Mapping[str, str] = env if env is not None else os.environ
    missing = _missing_vars(source, SHAREPOINT_REQUIRED_VARS, _SHAREPOINT_SERVICE)
    if missing:
        raise MissingConfigError(missing)

    drive_id = source.get("SHAREPOINT_DRIVE_ID") or None
    return SharePointConfig(
        tenant_id=source["SHAREPOINT_TENANT_ID"],
        client_id=source["SHAREPOINT_CLIENT_ID"],
        client_secret=source["SHAREPOINT_CLIENT_SECRET"],
        site_id=source["SHAREPOINT_SITE_ID"],
        drive_id=drive_id,
    )


def load_config(env: Optional[Mapping[str, str]] = None) -> AppConfig:
    """Load & validate the full ``AppConfig`` (Fulfil + SharePoint).

    Validates both services before raising, so a single
    :class:`MissingConfigError` names every missing variable across both
    services in one pass rather than forcing a fix-one-run-again loop.
    """
    source: Mapping[str, str] = env if env is not None else os.environ
    missing = _missing_vars(source, FULFIL_REQUIRED_VARS, _FULFIL_SERVICE) + _missing_vars(
        source, SHAREPOINT_REQUIRED_VARS, _SHAREPOINT_SERVICE
    )
    if missing:
        raise MissingConfigError(missing)

    return AppConfig(
        fulfil=load_fulfil_config(source),
        sharepoint=load_sharepoint_config(source),
    )


def config_presence(env: Optional[Mapping[str, str]] = None) -> Dict[str, bool]:
    """Report which known config vars are SET (non-empty) — presence only.

    Never returns, logs, or otherwise exposes an actual value; safe to print
    or include in a healthcheck response.
    """
    source: Mapping[str, str] = env if env is not None else os.environ
    all_names = (
        *FULFIL_REQUIRED_VARS,
        *FULFIL_OPTIONAL_VARS,
        *SHAREPOINT_REQUIRED_VARS,
        *SHAREPOINT_OPTIONAL_VARS,
    )
    return {name: bool(source.get(name, "").strip()) for name in all_names}
