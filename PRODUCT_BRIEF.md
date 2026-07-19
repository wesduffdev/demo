# Buyer's Desk — Decision Record & Audit Trail

> The plan and product story live in `docs/PRD.md`. This file is the audit delta only —
> how the setup was decided, not what the product is.

## Given vs. inferred
- **[given]** (client stated): High-end pet food / snacks / toys retailer ("Whole Foods for pets").
  Primary user is the company's Buyer. Money moment = agents + rules that automate data aggregation
  and display for fast Buyer decisions; manage inventory; decide new orders when sales are high; pull
  underperforming products; reports are the cornerstone for leadership & buyers. Excel is heavily
  used. Company uses **Fulfil** (ERP) and saves reports to **SharePoint**. Real company name not
  required.
- **[inferred]** (assumed): Leadership as a secondary report-consuming persona; the specific v1
  scope IN/OUT list; the success-metric targets; the technology stack (ADR-0002 — Python, file-based
  snapshots, no DB in v1) — flagged for the build team to confirm at first architecture review.
- **Confirmed by client:** system *recommends*, never auto-places orders (Checkpoint A); PII rule
  stays ON because Fulfil holds customer data (Checkpoint D).

## Rules Matrix (ratified — Checkpoint D)
All eight ON; none switched off.

| Rule | On/Off | Severity | Binds | Note |
|---|---|---|---|---|
| no-pii | ON | Critical / MUST | global | Aggregate at source; never pull/store/log customer-level PII from Fulfil. |
| security-secrets | ON | Critical / MUST | global | Fulfil API keys + SharePoint auth via env/secrets only. |
| destructive-actions | ON | Critical / MUST | agents with Bash | No `rm -rf` / overwrite / force-ops without approval. |
| human-in-the-loop | ON | High / MUST | report-publisher + outward | SharePoint publish + any order action human-gated. |
| external-services | ON | High / MUST | data-integrator, report-publisher | Read-only default vs Fulfil; SharePoint writes gated. |
| legal-compliance | ON | High / SHOULD | global | Dependency licensing + personal-data retention. |
| code-quality-testing | ON | Medium / MUST | code-writing agents | Build/lint/tests pass; bug fix needs failing→passing test. |
| scope-discipline | ON | Medium / MUST | all subagents | Stay in lane; hand off through the PO. |

**Switched OFF, on purpose:** None. `legal-compliance` was the one candidate for OFF (internal
tooling) but kept ON for dependency-licensing and personal-data-retention coverage.

## Hooks (ratified — Checkpoint E)
Four accepted (`jq` present, so they enforce):
- **guard-secret-files** (PreToolUse `Edit|Write`) — blocks writes to secret/credential files.
- **guard-dangerous-commands** (PreToolUse `Bash`) — blocks destructive shell.
- **guard-no-pii** (PreToolUse `Bash|WebFetch`) — blocks outbound PII; allowlists synthetic ranges.
- **session-context** (SessionStart) — orients the PO each session.

Deferred: `format-file`, `inject-context`, `run-affected-tests` (add once the stack stabilizes).

## ADR index
- **0000** Record architecture decisions as ADRs — Accepted
- **0001** Agent boundaries follow bounded contexts — Accepted
- **0002** Tech stack: Python, file-based snapshots, no DB in v1 — Accepted
- **0003** Promote security-secrets / destructive-actions / no-pii to hard-hook enforcement — Accepted
- **0004** Output mode A — stamp in place — Accepted

## Open assumptions to confirm
- Technology stack (ADR-0002) is inferred — confirm at first architecture review.
- Success-metric target values (e.g. the "≥90%" and "minutes not hours" thresholds) are inferred
  placeholders — set real targets with the Buyer/leadership.
- Whether Fulfil access can be scoped to a PII-free view (would reduce, not remove, the no-PII risk).

## How this was generated
Intake run on 2026-07-19. Path: Fast Track. Output mode: A (stamp in place). Re-run the intake to
revise any phase.
