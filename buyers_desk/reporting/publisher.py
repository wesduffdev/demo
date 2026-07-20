"""SharePoint publisher for the ``Report`` aggregate (BD-007), via Microsoft Graph.

This is the boundary write-client through which a finished report file could
reach SharePoint (see ADR-0002 and ``docs/context-map.md``'s "Reporting &
Publishing -> SharePoint" Conformist relationship). It is deliberately split
into two phases that must never be collapsed into one:

Draft (stage) vs. send (publish) — the core of this ticket
------------------------------------------------------------
* :meth:`SharePointPublisher.stage_upload` resolves the target SharePoint
  location (site/drive + destination path + the exact Microsoft Graph upload
  URL that would be called) and returns a :class:`PendingUpload` preview.
  It performs **no network call** — it is pure, local computation (plus a
  local filesystem existence check on the report file) so a human can review
  the exact WHAT/WHERE before anything is sent (human-in-the-loop rule).
* :meth:`SharePointPublisher.publish` is the only method that ever issues the
  real Graph upload, and it does so **only** when called with
  ``approved=True``. With no approval (the default) it raises
  :class:`PublishNotApprovedError` and performs zero network calls — it is
  impossible to publish "by default", on import, or on construction.
* Wiring the three real reports (BD-017/018/019) through this client to
  actually publish is a later ticket (BD-020); this ticket delivers the
  boundary client only.

The module never sets ``Report.published_to``/``published_at`` on its own
initiative (see ``buyers_desk/contracts/report.py``'s draft-vs-published
note). :meth:`publish` will set them on an optionally-supplied ``Report``,
but only as the result of a completed, explicitly-approved publish — never
as a side effect of staging, construction, or any other code path.

Security & scope posture (see ``.claude/rules/security-secrets.md`` and
``.claude/rules/external-services.md``):

* Credentials are never read from ``os.environ`` directly here. This client
  is constructed from a :class:`~buyers_desk.config.SharePointConfig` —
  either injected directly (as tests do, with a fake config) or built via
  :meth:`SharePointPublisher.from_env`, which delegates to
  ``buyers_desk.config.load_sharepoint_config`` (the single source of truth
  for reading ``SHAREPOINT_*`` environment variables).
* ``client_secret`` is sent only in the token-exchange request body (Microsoft
  Graph's documented client-credentials flow). It is never logged, printed,
  included in an exception message, or exposed via ``__repr__``/``__str__``
  on this class, on :class:`PendingUpload`, or on :class:`PublishResult`.
* No network call happens at import time, in ``__init__``, in ``from_env``,
  or in ``stage_upload`` — the only methods that issue HTTP requests are the
  internal token fetch and the upload PUT, both reachable only through
  :meth:`publish`.
* Single-attempt, bounded-timeout calls only: no retry loop (unbounded or
  otherwise) around the write path, per the external-services rule's "no
  unbounded loops of paid/rate-limited calls" guidance. A caller-supplied
  ``requests.Session`` may still be configured with its own retry policy if
  a human operator wants one.
* :meth:`stage_upload` rejects any ``dest_folder`` containing a ``..`` path
  segment (raising :class:`SharePointInvalidDestinationError`) before the
  destination path or Graph ``upload_url`` is ever constructed — defense in
  depth against path traversal, enforced during the network-free staging
  step so a traversal attempt never even produces a :class:`PendingUpload`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Optional
from urllib.parse import quote

import requests

from buyers_desk.config import SharePointConfig, load_sharepoint_config
from buyers_desk.contracts import Report

#: Default per-request timeout (seconds): (connect, read). Uploads are larger
#: than a typical JSON call, so the read timeout is more generous than
#: ``data_integration.fulfil_client``'s, but still bounded.
DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)

#: Microsoft Graph v1.0 base URL (see ADR-0002: Graph is the SharePoint
#: integration surface).
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

#: Microsoft Entra ID (Azure AD) v2.0 token endpoint, per-tenant.
GRAPH_TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

#: The application-permission (client-credentials) scope for unattended Graph
#: calls — this client never does an interactive/delegated sign-in.
GRAPH_DEFAULT_SCOPE = "https://graph.microsoft.com/.default"

#: Content-Type for the Excel-compatible workbooks this client uploads.
XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class PublishNotApprovedError(RuntimeError):
    """Raised by :meth:`SharePointPublisher.publish` when ``approved`` is falsy.

    No network call is made before this is raised — refusing is the whole
    point (human-in-the-loop rule): publishing never happens "by default".
    """


class SharePointConnectionError(RuntimeError):
    """Raised when Microsoft Graph could not be reached (network/timeout).

    Wraps the underlying ``requests`` exception's type only — never includes
    request headers or body, so the client secret cannot leak via this path.
    """


class SharePointAuthError(RuntimeError):
    """Raised when the Graph token endpoint returns a non-2xx response.

    Carries the HTTP status code only. Never carries, logs, or embeds the
    client secret that was sent in the (unlogged) request body.
    """

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"Microsoft Graph token request failed with status {status_code}")


class SharePointPublishError(RuntimeError):
    """Raised when the Graph upload PUT returns a non-2xx response.

    Carries the HTTP status code and the (non-secret) destination path only.
    """

    def __init__(self, status_code: int, dest_path: str) -> None:
        self.status_code = status_code
        self.dest_path = dest_path
        super().__init__(f"SharePoint upload to {dest_path!r} failed with status {status_code}")


class SharePointInvalidDestinationError(ValueError):
    """Raised when ``dest_folder`` contains a ``..`` path-traversal segment.

    Defense-in-depth (security-secrets rule): ``dest_folder`` is embedded
    directly into the constructed destination path and Graph ``upload_url``,
    so a ``..`` segment is rejected during :meth:`SharePointPublisher.stage_upload`
    — before any path/URL is built and before any network call could occur.
    The message names the offending folder only; it carries no secret.
    """


@dataclass(frozen=True)
class PendingUpload:
    """A staged plan describing exactly WHAT would be uploaded and WHERE.

    Produced only by :meth:`SharePointPublisher.stage_upload`, which makes no
    network call. Every field here is safe to print/log/show to a human for
    approval — none of them is a secret (the client secret never appears on
    this object at all).
    """

    report_path: Path
    file_name: str
    dest_folder: str
    dest_path: str
    site_id: str
    drive_id: Optional[str]
    upload_url: str
    staged_at: datetime


@dataclass(frozen=True)
class PublishResult:
    """The outcome of a completed, approved publish."""

    web_url: str
    dest_path: str
    published_at: datetime
    graph_item_id: Optional[str] = None


def _drive_root_segment(site_id: str, drive_id: Optional[str]) -> str:
    """Graph path segment for the target drive's root.

    Mirrors Microsoft Graph's documented shape: a specific document library
    (``drives/{drive-id}``) if ``drive_id`` is configured, otherwise the
    site's default document library (``drive``).
    """
    if drive_id:
        return f"sites/{site_id}/drives/{drive_id}/root"
    return f"sites/{site_id}/drive/root"


def _build_dest_path(dest_folder: str, file_name: str) -> str:
    """Join a (possibly empty) destination folder and file name into one path."""
    normalized_folder = dest_folder.strip("/")
    if not normalized_folder:
        return file_name
    return f"{normalized_folder}/{file_name}"


def _reject_path_traversal(dest_folder: str) -> None:
    """Refuse a ``dest_folder`` containing a normalized ``..`` path segment.

    Defense-in-depth against path traversal into the Graph ``upload_url``:
    splits on both ``/`` and ``\\`` so a ``..`` segment can't sneak in via
    either separator, and rejects before any destination path or upload URL
    is constructed.
    """
    segments = dest_folder.replace("\\", "/").split("/")
    if any(segment.strip() == ".." for segment in segments):
        raise SharePointInvalidDestinationError(
            f"dest_folder must not contain '..' path segments: {dest_folder!r}"
        )


class SharePointPublisher:
    """Stages and (only on explicit approval) publishes a report to SharePoint.

    Dependency-injected: construct with an explicit :class:`SharePointConfig`
    (as tests do, with a fake config) or via :meth:`from_env` for the real
    environment-backed config. Never reads ``os.environ`` itself.

    See the module docstring for the draft-vs-send contract this class
    enforces: :meth:`stage_upload` never touches the network;
    :meth:`publish` does, and only when ``approved=True``.
    """

    #: Non-secret, redacted attribute names safe to include in ``__repr__``.
    _REPR_FIELDS: ClassVar[tuple[str, ...]] = ("tenant_id", "client_id", "site_id", "drive_id")

    def __init__(
        self,
        config: SharePointConfig,
        *,
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._config = config
        self._timeout = timeout
        # A caller-supplied session is accepted so tests can inject a mock
        # without patching module internals; no request is made here.
        self._session = session if session is not None else requests.Session()

    @classmethod
    def from_env(cls, **kwargs: Any) -> "SharePointPublisher":
        """Build a publisher from real environment-backed config.

        Delegates to ``buyers_desk.config.load_sharepoint_config`` (which
        reads ``SHAREPOINT_*`` env vars / a secrets manager) rather than
        touching ``os.environ`` itself. Raises ``MissingConfigError`` if
        required variables are unset. Makes no network call.
        """
        return cls(load_sharepoint_config(), **kwargs)

    @property
    def site_id(self) -> str:
        return self._config.site_id

    @property
    def drive_id(self) -> Optional[str]:
        return self._config.drive_id

    def __repr__(self) -> str:
        fields = ", ".join(f"{name}={getattr(self._config, name)!r}" for name in self._REPR_FIELDS)
        return f"SharePointPublisher({fields}, client_secret=<redacted>)"

    # -- stage: resolves the target + returns a preview, no network -----

    def stage_upload(self, report_path: str, *, dest_folder: str = "") -> PendingUpload:
        """Resolve the SharePoint target for ``report_path`` and return a preview.

        ``dest_folder`` is the drive-relative folder to publish into (e.g.
        ``"Reports/2026-07"``); leave blank to publish to the drive root.
        Performs **no network call** — only a local existence check on
        ``report_path`` and pure string/URL construction from ``config`` plus
        the arguments given. Raises ``FileNotFoundError`` if ``report_path``
        does not exist, since staging a nonexistent file would be a useless
        preview. Raises :class:`SharePointInvalidDestinationError` if
        ``dest_folder`` contains a ``..`` path segment — rejected before any
        destination path or upload URL is built, so a traversal attempt never
        produces a :class:`PendingUpload`.
        """
        _reject_path_traversal(dest_folder)

        path = Path(report_path)
        if not path.is_file():
            raise FileNotFoundError(f"Report file not found: {path}")

        file_name = path.name
        normalized_folder = dest_folder.strip("/")
        dest_path = _build_dest_path(normalized_folder, file_name)
        encoded_dest_path = quote(dest_path, safe="/")
        drive_segment = _drive_root_segment(self._config.site_id, self._config.drive_id)
        upload_url = f"{GRAPH_BASE_URL}/{drive_segment}:/{encoded_dest_path}:/content"

        return PendingUpload(
            report_path=path,
            file_name=file_name,
            dest_folder=normalized_folder,
            dest_path=dest_path,
            site_id=self._config.site_id,
            drive_id=self._config.drive_id,
            upload_url=upload_url,
            staged_at=datetime.now(timezone.utc),
        )

    # -- internal: token exchange (only ever reached via publish()) -----

    def _fetch_access_token(self) -> str:
        """Client-credentials token exchange. Never called except from ``publish``."""
        try:
            response = self._session.post(
                GRAPH_TOKEN_URL_TEMPLATE.format(tenant_id=self._config.tenant_id),
                data={
                    "client_id": self._config.client_id,
                    "client_secret": self._config.client_secret,
                    "scope": GRAPH_DEFAULT_SCOPE,
                    "grant_type": "client_credentials",
                },
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise SharePointConnectionError(
                f"Could not reach Microsoft Graph token endpoint: {exc.__class__.__name__}"
            ) from exc

        if response.status_code >= 300:
            raise SharePointAuthError(response.status_code)

        token = response.json().get("access_token")
        if not token:
            raise SharePointAuthError(response.status_code)
        return token

    # -- publish: the ONLY method that can send, and only if approved ---

    def publish(
        self,
        pending: PendingUpload,
        *,
        approved: bool = False,
        report: Optional[Report] = None,
    ) -> PublishResult:
        """Upload ``pending`` to SharePoint — but ONLY if ``approved=True``.

        With no approval (the default), raises :class:`PublishNotApprovedError`
        and makes zero network calls; nothing is sent and nothing is mutated.
        This is the human-gate: callers must pass an explicit, affirmative
        ``approved=True`` obtained from a human reviewing the ``pending``
        preview — this method never decides that on its own.

        When approved, performs exactly one token exchange and exactly one
        Graph upload PUT (no retry loop). If ``report`` is supplied and the
        upload succeeds, sets ``report.published_to``/``published_at`` to the
        resulting location/time — the only place in this module those fields
        are ever touched, and only as the outcome of this approved publish.
        """
        if not approved:
            raise PublishNotApprovedError(
                "Publish requires explicit human approval (approved=True); "
                "refusing to upload — nothing was sent."
            )

        token = self._fetch_access_token()
        content = pending.report_path.read_bytes()

        try:
            response = self._session.put(
                pending.upload_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": XLSX_CONTENT_TYPE,
                },
                data=content,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise SharePointConnectionError(
                f"Could not reach Microsoft Graph while uploading to {pending.dest_path!r}: "
                f"{exc.__class__.__name__}"
            ) from exc

        if response.status_code >= 300:
            raise SharePointPublishError(response.status_code, pending.dest_path)

        body = response.json() if response.content else {}
        published_at = datetime.now(timezone.utc)
        web_url = body.get("webUrl") or pending.dest_path

        if report is not None:
            report.published_to = web_url
            report.published_at = published_at

        return PublishResult(
            web_url=web_url,
            dest_path=pending.dest_path,
            published_at=published_at,
            graph_item_id=body.get("id"),
        )
