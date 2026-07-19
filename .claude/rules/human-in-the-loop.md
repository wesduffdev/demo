# Rule: Human-in-the-Loop for Irreversible & Outward-Facing Actions

**Severity: High.**

## Scope
Any action that reaches the outside world or cannot be undone.

## Directives
- STOP and get explicit human approval before any externally visible or hard-to-reverse action:
  sending email/SMS/push/Slack, posting to public channels, publishing packages/releases,
  deploying to production, merging to the default branch, charging or refunding money,
  creating/deleting cloud infrastructure, or notifying real customers.
- Present a clear preview first — recipient/target, exact payload/content, expected effect —
  and proceed only after an affirmative human response.
- Distinguish DRAFT from SEND: prepare drafts, PRs, and staged changes freely; the final
  send/publish/deploy step is human-gated.
- Bulk outward actions (e.g. emailing a list) require approval of the FULL scope (how many, to
  whom). Never send in a loop on your own initiative.
- If approval is unavailable, leave the work in a staged, resumable state and report what
  remains — do not force completion.

## Enforcement
Set outward-facing tools to `permissionMode: default` (ask), and back the critical ones with a
PreToolUse approval hook.
