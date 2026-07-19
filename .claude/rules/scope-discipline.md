# Rule: Scope Discipline — Agents Stay in Lane

**Severity: Medium.**

## Scope
All subagents in the roster.

## Directives
- Each agent acts ONLY within the responsibilities in its own agent file. If a task falls
  outside your lane, hand it back to the Product Owner for routing — do not do another agent's
  job.
- Do not modify another agent's owned files, domains, or configuration. Coordinate through the
  Product Owner rather than reaching across boundaries.
- Do the task asked and nothing more: no speculative features, no opportunistic refactors. If
  you spot adjacent work, note it and let a human/PO decide.
- When requirements are ambiguous, or a task exceeds your authority (touches rules, secrets, or
  another domain), ASK before acting.
- Stay within the project working directory and the tools your agent file grants. Do not attempt
  to escalate your own permissions.
- Keep outputs handoff-ready: report what you did, what changed, and what remains.

## Enforcement
Encoded through each subagent's `tools`/`disallowedTools` and `description`. The Product Owner
arbitrates all cross-agent work; subagents are not granted the `Agent` tool.
