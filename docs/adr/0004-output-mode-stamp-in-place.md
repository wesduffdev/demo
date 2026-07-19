# 0004. Output mode: stamp in place

- **Status:** Accepted
- **Date:** 2026-07-19

## Context
The Product Owner Intake can deliver the generated company setup two ways: **Mode A** writes the
setup into this repo and stops; **Mode B** additionally packages it as an installable Claude Code
plugin + marketplace on a dedicated branch, so the same shape can be stamped into other repos. This
is the first setup for Buyer's Desk and there is no immediate need to replicate it elsewhere.

## Decision
We will use **Mode A — stamp in place**: generate `CLAUDE.md`, the agents, rules, hooks, merged
`settings.json`, and the `docs/` plan (PRD, glossary, context map, ADRs) directly into this
repository, and stop. No plugin, marketplace, or stamp branch is produced.

## Alternatives considered
- **Mode B — also publish an installable plugin** — valuable if we later want to stamp this company
  shape into other/new repos, but it adds a distribution artifact to maintain (version bumps, a
  self-contained plugin, a published branch) with no current consumer.

## Consequences
**Good** — simplest path to a working setup; nothing extra to maintain; the repo owns real, editable
files.
**Bad** — replicating this setup into another repo later means re-running the intake or manually
copying files. If reuse becomes a need, a superseding ADR can adopt Mode B.

## Related
- Supersede this ADR if the setup is later packaged for distribution (Mode B / Phase 8).
