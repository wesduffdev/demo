"""Read-only Fulfil REST API client (BD-005).

This is the boundary module ("anti-corruption layer" entry point) through
which Buyer's Desk talks to Fulfil, the ERP system of record for sales &
inventory (see ``docs/GLOSSARY.md``). Later tickets (BD-008 sales pull,
BD-009 inventory pull) build the actual data-shaping logic on top of the
:meth:`FulfilClient.get` helper this module exposes; this ticket only
delivers authenticated, read-only connectivity + a health check.

Security & scope posture (see ``.claude/rules/security-secrets.md`` and
``.claude/rules/external-services.md``):

* Credentials are never read from ``os.environ`` directly here. The client
  is constructed from a :class:`~buyers_desk.config.FulfilConfig` — either
  injected directly (e.g. by tests, with a fake config) or built via
  :meth:`FulfilClient.from_env`, which delegates to
  ``buyers_desk.config.load_fulfil_config`` (the single source of truth for
  reading ``FULFIL_*`` environment variables).
* ``FulfilConfig.base_url`` already honors the ``FULFIL_BASE_URL`` sandbox
  override (see ``buyers_desk/config.py``); this client makes no production
  vs. sandbox decision of its own and issues no network call at import time,
  in ``__init__``, or anywhere outside an explicit method call.
* Read-only ONLY. This module defines no POST/PUT/PATCH/DELETE method, and
  :meth:`FulfilClient.get` is a thin wrapper around ``requests.get`` — there
  is no generic "request" method that could be pointed at a mutating verb.
* The API key is sent only in the ``X-API-KEY`` request header (Fulfil's
  documented auth scheme). It is never logged, printed, included in an
  exception message, or exposed via ``__repr__``/``__str__``.
* Bounded retries with backoff and a fixed request timeout guard against
  unbounded loops of paid/rate-limited calls (see external-services rule).
"""

from __future__ import annotations

import time
from typing import Any, ClassVar, Mapping, Optional

import requests

from buyers_desk.config import FulfilConfig, load_fulfil_config

#: Default per-request timeout (seconds): (connect, read). Keeps a hung
#: Fulfil endpoint from blocking a run indefinitely.
DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 30.0)

#: Small, bounded retry budget for transient failures only (connection
#: errors, timeouts, and 5xx responses). Never retries on a 4xx (client/auth
#: error) since a retry cannot fix a bad request or bad credentials.
DEFAULT_MAX_RETRIES = 2
DEFAULT_BACKOFF_SECONDS = 0.5

#: Fulfil's read-only health/ping endpoint used by :meth:`FulfilClient.ping`.
#: A lightweight, side-effect-free GET suitable for verifying auth + connectivity.
HEALTH_PATH = "/api/v2/model/ir.model"


class FulfilAPIError(RuntimeError):
    """Raised when Fulfil returns a non-2xx response.

    Carries the HTTP status code and response path for diagnostics. Never
    carries, logs, or embeds the API key — only the status code and the
    (non-secret) request path are included in the message.
    """

    def __init__(self, status_code: int, path: str, message: str = "") -> None:
        self.status_code = status_code
        self.path = path
        detail = f": {message}" if message else ""
        super().__init__(f"Fulfil API request to {path!r} failed with status {status_code}{detail}")


class FulfilConnectionError(RuntimeError):
    """Raised when a request to Fulfil could not be completed (network/timeout).

    Wraps the underlying ``requests`` exception's type/message only — never
    includes request headers, so the API key cannot leak via this path.
    """


