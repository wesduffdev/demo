# 0000. Record architecture decisions as ADRs

- **Status:** Accepted
- **Date:** 2026-07-19

## Context
Buyer's Desk is built and operated by a team of AI agents plus human owners. Decisions about
domain boundaries, stack, and rules will be made over time, by different people and agents. Without
a durable record of *why* things are the way they are, future teammates (human or agent) will
re-litigate settled questions or break load-bearing decisions they didn't know existed.

## Decision
We will record every significant, hard-to-reverse decision as a numbered Architecture Decision
Record (ADR) in `docs/adr/`, using a short MADR-style template (Context / Decision / Alternatives /
Consequences). ADRs are append-only: when a decision is reversed, we write a new ADR and mark the
old one **Superseded** — we never edit or delete it.

## Alternatives considered
- **No formal record (tribal knowledge / commit messages)** — cheap now, but the rationale is lost
  and decisions silently drift.
- **A single living design doc** — one editable doc loses the history of what was tried and why it
  changed; ADRs preserve the trail.

## Consequences
**Good** — a permanent "why is it like this?" history; onboarding and agent context are cheaper;
reversals are explicit and traceable.
**Bad** — a small per-decision authoring cost; discipline required to keep the log current.

## Related
- All subsequent ADRs (0001+) follow this convention.
