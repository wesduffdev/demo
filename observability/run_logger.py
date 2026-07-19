"""Orchestrator run logging & observability (BD-000).

A minimal, standard-library-only run logger the Product Owner (orchestrator)
uses to record, per cycle:

* what the orchestrator is doing — the ordered action / hand-off sequence;
* which specialist agents ran, how many tokens each used, and how long each
  took to complete.

Each run is written to a timestamped ``.txt`` file in a repo-root ``logs/``
folder, which is intentionally checked in (see ``logs/README.md``). Only
orchestration metadata is recorded — agent names, token counts, durations, and
timestamps — never secrets or customer PII. Free-text ``message``/``note``
fields additionally pass through a redaction guard as defense in depth.

This module deliberately depends on the standard library only and presupposes
no package layout, so it does not pre-empt the repo scaffolding decided in
BD-001.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Union


def _utc_now() -> datetime:
    """Default clock: timezone-aware UTC ``now``."""
    return datetime.now(timezone.utc)


# Patterns for values that must never land in a checked-in log. Kept
# intentionally conservative — this is a safety net, not a substitute for only
# passing metadata in the first place.
_REDACTION_PATTERNS = (
    re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),   # email address
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),                            # OpenAI-style secret key
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),                           # GitHub personal access token
    re.compile(r"\bgho_[A-Za-z0-9]{20,}\b"),                           # GitHub OAuth token
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                               # AWS access key id
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]+"),                    # bearer token
    re.compile(r"(?i)\b(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+"),  # key=value secret
)

_REDACTED = "[REDACTED]"


def _redact(text: str) -> str:
    """Scrub obvious secrets/PII from a free-text string."""
    cleaned = str(text)
    for pattern in _REDACTION_PATTERNS:
        cleaned = pattern.sub(_REDACTED, cleaned)
    return cleaned


def _fmt_ts(dt: datetime) -> str:
    """Render a datetime as a compact UTC ISO-8601 string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt_tokens(tokens: Optional[int]) -> str:
    return "n/a" if tokens is None else str(tokens)


def _fmt_elapsed(elapsed_s: Optional[float]) -> str:
    return "n/a" if elapsed_s is None else f"{elapsed_s:.1f}s"


@dataclass
class _Action:
    ts: datetime
    actor: str
    message: str


@dataclass
class _AgentEntry:
    name: str
    tokens: Optional[int]
    elapsed_s: Optional[float]
    status: str
    note: str


class RunLogger:
    """Collects orchestrator actions and agent telemetry, then writes a log.

    Example::

        run = RunLogger()
        run.log_action("Pulled BD-000 into In Progress")
        run.log_agent("test-engineer", tokens=4200, elapsed_s=31.5)
        path = run.finalize()  # -> logs/run-<timestamp>.txt
    """

    def __init__(
        self,
        logs_dir: Union[str, Path] = "logs",
        run_id: Optional[str] = None,
        now: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._now: Callable[[], datetime] = now or _utc_now
        # ``now`` is expected to return a UTC datetime; normalize defensively so the
        # run_id / filename 'Z' suffix is always truthful even if a caller injects a
        # naive or non-UTC clock (mirrors _fmt_ts).
        start = self._now()
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        self._start: datetime = start.astimezone(timezone.utc)
        self.logs_dir: Path = Path(logs_dir)
        self.run_id: str = run_id or f"run-{self._start:%Y%m%dT%H%M%SZ}"
        self._actions: List[_Action] = []
        self._agents: List[_AgentEntry] = []

    @property
    def path(self) -> Path:
        """The file this run will be (or was) written to."""
        return self.logs_dir / f"{self.run_id}.txt"

    def log_action(self, message: str, actor: str = "orchestrator") -> "RunLogger":
        """Record one orchestrator action / hand-off step, in order."""
        self._actions.append(
            _Action(ts=self._now(), actor=_redact(actor), message=_redact(message))
        )
        return self

    def log_agent(
        self,
        name: str,
        tokens: Optional[int],
        elapsed_s: Optional[float],
        status: str = "completed",
        note: str = "",
    ) -> "RunLogger":
        """Record a specialist agent's run: name, tokens used, elapsed time."""
        self._agents.append(
            _AgentEntry(
                name=_redact(name),
                tokens=tokens,
                elapsed_s=elapsed_s,
                status=_redact(status),
                note=_redact(note),
            )
        )
        return self

    def render(self) -> str:
        """Build the full log text without writing it to disk."""
        finished = self._now()
        lines: List[str] = [
            "Buyer's Desk — Orchestrator Run Log",
            f"Run ID:  {self.run_id}",
            f"Started: {_fmt_ts(self._start)} (UTC)",
            "",
            "[ACTIONS]  what the orchestrator did (hand-off sequence)",
        ]
        if self._actions:
            for action in self._actions:
                lines.append(
                    f"  {_fmt_ts(action.ts)}  {action.actor:<14}  {action.message}"
                )
        else:
            lines.append("  (none recorded)")

        lines += ["", "[AGENTS]  specialist runs — name / tokens / elapsed / status"]
        if self._agents:
            for agent in self._agents:
                line = (
                    f"  agent={agent.name}  tokens={_fmt_tokens(agent.tokens)}"
                    f"  elapsed={_fmt_elapsed(agent.elapsed_s)}  status={agent.status}"
                )
                if agent.note:
                    line += f"  note={agent.note}"
                lines.append(line)
        else:
            lines.append("  (none recorded)")

        total_tokens = sum(a.tokens for a in self._agents if isinstance(a.tokens, int))
        total_elapsed = sum(
            a.elapsed_s for a in self._agents if isinstance(a.elapsed_s, (int, float))
        )
        lines += [
            "",
            f"Finished: {_fmt_ts(finished)} (UTC)",
            f"Totals:   agents={len(self._agents)}  tokens={total_tokens}"
            f"  elapsed={total_elapsed:.1f}s",
            "",
        ]
        return "\n".join(lines)

    def finalize(self) -> Path:
        """Write the run log to ``logs_dir/<run_id>.txt`` and return its path."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        target = self.path
        target.write_text(self.render(), encoding="utf-8")
        return target