class FulfilClient:
    """Minimal, read-only, authenticated client for Fulfil's REST API.

    Dependency-injected: construct with an explicit :class:`FulfilConfig` (as
    tests do, with a fake config) or via :meth:`from_env` for the real
    environment-backed config. Never reads ``os.environ`` itself.

    Read-only by design: the only HTTP verb this class issues is GET, via
    :meth:`get` (a generic authenticated GET helper) and :meth:`ping`
    (a convenience health check built on it). There is intentionally no
    ``post``/``put``/``patch``/``delete`` method.
    """

    #: Non-secret, redacted attribute names safe to include in ``__repr__``.
    _REPR_FIELDS: ClassVar[tuple[str, ...]] = ("subdomain", "base_url")

    def __init__(
        self,
        config: FulfilConfig,
        *,
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._config = config
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        # A caller-supplied session is accepted so tests can inject a mock
        # without patching module internals; no request is made here.
        self._session = session if session is not None else requests.Session()

    @classmethod
    def from_env(cls, **kwargs: Any) -> "FulfilClient":
        """Build a client from real environment-backed config.

        Delegates to ``buyers_desk.config.load_fulfil_config`` (which reads
        ``FULFIL_*`` env vars / a secrets manager) rather than touching
        ``os.environ`` itself. Raises ``MissingConfigError`` if required
        variables are unset. Makes no network call.
        """
        return cls(load_fulfil_config(), **kwargs)

    @property
    def subdomain(self) -> str:
        return self._config.subdomain

    @property
    def base_url(self) -> str:
        return self._config.base_url

    def __repr__(self) -> str:
        fields = ", ".join(f"{name}={getattr(self._config, name)!r}" for name in self._REPR_FIELDS)
        return f"FulfilClient({fields}, api_key=<redacted>)"

    # -- internal helpers ----------------------------------------------

    def _headers(self) -> dict[str, str]:
        # The API key is set here, on each request, and nowhere else —
        # never assigned to an attribute that a repr/log could later expose.
        return {"X-API-KEY": self._config.api_key, "Accept": "application/json"}

    def _url(self, path: str) -> str:
        return f"{self._config.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _request(
        self, method: str, path: str, *, params: Optional[Mapping[str, Any]] = None
    ) -> requests.Response:
        """Issue one HTTP request with a bounded retry budget.

        Only ever called internally with ``method="GET"`` — see the class
        docstring's read-only guarantee. That guarantee is enforced here at
        runtime (not just by convention/code review): a non-``"GET"`` method
        raises :class:`ValueError` before any request is issued, so a future
        internal caller cannot silently turn this client into a write path.
        Retries transient failures (connection errors, timeouts, 5xx) up to
        ``max_retries`` times with a linear backoff; never retries a 4xx,
        since that indicates a bad request or bad credentials that a retry
        cannot fix.
        """
        if method != "GET":
            raise ValueError("FulfilClient is read-only; only GET is permitted")

        url = self._url(path)
        attempt = 0
        while True:
            try:
                response = self._session.request(
                    method,
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=self._timeout,
                )
            except requests.RequestException as exc:
                if attempt >= self._max_retries:
                    raise FulfilConnectionError(
                        f"Could not reach Fulfil at {path!r}: {exc.__class__.__name__}"
                    ) from exc
                attempt += 1
                time.sleep(self._backoff_seconds * attempt)
                continue

            if 200 <= response.status_code < 300:
                return response
            if response.status_code >= 500 and attempt < self._max_retries:
                attempt += 1
                time.sleep(self._backoff_seconds * attempt)
                continue

            raise FulfilAPIError(response.status_code, path)

    # -- public, read-only API ------------------------------------------

    def get(self, path: str, *, params: Optional[Mapping[str, Any]] = None) -> Any:
        """Authenticated read-only GET against ``path``. Returns parsed JSON.

        ``path`` may be relative (e.g. ``"/api/v2/model/sale.sale"``) and is
        joined onto ``config.base_url``. Raises :class:`FulfilAPIError` on a
        non-2xx response and :class:`FulfilConnectionError` if Fulfil could
        not be reached at all. This is the only request-issuing method on
        this class besides :meth:`ping`, which calls it.
        """
        response = self._request("GET", path, params=params)
        if not response.content:
            return None
        return response.json()

    def ping(self) -> bool:
        """Read-only health check: confirm auth + connectivity to Fulfil.

        Returns ``True`` on any 2xx response from ``HEALTH_PATH``. Raises
        :class:`FulfilAPIError` on a non-2xx response (e.g. a bad/expired
        API key) and :class:`FulfilConnectionError` if unreachable.
        """
        self.get(HEALTH_PATH)
        return True

    def health(self) -> bool:
        """Alias for :meth:`ping`, kept for naming-convention flexibility."""
        return self.ping()
