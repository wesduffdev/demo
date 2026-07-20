"""Tests for BD-005 Fulfil API client (``buyers_desk/data_integration/fulfil_client.py``).

No live network calls: ``requests`` is patched via ``unittest.mock``. All
fixture values are synthetic/fake (per the no-pii rule) — a fake subdomain
(``acme``) and a clearly-fake API key (``test-key-not-real``), never a real
credential.
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, Mock

import pytest
import requests

from buyers_desk.config import FulfilConfig
from buyers_desk.data_integration import (
    FulfilAPIError,
    FulfilClient,
    FulfilConnectionError,
)
from buyers_desk.data_integration.fulfil_client import HEALTH_PATH

FAKE_API_KEY = "test-key-not-real"


def _fake_config(**overrides: str) -> FulfilConfig:
    fields = {
        "api_key": FAKE_API_KEY,
        "subdomain": "acme",
        "base_url": "https://acme.fulfil.io",
    }
    fields.update(overrides)
    return FulfilConfig(**fields)


def _mock_session(response: Mock) -> MagicMock:
    session = MagicMock(spec=requests.Session)
    session.request.return_value = response
    return session


def _make_response(status_code: int, json_body: object = None) -> Mock:
    response = Mock(spec=requests.Response)
    response.status_code = status_code
    response.content = b"{}" if json_body is not None else b""
    response.json.return_value = json_body
    return response


# ---------------------------------------------------------------------------
# Construction: no network call, config-driven (not os.environ)
# ---------------------------------------------------------------------------


def test_client_makes_no_network_call_on_construction():
    session = MagicMock(spec=requests.Session)
    FulfilClient(_fake_config(), session=session)

    session.request.assert_not_called()


def test_client_exposes_subdomain_and_base_url_from_config():
    config = _fake_config(subdomain="acme", base_url="https://acme.fulfil.io")
    client = FulfilClient(config, session=MagicMock(spec=requests.Session))

    assert client.subdomain == "acme"
    assert client.base_url == "https://acme.fulfil.io"


def test_client_repr_never_contains_api_key():
    client = FulfilClient(_fake_config(), session=MagicMock(spec=requests.Session))

    rendered = repr(client)

    assert FAKE_API_KEY not in rendered
    assert "<redacted>" in rendered


# ---------------------------------------------------------------------------
# Auth header + base_url are respected on every request
# ---------------------------------------------------------------------------


def test_get_sends_x_api_key_header_from_config():
    response = _make_response(200, {"ok": True})
    session = _mock_session(response)
    client = FulfilClient(_fake_config(api_key=FAKE_API_KEY), session=session)

    client.get("/api/v2/model/sale.sale")

    _, kwargs = session.request.call_args
    assert kwargs["headers"]["X-API-KEY"] == FAKE_API_KEY


def test_get_builds_url_from_configured_base_url():
    response = _make_response(200, {"ok": True})
    session = _mock_session(response)
    client = FulfilClient(_fake_config(base_url="https://sandbox.fulfil.io"), session=session)

    client.get("/api/v2/model/sale.sale")

    args, kwargs = session.request.call_args
    url = args[1] if len(args) > 1 else kwargs.get("url")
    assert url.startswith("https://sandbox.fulfil.io/")


def test_get_uses_get_http_method_only():
    response = _make_response(200, {"ok": True})
    session = _mock_session(response)
    client = FulfilClient(_fake_config(), session=session)

    client.get("/api/v2/model/sale.sale")

    args, kwargs = session.request.call_args
    method = args[0] if args else kwargs.get("method")
    assert method == "GET"


def test_get_sets_a_bounded_timeout():
    response = _make_response(200, {"ok": True})
    session = _mock_session(response)
    client = FulfilClient(_fake_config(), session=session)

    client.get("/api/v2/model/sale.sale")

    _, kwargs = session.request.call_args
    assert kwargs["timeout"] is not None


def test_get_returns_parsed_json_body():
    response = _make_response(200, {"records": [1, 2, 3]})
    session = _mock_session(response)
    client = FulfilClient(_fake_config(), session=session)

    result = client.get("/api/v2/model/sale.sale")

    assert result == {"records": [1, 2, 3]}


# ---------------------------------------------------------------------------
# ping()/health(): success path on mocked 200
# ---------------------------------------------------------------------------


def test_ping_returns_true_on_mocked_200():
    response = _make_response(200, {})
    session = _mock_session(response)
    client = FulfilClient(_fake_config(), session=session)

    assert client.ping() is True
    session.request.assert_called_once()
    _, kwargs = session.request.call_args
    assert kwargs["headers"]["X-API-KEY"] == FAKE_API_KEY


def test_ping_hits_the_documented_health_path():
    response = _make_response(200, {})
    session = _mock_session(response)
    client = FulfilClient(_fake_config(base_url="https://acme.fulfil.io"), session=session)

    client.ping()

    args, kwargs = session.request.call_args
    url = args[1] if len(args) > 1 else kwargs.get("url")
    assert url == f"https://acme.fulfil.io{HEALTH_PATH}"


def test_health_is_an_alias_for_ping():
    response = _make_response(200, {})
    session = _mock_session(response)
    client = FulfilClient(_fake_config(), session=session)

    assert client.health() is True


# ---------------------------------------------------------------------------
# non-2xx -> FulfilAPIError, never leaking the key
# ---------------------------------------------------------------------------


def test_get_raises_fulfil_api_error_on_401():
    response = _make_response(401, None)
    session = _mock_session(response)
    client = FulfilClient(_fake_config(api_key=FAKE_API_KEY), session=session)

    with pytest.raises(FulfilAPIError) as exc_info:
        client.get("/api/v2/model/sale.sale")

    assert exc_info.value.status_code == 401
    assert FAKE_API_KEY not in str(exc_info.value)


def test_get_raises_fulfil_api_error_on_404_without_retry():
    response = _make_response(404, None)
    session = _mock_session(response)
    client = FulfilClient(_fake_config(), session=session)

    with pytest.raises(FulfilAPIError):
        client.get("/api/v2/model/sale.sale")

    # A 4xx is a bad request, not transient - must not be retried.
    session.request.assert_called_once()


def test_ping_raises_fulfil_api_error_on_500():
    response = _make_response(500, None)
    session = _mock_session(response)
    client = FulfilClient(_fake_config(), session=session, max_retries=0, backoff_seconds=0.0)

    with pytest.raises(FulfilAPIError) as exc_info:
        client.ping()

    assert exc_info.value.status_code == 500


def test_connection_error_raises_fulfil_connection_error_without_leaking_key():
    session = MagicMock(spec=requests.Session)
    session.request.side_effect = requests.ConnectionError("boom")
    client = FulfilClient(
        _fake_config(api_key=FAKE_API_KEY),
        session=session,
        max_retries=0,
        backoff_seconds=0.0,
    )

    with pytest.raises(FulfilConnectionError) as exc_info:
        client.get("/api/v2/model/sale.sale")

    assert FAKE_API_KEY not in str(exc_info.value)


def test_retries_transient_5xx_up_to_max_retries_then_succeeds():
    failure = _make_response(503, None)
    success = _make_response(200, {"ok": True})
    session = MagicMock(spec=requests.Session)
    session.request.side_effect = [failure, success]
    client = FulfilClient(_fake_config(), session=session, max_retries=1, backoff_seconds=0.0)

    result = client.get("/api/v2/model/sale.sale")

    assert result == {"ok": True}
    assert session.request.call_count == 2


def test_retries_are_bounded_and_eventually_raise():
    failure = _make_response(503, None)
    session = MagicMock(spec=requests.Session)
    session.request.return_value = failure
    client = FulfilClient(_fake_config(), session=session, max_retries=2, backoff_seconds=0.0)

    with pytest.raises(FulfilAPIError):
        client.get("/api/v2/model/sale.sale")

    # Initial attempt + 2 retries = 3 total calls, never unbounded.
    assert session.request.call_count == 3


# ---------------------------------------------------------------------------
# Read-only surface: no write/mutation method exists on the client
# ---------------------------------------------------------------------------


def test_client_exposes_no_write_or_mutation_method():
    forbidden_names = {"post", "put", "patch", "delete", "create", "update", "write"}
    public_members = {
        name for name, _ in inspect.getmembers(FulfilClient) if not name.startswith("_")
    }

    assert public_members.isdisjoint(forbidden_names)


def test_client_never_issues_a_non_get_http_method():
    """Every code path that calls session.request must pass method='GET'."""
    response = _make_response(200, {})
    session = _mock_session(response)
    client = FulfilClient(_fake_config(), session=session)

    client.get("/api/v2/model/sale.sale")
    client.ping()

    for call in session.request.call_args_list:
        args, kwargs = call
        method = args[0] if args else kwargs.get("method")
        assert method == "GET"


def test_internal_request_guard_rejects_non_get_method_without_calling_http():
    """Defense-in-depth: ``_request`` itself refuses a non-GET verb, even if
    called directly, so the read-only guarantee does not rely solely on
    convention (every current call site passing ``"GET"``)."""
    session = MagicMock(spec=requests.Session)
    client = FulfilClient(_fake_config(), session=session)

    with pytest.raises(ValueError, match="read-only"):
        client._request("POST", "/api/v2/model/sale.sale")

    session.request.assert_not_called()
