# logs/

Orchestrator run logs (see ticket **BD-000 — Orchestrator run logging & observability**).

Each orchestration cycle writes a timestamped `.txt` file here — e.g.
`run-20260719T230000Z.txt` — via `observability/run_logger.py` (`RunLogger`). Each log
captures:

- **[ACTIONS]** — what the orchestrator (Product Owner) did, in order (the agent hand-off sequence).
- **[AGENTS]** — each specialist agent that ran, with its **name**, **token usage**, and
  **elapsed time** to completion.
- **Totals** — agent count, summed tokens, summed elapsed time.

> ✅ Unlike [`output/`](../output/README.md) (which is git-ignored because it holds real company
> financials), **`logs/` is intentionally checked in.** It records **only orchestration metadata** —
> agent names, token counts, durations, and timestamps — and **never** secrets or customer PII.
> Free-text lines pass through a redaction guard in `RunLogger` as defense in depth. See
> `.claude/rules/no-pii.md` and `.claude/rules/security-secrets.md`.
