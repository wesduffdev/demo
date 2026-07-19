# Buyer's Desk — Product Requirements Document (PRD)

## Problem & opportunity
The Buyer at a high-end pet products retailer ("Whole Foods for pets" — food, snacks, toys) makes
purchasing, reorder, and keep-or-drop decisions largely by hand: pulling data from **Fulfil**,
crunching it in **Excel**, and saving reports to **SharePoint**. It's slow, manual, and the insights
leadership relies on are buried in spreadsheet labor. The opportunity is to automate the aggregation,
analysis, and reporting so decisions become fast and reliable.

## Target users & jobs-to-be-done
**Buyer (primary)**
- *When* stock is running low or an item is selling fast, *I want* an automatic list of what to
  reorder and how much, *so I can* place orders quickly and with confidence.
- *When* I review the range, *I want* underperformers and overstock flagged, *so I can* decide what
  to pull from the shelf or discount.

**Leadership (secondary)**
- *When* I review business performance, *I want* consistent, up-to-date reports in SharePoint, *so I
  can* make merchandising and financial calls without waiting on manual spreadsheet work.

## Core value / money moment
Automatically aggregate Fulfil sales + inventory into the plans, reports, and reorder/assortment
guidance the Buyer needs — turning hours of Excel work into fast, reliable decisions, with finished
reports saved to SharePoint. The system **recommends; the human Buyer commits every order.**

## Scope
- **In (v1):** (1) aggregate sales & inventory from Fulfil into clean datasets; (2) generate the core
  reports (sales performance, low-stock/reorder, slow-movers/overstock) as Excel-compatible output;
  (3) reorder guidance (what/how much/when by velocity + stock); (4) assortment guidance (flag
  underperformers to pull); (5) publish reports to SharePoint.
- **Out / non-goals:** no auto-purchasing / auto-spend; no customer-facing storefront, payments, or
  customer accounts; not replacing Fulfil or SharePoint (integrate only); no ML/statistical
  forecasting in v1 (start with sales-velocity reorder points).

## Domain model (DDD)
Agreed vocabulary is in `docs/GLOSSARY.md`; bounded contexts, aggregates, and domain events are in
`docs/context-map.md`. Summary: three contexts — **Data Integration** (Fulfil → clean DataSnapshot),
**Merchandising Intelligence** (the core: velocity, reorder points, reorder/slow-mover/overstock
guidance), and **Reporting & Publishing** (Excel reports → SharePoint) — linked by the events
`SnapshotAggregated` → `RecommendationsReady` → `ReportPublished`.

## Agent team
- `data-integrator` — Data Integration; pulls & validates Fulfil data into a clean DataSnapshot.
- `merchandising-analyst` — Merchandising Intelligence (core); reorder & assortment guidance.
- `report-publisher` — Reporting & Publishing; builds Excel reports and publishes to SharePoint.
- `test-engineer` — cross-cutting; guards aggregation & calculation correctness.
- `code-reviewer` — cross-cutting; read-only diff review.
- `security-compliance-reviewer` — cross-cutting; read-only rule enforcement (creds/PII/licensing).

## Success metrics
1. Weekly report set produced in minutes, not hours (manual Excel time → near-zero).
2. ≥90% of SKUs that cross a reorder threshold are flagged automatically each cycle.
3. A slow-mover / overstock list is generated every cycle with no manual spreadsheet work.
4. Reports land in the correct SharePoint location with consistent formatting, automatically.
5. Buyer adoption — acts on the generated reports rather than rebuilding them in Excel.

## Roadmap (first milestones)
1. **Data Integration first** — stand up the Fulfil extract + a validated, file-based DataSnapshot
   (the foundation everything else reads).
2. **Merchandising Intelligence** — velocity, reorder points, ReorderSuggestions; then SlowMover /
   Overstock flags.
3. **Reporting & Publishing** — Excel report generation, then the human-gated SharePoint publish.
4. **Hardening** — regression tests on the math, then optional format/test hooks and a CI gate.

## Decisions
Key decisions and their rationale are recorded as ADRs in `docs/adr/`:
- [ADR-0000](adr/0000-record-architecture-decisions.md) — Record architecture decisions as ADRs
- [ADR-0001](adr/0001-agent-boundaries-follow-bounded-contexts.md) — Agent boundaries follow bounded contexts
- [ADR-0002](adr/0002-technology-stack.md) — Technology stack (Python, file-based snapshots, no DB in v1)
- [ADR-0003](adr/0003-hard-hook-enforcement.md) — Promote critical rules to hard-hook enforcement
- [ADR-0004](adr/0004-output-mode-stamp-in-place.md) — Output mode: stamp in place
