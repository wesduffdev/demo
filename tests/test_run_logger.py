"""Tests for the BD-000 run-logging harness (``observability/run_logger.py``).

Uses only synthetic, clearly-fake fixtures (fake emails / fake secret-shaped
tokens) per the no-pii rule. Every test writes under pytest's ``tmp_path`` —
never the real repo ``logs/`` directory.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from observability.run_logger import RunLogger

FIXED_START = datetime(2026, 7, 19, 23, 0, 35, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 1. finalize() writes to logs_dir/<run_id>.txt under tmp_path; .path matches
# ---------------------------------------------------------------------------


def test_finalize_creates_file_under_tmp_path_and_path_matches(tmp_path):
    logs_dir = tmp_path / "logs"
    run = RunLogger(logs_dir=logs_dir, now=lambda: FIXED_START)

    run.log_action("Started cycle")
    run.log_agent("data-integrator", tokens=500, elapsed_s=3.0)

    expected_path = logs_dir / f"{run.run_id}.txt"
    assert run.path == expected_path

    written_path = run.finalize()

    assert written_path == expected_path
    assert written_path.exists()
    assert written_path.is_file()
    # finalize() must have created the logs dir itself.
    assert logs_dir.is_dir()

    # Sanity: never touching the real repo logs/ directory.
    assert "buyerTest/logs" not in str(written_path)


def test_finalize_returns_pathlib_path(tmp_path):
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)
    result = run.finalize()
    assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# 2. Fixed injected `now` -> deterministic run_id / filename / timestamps
# ---------------------------------------------------------------------------


def test_fixed_now_produces_deterministic_run_id_and_filename(tmp_path):
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)

    assert run.run_id == "run-20260719T230035Z"
    assert run.path.name == "run-20260719T230035Z.txt"

    written_path = run.finalize()
    assert written_path.name == "run-20260719T230035Z.txt"


def test_fixed_now_produces_deterministic_started_timestamp(tmp_path):
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)
    text = run.render()

    assert "Run ID:  run-20260719T230035Z" in text
    assert "Started: 2026-07-19T23:00:35Z (UTC)" in text


def test_explicit_run_id_overrides_derived_default(tmp_path):
    run = RunLogger(logs_dir=tmp_path / "logs", run_id="run-custom-id", now=lambda: FIXED_START)
    assert run.run_id == "run-custom-id"
    assert run.path == tmp_path / "logs" / "run-custom-id.txt"


def test_render_is_repeatable_with_a_constant_clock(tmp_path):
    """With a constant (non-advancing) clock, render() must be byte-identical
    across calls, and finalize() must persist exactly that text."""
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)
    run.log_action("Kicked off cycle")
    run.log_agent("merchandising-analyst", tokens=999, elapsed_s=4.2)

    first_render = run.render()
    second_render = run.render()
    assert first_render == second_render

    written_path = run.finalize()
    assert written_path.read_text(encoding="utf-8") == first_render


# ---------------------------------------------------------------------------
# 3. Actions appear in the order logged, inside [ACTIONS]
# ---------------------------------------------------------------------------


def test_actions_appear_in_logged_order(tmp_path):
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)
    run.log_action("first: pulled snapshot")
    run.log_action("second: computed reorder plan")
    run.log_action("third: published report")

    text = run.render()

    actions_section = text.split("[ACTIONS]")[1].split("[AGENTS]")[0]
    idx_first = actions_section.index("first: pulled snapshot")
    idx_second = actions_section.index("second: computed reorder plan")
    idx_third = actions_section.index("third: published report")

    assert idx_first < idx_second < idx_third


def test_log_action_returns_self_for_chaining(tmp_path):
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)
    result = run.log_action("a").log_action("b").log_agent("x", 1, 1.0)
    assert result is run


def test_no_actions_recorded_renders_placeholder(tmp_path):
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)
    text = run.render()
    actions_section = text.split("[ACTIONS]")[1].split("[AGENTS]")[0]
    assert "(none recorded)" in actions_section


# ---------------------------------------------------------------------------
# 4. Agent entries: name/tokens/elapsed/status; None -> n/a and excluded from
#    numeric totals; Totals reflects correct count and sums.
# ---------------------------------------------------------------------------


def test_agent_entry_shows_name_tokens_elapsed_status(tmp_path):
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)
    run.log_agent("data-integrator", tokens=1200, elapsed_s=12.5, status="completed")

    text = run.render()

    assert "agent=data-integrator  tokens=1200  elapsed=12.5s  status=completed" in text


def test_agent_with_none_tokens_and_elapsed_renders_na_and_excluded_from_totals(tmp_path):
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)
    run.log_agent("data-integrator", tokens=1200, elapsed_s=12.5, status="completed")
    run.log_agent("report-publisher", tokens=None, elapsed_s=None, status="skipped")

    text = run.render()

    # The None-valued agent renders n/a for both fields.
    assert "agent=report-publisher  tokens=n/a  elapsed=n/a  status=skipped" in text

    # Totals: 2 agents total, but only the numeric agent contributes to sums.
    totals_line = next(line for line in text.splitlines() if line.startswith("Totals:"))
    match = re.search(
        r"Totals:\s+agents=(\d+)\s+tokens=(\d+)\s+elapsed=([\d.]+)s", totals_line
    )
    assert match is not None, f"Totals line did not match expected shape: {totals_line!r}"
    agents_count, total_tokens, total_elapsed = match.groups()

    assert agents_count == "2"
    assert total_tokens == "1200"
    assert total_elapsed == "12.5"


def test_totals_sum_across_multiple_numeric_agents(tmp_path):
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)
    run.log_agent("data-integrator", tokens=1000, elapsed_s=10.0)
    run.log_agent("merchandising-analyst", tokens=2000, elapsed_s=5.5)
    run.log_agent("report-publisher", tokens=None, elapsed_s=None, status="skipped")

    text = run.render()
    totals_line = next(line for line in text.splitlines() if line.startswith("Totals:"))
    match = re.search(
        r"Totals:\s+agents=(\d+)\s+tokens=(\d+)\s+elapsed=([\d.]+)s", totals_line
    )
    assert match is not None
    agents_count, total_tokens, total_elapsed = match.groups()

    assert agents_count == "3"
    assert total_tokens == "3000"
    assert total_elapsed == "15.5"


def test_no_agents_recorded_totals_are_zero(tmp_path):
    """Edge case: an empty cycle (no agents ran) must not error and must sum
    to zero, not raise or render blank/garbage totals."""
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)
    text = run.render()

    agents_section = text.split("[AGENTS]")[1].split("Finished:")[0]
    assert "(none recorded)" in agents_section

    totals_line = next(line for line in text.splitlines() if line.startswith("Totals:"))
    match = re.search(
        r"Totals:\s+agents=(\d+)\s+tokens=(\d+)\s+elapsed=([\d.]+)s", totals_line
    )
    assert match is not None
    agents_count, total_tokens, total_elapsed = match.groups()
    assert agents_count == "0"
    assert total_tokens == "0"
    assert total_elapsed == "0.0"


def test_log_agent_returns_self_for_chaining(tmp_path):
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)
    result = run.log_agent("test-engineer", tokens=10, elapsed_s=1.0)
    assert result is run


# ---------------------------------------------------------------------------
# 5. Redaction: fake email / fake secret must never appear in rendered or
#    finalized text; must be replaced with [REDACTED].
# ---------------------------------------------------------------------------


def test_action_message_email_is_redacted(tmp_path):
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)
    fake_email = "fake.user@example.com"
    run.log_action(f"Escalated to {fake_email} for approval")

    text = run.render()

    assert fake_email not in text
    assert "[REDACTED]" in text


def test_agent_note_secret_token_is_redacted(tmp_path):
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)
    fake_secret = "ghp_1234567890ABCDEFGHIJKL"  # fake-shaped GitHub PAT, 24 chars
    run.log_agent(
        "data-integrator",
        tokens=100,
        elapsed_s=1.0,
        note=f"leaked credential {fake_secret} in log line",
    )

    text = run.render()

    assert fake_secret not in text
    assert "[REDACTED]" in text


def test_agent_note_key_value_secret_is_redacted(tmp_path):
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)
    fake_secret_value = "SUPERSECRETVALUE12345"
    run.log_agent(
        "data-integrator",
        tokens=100,
        elapsed_s=1.0,
        note=f"rotated api_key={fake_secret_value} per policy",
    )

    text = run.render()

    assert fake_secret_value not in text
    assert "[REDACTED]" in text


def test_redaction_survives_finalize_to_disk(tmp_path):
    """Redaction must apply to the persisted file, not just render()."""
    run = RunLogger(logs_dir=tmp_path / "logs", now=lambda: FIXED_START)
    fake_email = "another.fake@example.org"
    fake_secret = "AKIAABCDEFGHIJ12345Z"  # fake-shaped AWS access key id

    run.log_action(f"Notify {fake_email}")
    run.log_agent("report-publisher", tokens=50, elapsed_s=2.0, note=f"key {fake_secret} rotated")

    written_path = run.finalize()
    on_disk = written_path.read_text(encoding="utf-8")

    assert fake_email not in on_disk
    assert fake_secret not in on_disk
    assert on_disk.count("[REDACTED]") >= 2
