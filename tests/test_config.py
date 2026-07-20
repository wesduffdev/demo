"""Tests for BD-003 config & credential loading (``buyers_desk/config.py``).

Uses only synthetic, clearly-fake fixture values (per the no-pii rule) and
``monkeypatch.setenv``/``delenv`` so no real process environment leaks into a
test and no test leaks into the real process environment.
"""

from __future__ import annotations

import pytest

from buyers_desk.config import (
    FULFIL_REQUIRED_VARS,
    SHAREPOINT_REQUIRED_VARS,
    AppConfig,
    FulfilConfig,
    MissingConfigError,
    SharePointConfig,
    config_presence,
    load_config,
    load_fulfil_config,
    load_sharepoint_config,
)

FAKE_FULFIL_API_KEY = "fake-fulfil-api-key-000111222"
FAKE_SHAREPOINT_CLIENT_SECRET = "fake-sharepoint-client-secret-333444555"


def _set_all_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FULFIL_API_KEY", FAKE_FULFIL_API_KEY)
    monkeypatch.setenv("FULFIL_SUBDOMAIN", "fake-acme")
    monkeypatch.setenv("SHAREPOINT_TENANT_ID", "fake-tenant-id")
    monkeypatch.setenv("SHAREPOINT_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("SHAREPOINT_CLIENT_SECRET", FAKE_SHAREPOINT_CLIENT_SECRET)
    monkeypatch.setenv("SHAREPOINT_SITE_ID", "fake-site-id")


def _clear_all_known(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        *FULFIL_REQUIRED_VARS,
        "FULFIL_BASE_URL",
        *SHAREPOINT_REQUIRED_VARS,
        "SHAREPOINT_DRIVE_ID",
    ):
        monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------------------
# (a) all present -> loads
# ---------------------------------------------------------------------------


def test_load_config_with_all_vars_present_returns_app_config(monkeypatch):
    _clear_all_known(monkeypatch)
    _set_all_required(monkeypatch)

    config = load_config()

    assert isinstance(config, AppConfig)
    assert isinstance(config.fulfil, FulfilConfig)
    assert isinstance(config.sharepoint, SharePointConfig)
    assert config.fulfil.api_key == FAKE_FULFIL_API_KEY
    assert config.fulfil.subdomain == "fake-acme"
    assert config.fulfil.base_url == "https://fake-acme.fulfil.io"
    assert config.sharepoint.client_secret == FAKE_SHAREPOINT_CLIENT_SECRET
    assert config.sharepoint.site_id == "fake-site-id"
    assert config.sharepoint.drive_id is None


def test_load_fulfil_config_honors_base_url_override(monkeypatch):
    _clear_all_known(monkeypatch)
    _set_all_required(monkeypatch)
    monkeypatch.setenv("FULFIL_BASE_URL", "https://fake-sandbox.fulfil.io")

    fulfil = load_fulfil_config()

    assert fulfil.base_url == "https://fake-sandbox.fulfil.io"


def test_load_sharepoint_config_picks_up_optional_drive_id(monkeypatch):
    _clear_all_known(monkeypatch)
    _set_all_required(monkeypatch)
    monkeypatch.setenv("SHAREPOINT_DRIVE_ID", "fake-drive-id")

    sharepoint = load_sharepoint_config()

    assert sharepoint.drive_id == "fake-drive-id"


def test_load_config_reads_from_explicit_mapping_not_os_environ(monkeypatch):
    """Passing an explicit ``env`` mapping must not touch the real process env."""
    _clear_all_known(monkeypatch)  # ensure os.environ has none of these set

    explicit_env = {
        "FULFIL_API_KEY": FAKE_FULFIL_API_KEY,
        "FULFIL_SUBDOMAIN": "fake-acme",
        "SHAREPOINT_TENANT_ID": "fake-tenant-id",
        "SHAREPOINT_CLIENT_ID": "fake-client-id",
        "SHAREPOINT_CLIENT_SECRET": FAKE_SHAREPOINT_CLIENT_SECRET,
        "SHAREPOINT_SITE_ID": "fake-site-id",
    }

    config = load_config(explicit_env)

    assert config.fulfil.api_key == FAKE_FULFIL_API_KEY


# ---------------------------------------------------------------------------
# (b) missing required var -> raises, naming the missing var
# ---------------------------------------------------------------------------


def test_missing_fulfil_var_raises_missing_config_error_naming_it(monkeypatch):
    _clear_all_known(monkeypatch)
    _set_all_required(monkeypatch)
    monkeypatch.delenv("FULFIL_API_KEY", raising=False)

    with pytest.raises(MissingConfigError) as exc_info:
        load_fulfil_config()

    assert "FULFIL_API_KEY" in str(exc_info.value)
    assert ("FULFIL_API_KEY", "Fulfil") in exc_info.value.missing


def test_missing_sharepoint_var_raises_missing_config_error_naming_it(monkeypatch):
    _clear_all_known(monkeypatch)
    _set_all_required(monkeypatch)
    monkeypatch.delenv("SHAREPOINT_CLIENT_SECRET", raising=False)

    with pytest.raises(MissingConfigError) as exc_info:
        load_sharepoint_config()

    assert "SHAREPOINT_CLIENT_SECRET" in str(exc_info.value)


def test_blank_string_var_counts_as_missing(monkeypatch):
    """A var set to whitespace/empty must fail presence, not silently pass through."""
    _clear_all_known(monkeypatch)
    _set_all_required(monkeypatch)
    monkeypatch.setenv("FULFIL_SUBDOMAIN", "   ")

    with pytest.raises(MissingConfigError) as exc_info:
        load_fulfil_config()

    assert "FULFIL_SUBDOMAIN" in str(exc_info.value)


def test_load_config_reports_missing_vars_from_both_services_in_one_error(monkeypatch):
    _clear_all_known(monkeypatch)
    _set_all_required(monkeypatch)
    monkeypatch.delenv("FULFIL_SUBDOMAIN", raising=False)
    monkeypatch.delenv("SHAREPOINT_SITE_ID", raising=False)

    with pytest.raises(MissingConfigError) as exc_info:
        load_config()

    message = str(exc_info.value)
    assert "FULFIL_SUBDOMAIN" in message
    assert "SHAREPOINT_SITE_ID" in message


def test_missing_config_error_message_is_actionable(monkeypatch):
    _clear_all_known(monkeypatch)
    _set_all_required(monkeypatch)
    monkeypatch.delenv("FULFIL_API_KEY", raising=False)

    with pytest.raises(MissingConfigError) as exc_info:
        load_fulfil_config()

    message = str(exc_info.value)
    assert ".env.example" in message


# ---------------------------------------------------------------------------
# (c) secret values never leak into error messages or repr()
# ---------------------------------------------------------------------------


def test_missing_var_error_never_contains_a_set_secret_value(monkeypatch):
    """Unset FULFIL_SUBDOMAIN while a real-shaped secret IS set elsewhere;
    the raised error must name the missing var only, never echo the secret
    that happens to be present in the environment."""
    _clear_all_known(monkeypatch)
    _set_all_required(monkeypatch)
    monkeypatch.delenv("FULFIL_SUBDOMAIN", raising=False)

    with pytest.raises(MissingConfigError) as exc_info:
        load_fulfil_config()

    message = str(exc_info.value)
    assert FAKE_FULFIL_API_KEY not in message
    assert FAKE_SHAREPOINT_CLIENT_SECRET not in message


def test_fulfil_config_repr_never_contains_api_key(monkeypatch):
    _clear_all_known(monkeypatch)
    _set_all_required(monkeypatch)

    fulfil = load_fulfil_config()

    assert FAKE_FULFIL_API_KEY not in repr(fulfil)
    assert FAKE_FULFIL_API_KEY not in str(fulfil)
    assert "<redacted>" in repr(fulfil)


def test_sharepoint_config_repr_never_contains_client_secret(monkeypatch):
    _clear_all_known(monkeypatch)
    _set_all_required(monkeypatch)

    sharepoint = load_sharepoint_config()

    assert FAKE_SHAREPOINT_CLIENT_SECRET not in repr(sharepoint)
    assert FAKE_SHAREPOINT_CLIENT_SECRET not in str(sharepoint)
    assert "<redacted>" in repr(sharepoint)


def test_app_config_repr_never_contains_any_secret(monkeypatch):
    """The nested AppConfig repr must also never leak either secret."""
    _clear_all_known(monkeypatch)
    _set_all_required(monkeypatch)

    config = load_config()
    rendered = repr(config)

    assert FAKE_FULFIL_API_KEY not in rendered
    assert FAKE_SHAREPOINT_CLIENT_SECRET not in rendered


# ---------------------------------------------------------------------------
# config_presence(): booleans only, never values
# ---------------------------------------------------------------------------


def test_config_presence_reports_booleans_only(monkeypatch):
    _clear_all_known(monkeypatch)
    _set_all_required(monkeypatch)

    presence = config_presence()

    assert presence["FULFIL_API_KEY"] is True
    assert presence["FULFIL_SUBDOMAIN"] is True
    assert presence["FULFIL_BASE_URL"] is False
    assert presence["SHAREPOINT_DRIVE_ID"] is False
    # No value ever appears in the presence report — only True/False.
    assert FAKE_FULFIL_API_KEY not in repr(presence)
    assert FAKE_SHAREPOINT_CLIENT_SECRET not in repr(presence)


def test_config_presence_reports_false_for_unset_required_vars(monkeypatch):
    _clear_all_known(monkeypatch)

    presence = config_presence()

    for name in FULFIL_REQUIRED_VARS:
        assert presence[name] is False
    for name in SHAREPOINT_REQUIRED_VARS:
        assert presence[name] is False
