# 0003. Promote critical rules to hard-hook enforcement

- **Status:** Accepted
- **Date:** 2026-07-19

## Context
The rules in `.claude/rules/` are Markdown guidance — an agent can reason past them. Three failure
modes are expensive enough for Buyer's Desk that a single miss is unacceptable: a leaked Fulfil or
SharePoint **credential**, a **destroyed dataset** or force-push, and **customer PII exfiltrated** to
an external service (Fulfil is a full ERP, so PII is one careless query away). `jq` is installed on
the machine, so hooks will actually enforce.

## Decision
We will back three rules with deterministic **PreToolUse hooks** that hard-block the action (exit 2),
in addition to the prose rules:
- `security-secrets` → `guard-secret-files.sh` (blocks writes to `.env`, `*.pem`, keys, credentials).
- `destructive-actions` → `guard-dangerous-commands.sh` (blocks `rm -rf`, force-push, `DROP`/
  `TRUNCATE`, `curl … | sh`).
- `no-pii` → `guard-no-pii.sh` (scans **outbound** Bash/WebFetch only for PII; allowlists synthetic
  test ranges; does not scan ordinary file writes).

A SessionStart `session-context.sh` hook also orients the Product Owner each session. Format-on-save
and test-on-change hooks are **deferred** until the stack stabilizes.

## Alternatives considered
- **Rely on prose rules only** — zero friction, but no hard stop; one reasoned-past mistake leaks a
  credential or PII.
- **Scan every file write for PII** — would block the synthetic fixtures the no-PII rule prescribes
  and break legitimate internal data work; scoping to outbound tools protects against exfiltration
  without the false positives.
- **Enable test-on-change now** — slow/flaky before a stack exists; the `test-engineer` agent and a
  future CI gate cover correctness meanwhile.

## Consequences
**Good** — the three highest-cost mistakes are hard-blocked, not merely discouraged; enforcement is
consistent regardless of agent reasoning.
**Bad** — hooks run in the interaction loop (kept fast); they only enforce while `jq` is installed
(they safely no-op otherwise); accepting hooks triggers a one-time workspace-trust dialog on next
launch.

## Related
- Rules: `security-secrets`, `destructive-actions`, `no-pii`.
- Wiring: `.claude/settings.json`, `.claude/hooks/*.sh`.
