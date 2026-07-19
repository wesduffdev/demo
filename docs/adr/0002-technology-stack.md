# 0002. Technology stack: Python, file-based snapshots, no database in v1

- **Status:** Accepted
- **Date:** 2026-07-19

## Context
Buyer's Desk aggregates sales & inventory from Fulfil, computes reorder/assortment guidance, and
produces Excel reports published to SharePoint. Fulfil is the system of record. We need a stack that
fits data work and Excel output, without over-building infrastructure for v1.

## Decision
We will build the pipeline in **Python**. Aggregated data is stored as **file-based snapshots
(CSV/Parquet)** — **no database in v1**, since Fulfil remains the system of record and v1 needs only
point-in-time snapshots. Excel reports are generated with **openpyxl**. Integrations use the
**Fulfil REST API** for extraction and **Microsoft Graph** for SharePoint publishing. Credentials
come from environment variables / a secrets manager (never hardcoded).

## Alternatives considered
- **Add a database (Postgres/SQLite) now** — useful once we need history/query, but premature for v1
  point-in-time snapshots; adds ops burden and a destructive-action surface with no v1 payoff.
- **A BI/spreadsheet-native tool instead of code** — closer to today's Excel workflow, but hard to
  test, version, and automate; correctness (our core value) is hard to guarantee.
- **Node/TypeScript** — viable, but Python's data-handling and Excel ecosystem is the stronger fit.

## Consequences
**Good** — minimal moving parts for v1; snapshots are diffable files; strong Python libraries for
data + Excel; correctness is testable (see `test-engineer`).
**Bad** — file-based storage won't scale to rich historical querying; adding a database later is a
new ADR and a migration. This decision is `[inferred]` by the Product Owner and should be confirmed
by the build team at first architecture review.

## Related
- Reversing/expanding this (e.g. introducing a database) requires a superseding ADR.
- Bounded contexts: Data Integration, Reporting & Publishing.
