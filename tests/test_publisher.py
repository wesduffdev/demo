"""Tests for BD-007 SharePoint publisher (``buyers_desk/reporting/publisher.py``).

No live network calls: ``requests`` is patched via ``unittest.mock``. All
fixture values are synthetic/fake (per the no-pii rule) — fake tenant/site/
drive GUIDs and a clearly-fake client secret (``test-secret-not-real``),
never a real credential.

Covers the draft-vs-send contract at the heart of this ticket:
``stage_upload`` resolves the target Graph upload URL with zero network
calls; ``publish`` refuses (and sends nothing) without explicit approval,
and performs exactly one upload PUT when approval is given; and the client
secret never surfaces in ``repr``/exception output.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
import requests

from buyers_desk.config import SharePointConfig
from buyers_desk.contracts import Report, ReportKind
from buyers_desk.reporting import (
    GRAPH_BASE_URL,
    XLSX_CONTENT_TYPE,
    PendingUpload,
    PublishNotApprovedError,
    PublishResult,
    SharePointAuthError,
    SharePointConnectionError,
    SharePointInvalidDestinationError,
    SharePointPublisher,
    SharePointPublishError,
)

FAKE_CLIENT_SECRET = "test-secret-not-real"
FAKE_TENANT_ID = "11111111-1111-1111-1111-111111111111"
FAKE_CLIENT_ID = "22222222-2222-2222-2222-222222222222"
FAKE_SITE_ID = "33333333-3333-3333-3333-333333333333"
FAKE_DRIVE_ID = "44444444-4444-4444-4444-444444444444"
FIXED_NOW = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)


def _fake_config(**overrides: object) -> SharePointConfig:
    fields: dict[str, object] = {
        "tenant_id": FAKE_TENANT_ID,
        "client_id": FAKE_CLIENT_ID,
        "client_secret": FAKE_CLIENT_SECRET,
        "site_id": FAKE_SITE_ID,
        "drive_id": None,
    }
    fields.update(overrides)
    return SharePointConfig(**fields)  # type: ignore[arg-type]


def _make_response(status_code: int, json_body: object = None) -> Mock:
    response = Mock(spec=requests.Response)
    response.status_code = status_code
    response.content = b"{}" if json_body is not None else b""
    response.json.return_value = json_body
    return response


def _mock_session(*, token_response: Mock, upload_response: Mock | None = None) -> MagicMock:
    session = MagicMock(spec=requests.Session)
    session.post.return_value = token_response
    if upload_response is not None:
        session.put.return_value = upload_response
    return session


def _sample_report() -> Report:
    return Report(
        report_id="rpt-bd007-001",
        kind=ReportKind.LOW_STOCK_REORDER,
        generated_at=FIXED_NOW,
    )


def _write_fake_workbook(tmp_path: Path, name: str = "report.xlsx") -> Path:
    path = tmp_path / name
    path.write_bytes(b"fake-xlsx-bytes-not-a-real-workbook")
    return path


# ---------------------------------------------------------------------------
# Construction: no network call, config-driven (not os.environ)
# ---------------------------------------------------------------------------


def test_publisher_makes_no_network_call_on_construction():
    session = MagicMock(spec=requests.Session)
    SharePointPublisher(_fake_config(), session=session)

    session.post.assert_not_called()
    session.put.assert_not_called()


def test_from_env_loads_config_and_makes_no_network_call(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SHAREPOINT_TENANT_ID", FAKE_TENANT_ID)
    monkeypatch.setenv("SHAREPOINT_CLIENT_ID", FAKE_CLIENT_ID)
    monkeypatch.setenv("SHAREPOINT_CLIENT_SECRET", FAKE_CLIENT_SECRET)
    monkeypatch.setenv("SHAREPOINT_SITE_ID", FAKE_SITE_ID)
    monkeypatch.delenv("SHAREPOINT_DRIVE_ID", raising=False)
    session = MagicMock(spec=requests.Session)

    publisher = SharePointPublisher.from_env(session=session)

    assert publisher.site_id == FAKE_SITE_ID
    session.post.assert_not_called()
    session.put.assert_not_called()


def test_publisher_repr_never_contains_client_secret():
    publisher = SharePointPublisher(_fake_config(), session=MagicMock(spec=requests.Session))

    rendered = repr(publisher)

    assert FAKE_CLIENT_SECRET not in rendered
    assert "<redacted>" in rendered
    assert FAKE_SITE_ID in rendered


# ---------------------------------------------------------------------------
# stage_upload: resolves the target + Graph upload URL, NO network call
# ---------------------------------------------------------------------------


def test_stage_upload_makes_no_network_call(tmp_path: Path):
    session = MagicMock(spec=requests.Session)
    publisher = SharePointPublisher(_fake_config(), session=session)
    report_path = _write_fake_workbook(tmp_path)

    publisher.stage_upload(str(report_path), dest_folder="Reports/2026-07")

    session.post.assert_not_called()
    session.put.assert_not_called()
    session.request.assert_not_called()


def test_stage_upload_returns_pending_upload_with_resolved_default_drive_url(tmp_path: Path):
    publisher = SharePointPublisher(
        _fake_config(drive_id=None), session=MagicMock(spec=requests.Session)
    )
    report_path = _write_fake_workbook(tmp_path, name="Low Stock Reorder.xlsx")

    pending = publisher.stage_upload(str(report_path), dest_folder="Reports/2026-07")

    assert isinstance(pending, PendingUpload)
    assert pending.report_path == report_path
    assert pending.file_name == "Low Stock Reorder.xlsx"
    assert pending.dest_folder == "Reports/2026-07"
    assert pending.dest_path == "Reports/2026-07/Low Stock Reorder.xlsx"
    assert pending.site_id == FAKE_SITE_ID
    assert pending.drive_id is None
    expected_url = (
        f"{GRAPH_BASE_URL}/sites/{FAKE_SITE_ID}/drive/root:"
        "/Reports/2026-07/Low%20Stock%20Reorder.xlsx:/content"
    )
    assert pending.upload_url == expected_url


def test_stage_upload_uses_specific_drive_when_configured(tmp_path: Path):
    publisher = SharePointPublisher(
        _fake_config(drive_id=FAKE_DRIVE_ID), session=MagicMock(spec=requests.Session)
    )
    report_path = _write_fake_workbook(tmp_path)

    pending = publisher.stage_upload(str(report_path))

    expected_url = (
        f"{GRAPH_BASE_URL}/sites/{FAKE_SITE_ID}/drives/{FAKE_DRIVE_ID}/root:/report.xlsx:/content"
    )
    assert pending.upload_url == expected_url
    assert pending.dest_folder == ""
    assert pending.dest_path == "report.xlsx"


def test_stage_upload_normalizes_leading_and_trailing_slashes(tmp_path: Path):
    publisher = SharePointPublisher(_fake_config(), session=MagicMock(spec=requests.Session))
    report_path = _write_fake_workbook(tmp_path)

    pending = publisher.stage_upload(str(report_path), dest_folder="/Reports/2026-07/")

    assert pending.dest_folder == "Reports/2026-07"
    assert pending.dest_path == "Reports/2026-07/report.xlsx"


def test_stage_upload_raises_file_not_found_for_missing_report(tmp_path: Path):
    publisher = SharePointPublisher(_fake_config(), session=MagicMock(spec=requests.Session))

    with pytest.raises(FileNotFoundError):
        publisher.stage_upload(str(tmp_path / "does-not-exist.xlsx"))


def test_stage_upload_rejects_path_traversal_dest_folder_with_no_network_call(
    tmp_path: Path,
):
    session = MagicMock(spec=requests.Session)
    publisher = SharePointPublisher(_fake_config(), session=session)
    report_path = _write_fake_workbook(tmp_path)

    with pytest.raises(SharePointInvalidDestinationError):
        publisher.stage_upload(str(report_path), dest_folder="Reports/../../etc")

    session.post.assert_not_called()
    session.put.assert_not_called()
    session.request.assert_not_called()


# ---------------------------------------------------------------------------
# publish: refuses without approval, sends nothing
# ---------------------------------------------------------------------------


def test_publish_refuses_without_approval_and_sends_nothing(tmp_path: Path):
    session = MagicMock(spec=requests.Session)
    publisher = SharePointPublisher(_fake_config(), session=session)
    pending = publisher.stage_upload(str(_write_fake_workbook(tmp_path)))

    with pytest.raises(PublishNotApprovedError):
        publisher.publish(pending)

    session.post.assert_not_called()
    session.put.assert_not_called()


def test_publish_defaults_to_unapproved_when_no_kwarg_given(tmp_path: Path):
    session = MagicMock(spec=requests.Session)
    publisher = SharePointPublisher(_fake_config(), session=session)
    pending = publisher.stage_upload(str(_write_fake_workbook(tmp_path)))

    with pytest.raises(PublishNotApprovedError):
        publisher.publish(pending, approved=False)

    session.post.assert_not_called()
    session.put.assert_not_called()


def test_publish_does_not_mutate_report_when_not_approved(tmp_path: Path):
    session = MagicMock(spec=requests.Session)
    publisher = SharePointPublisher(_fake_config(), session=session)
    pending = publisher.stage_upload(str(_write_fake_workbook(tmp_path)))
    report = _sample_report()

    with pytest.raises(PublishNotApprovedError):
        publisher.publish(pending, report=report)

    assert report.published_to is None
    assert report.published_at is None


# ---------------------------------------------------------------------------
# publish: exactly one upload PUT, and only when approved
# ---------------------------------------------------------------------------


def test_publish_performs_exactly_one_put_when_approved(tmp_path: Path):
    token_response = _make_response(200, {"access_token": "fake-graph-token"})
    upload_response = _make_response(
        201, {"webUrl": "https://contoso.sharepoint.com/sites/test/report.xlsx", "id": "item-1"}
    )
    session = _mock_session(token_response=token_response, upload_response=upload_response)
    publisher = SharePointPublisher(_fake_config(), session=session)
    pending = publisher.stage_upload(str(_write_fake_workbook(tmp_path)))

    result = publisher.publish(pending, approved=True)

    session.put.assert_called_once()
    assert isinstance(result, PublishResult)
    assert result.web_url == "https://contoso.sharepoint.com/sites/test/report.xlsx"
    assert result.graph_item_id == "item-1"
    assert result.dest_path == pending.dest_path


def test_publish_put_targets_the_staged_upload_url_with_bearer_token(tmp_path: Path):
    token_response = _make_response(200, {"access_token": "fake-graph-token"})
    upload_response = _make_response(201, {"webUrl": "https://contoso.sharepoint.com/x.xlsx"})
    session = _mock_session(token_response=token_response, upload_response=upload_response)
    publisher = SharePointPublisher(_fake_config(), session=session)
    pending = publisher.stage_upload(str(_write_fake_workbook(tmp_path)))

    publisher.publish(pending, approved=True)

    args, kwargs = session.put.call_args
    url = args[0] if args else kwargs.get("url")
    assert url == pending.upload_url
    assert kwargs["headers"]["Authorization"] == "Bearer fake-graph-token"
    assert kwargs["headers"]["Content-Type"] == XLSX_CONTENT_TYPE
    assert kwargs["data"] == pending.report_path.read_bytes()
    assert kwargs["timeout"] is not None


def test_publish_sets_report_published_fields_only_on_approved_success(tmp_path: Path):
    token_response = _make_response(200, {"access_token": "fake-graph-token"})
    upload_response = _make_response(
        200, {"webUrl": "https://contoso.sharepoint.com/sites/test/report.xlsx"}
    )
    session = _mock_session(token_response=token_response, upload_response=upload_response)
    publisher = SharePointPublisher(_fake_config(), session=session)
    pending = publisher.stage_upload(str(_write_fake_workbook(tmp_path)))
    report = _sample_report()

    assert report.published_to is None
    assert report.published_at is None

    publisher.publish(pending, approved=True, report=report)

    assert report.published_to == "https://contoso.sharepoint.com/sites/test/report.xlsx"
    assert report.published_at is not None


def test_publish_without_report_kwarg_does_not_require_or_touch_a_report(tmp_path: Path):
    token_response = _make_response(200, {"access_token": "fake-graph-token"})
    upload_response = _make_response(201, {"webUrl": "https://contoso.sharepoint.com/x.xlsx"})
    session = _mock_session(token_response=token_response, upload_response=upload_response)
    publisher = SharePointPublisher(_fake_config(), session=session)
    pending = publisher.stage_upload(str(_write_fake_workbook(tmp_path)))

    result = publisher.publish(pending, approved=True)

    assert isinstance(result, PublishResult)


# ---------------------------------------------------------------------------
# Failure paths: non-2xx / connection errors, never leaking the secret
# ---------------------------------------------------------------------------


def test_publish_raises_auth_error_on_non_2xx_token_response(tmp_path: Path):
    token_response = _make_response(401, None)
    session = _mock_session(token_response=token_response)
    publisher = SharePointPublisher(_fake_config(), session=session)
    pending = publisher.stage_upload(str(_write_fake_workbook(tmp_path)))

    with pytest.raises(SharePointAuthError) as exc_info:
        publisher.publish(pending, approved=True)

    assert exc_info.value.status_code == 401
    assert FAKE_CLIENT_SECRET not in str(exc_info.value)
    session.put.assert_not_called()


def test_publish_raises_publish_error_on_non_2xx_upload_response(tmp_path: Path):
    token_response = _make_response(200, {"access_token": "fake-graph-token"})
    upload_response = _make_response(507, None)
    session = _mock_session(token_response=token_response, upload_response=upload_response)
    publisher = SharePointPublisher(_fake_config(), session=session)
    pending = publisher.stage_upload(str(_write_fake_workbook(tmp_path)))
    report = _sample_report()

    with pytest.raises(SharePointPublishError) as exc_info:
        publisher.publish(pending, approved=True, report=report)

    assert exc_info.value.status_code == 507
    assert FAKE_CLIENT_SECRET not in str(exc_info.value)
    assert report.published_to is None
    assert report.published_at is None


def test_publish_raises_connection_error_on_token_network_failure_without_leaking_secret(
    tmp_path: Path,
):
    session = MagicMock(spec=requests.Session)
    session.post.side_effect = requests.ConnectionError("boom")
    publisher = SharePointPublisher(_fake_config(), session=session)
    pending = publisher.stage_upload(str(_write_fake_workbook(tmp_path)))

    with pytest.raises(SharePointConnectionError) as exc_info:
        publisher.publish(pending, approved=True)

    assert FAKE_CLIENT_SECRET not in str(exc_info.value)
    session.put.assert_not_called()


def test_publish_raises_connection_error_on_upload_network_failure(tmp_path: Path):
    token_response = _make_response(200, {"access_token": "fake-graph-token"})
    session = MagicMock(spec=requests.Session)
    session.post.return_value = token_response
    session.put.side_effect = requests.Timeout("timed out")
    publisher = SharePointPublisher(_fake_config(), session=session)
    pending = publisher.stage_upload(str(_write_fake_workbook(tmp_path)))

    with pytest.raises(SharePointConnectionError) as exc_info:
        publisher.publish(pending, approved=True)

    assert FAKE_CLIENT_SECRET not in str(exc_info.value)


# ---------------------------------------------------------------------------
# Secrets: never in repr/log/exception surfaces
# ---------------------------------------------------------------------------


def test_pending_upload_repr_never_contains_client_secret(tmp_path: Path):
    publisher = SharePointPublisher(_fake_config(), session=MagicMock(spec=requests.Session))
    pending = publisher.stage_upload(str(_write_fake_workbook(tmp_path)))

    assert FAKE_CLIENT_SECRET not in repr(pending)


def test_publish_not_approved_error_message_never_contains_client_secret(tmp_path: Path):
    publisher = SharePointPublisher(_fake_config(), session=MagicMock(spec=requests.Session))
    pending = publisher.stage_upload(str(_write_fake_workbook(tmp_path)))

    with pytest.raises(PublishNotApprovedError) as exc_info:
        publisher.publish(pending)

    assert FAKE_CLIENT_SECRET not in str(exc_info.value)
