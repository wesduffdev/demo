# 0001. Agent boundaries follow bounded contexts

- **Status:** Accepted
- **Date:** 2026-07-19

## Context
Buyer's Desk spans three areas of the business: pulling data from Fulfil, turning it into buy/pull
guidance, and producing/publishing reports. We need a rule for how many agents to create and what
each may write. Ad-hoc splits risk two agents editing the same model and disagreeing on what a term
(e.g. "DataSnapshot" or "Report") means.

## Decision
We will make each **bounded context** the ownership boundary of exactly one agent:
- **Data Integration** → `data-integrator`, guarding the `DataSnapshot` aggregate.
- **Merchandising Intelligence** → `merchandising-analyst`, guarding `ReorderPlan` and
  `AssortmentReview`.
- **Reporting & Publishing** → `report-publisher`, guarding `Report`.

Data Integration is deliberately isolated behind an **anti-corruption layer** around Fulfil, so that
if Fulfil's model changes only one agent is affected. Merchandising Intelligence keeps **both**
reorder and assortment logic together for v1 (one analytical brain), rather than splitting into two
agents. Cross-cutting agents (`test-engineer`, `code-reviewer`, `security-compliance-reviewer`) serve
all contexts and own no business aggregate. Agents coordinate only through domain events routed by
the Product Owner; subagents are not granted the Agent tool.

## Alternatives considered
- **One monolithic agent for everything** — simpler to start, but no guardrails; it conflates
  vocabularies across contexts and edits any file.
- **Split Merchandising into separate reorder and assortment agents** — finer-grained, but both
  consume the same DataSnapshot and serve the same Buyer; splitting multiplies hand-offs without a
  modeling reason in v1.
- **Fold Data Integration into Merchandising** — fewer agents, but couples the volatile Fulfil
  integration to the analytical core, so a Fulfil change ripples into the reasoning logic.

## Consequences
**Good** — clear, non-overlapping write boundaries; each term has one authoritative owner; the
context map doubles as the roster and event-routing table; the Fulfil integration is quarantined.
**Bad** — cross-context features require an explicit event hand-off; re-drawing a boundary later
(e.g. splitting Merchandising) means reassigning an agent and writing a new ADR.

## Related
- Defines the ownership used by `docs/GLOSSARY.md` and `docs/context-map.md`.
- Events: `SnapshotAggregated`, `RecommendationsReady`, `ReportPublished`.
