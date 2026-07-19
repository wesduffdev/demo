# Buyer's Desk — Decision Record & Audit Trail (DRAFT)

> **This is a mid-intake draft**, saved via `save draft` on 2026-07-19 so the DDD work survives a
> long session. It is NOT the final brief. The full product story will live in `docs/PRD.md` once
> the intake completes. To resume, re-run `PRODUCT-OWNER-INTAKE.md` and say `resume`.

- **Product (working name):** Buyer's Desk
- **Company (working name):** Wholesome Paws — high-end pet food, snacks & toys ("Whole Foods for pets"). Real name not required per client.
- **One-liner:** An internal decision-support system that aggregates Fulfil sales & inventory data into the plans, reports, and reorder/assortment guidance the Buyer needs — automating the Excel work and publishing to SharePoint.

## Intake progress
- **Path:** Fast Track
- **Phases complete:** 0 (seed), 1 (product definition — ratified Checkpoint A), 2 (personas, glossary, contexts — ratified Checkpoint B)
- **Next:** Phase 3 (agent roster → Checkpoint C), Phase 4 (rules → D), Phase 5 (hooks → E), Phase 6 (review + go/no-go)
- **Not yet decided:** agent roster, rules matrix (incl. the PII decision), hooks, output mode.

## Given vs. inferred
- **[given]** (client stated): High-end pet food/snacks/toys retailer. Primary user is the company's Buyer. Money moment = agents + rules that automate data aggregation and display for fast Buyer decisions; manage inventory; decide new orders when sales are high; pull underperforming products; reports are the cornerstone for leadership & buyers. Excel is heavily used. Company uses **Fulfil** (ERP) and saves reports to **SharePoint**.
- **[inferred]** (assumed, to confirm): Leadership as a secondary report-consuming persona; the specific v1 scope IN/OUT list; the success metrics; that the system *recommends* rather than *auto-places* orders (confirmed by client at Checkpoint A); no customer PII involved (to be formally decided in Phase 4).

## Product definition (ratified — Checkpoint A)
- **Problem:** The Buyer makes purchasing, reorder, and keep-or-drop decisions by hand — pulling from Fulfil, crunching in Excel, saving to SharePoint. Slow, manual, insight buried in spreadsheet labor.
- **Target users:** Buyer (primary); Leadership (secondary, report consumer).
- **Core value / money moment:** Automatically aggregate Fulfil sales + inventory into plans, reports, and reorder/assortment guidance — hours of Excel → fast, reliable decisions, saved to SharePoint.
- **In scope (v1):** (1) aggregate sales & inventory from Fulfil into clean datasets; (2) generate core reports (sales performance, low-stock/reorder, slow-movers/overstock) as Excel-compatible output; (3) reorder guidance (what/how much/when by velocity + stock); (4) assortment guidance (flag underperformers to pull); (5) publish reports to SharePoint.
- **Out of scope / non-goals (v1):** no auto-purchasing / auto-spend (human commits every order); no customer-facing storefront, payments, or customer accounts; not replacing Fulfil or SharePoint (integrate only); no ML/statistical forecasting in v1 (start with sales-velocity reorder points).
- **Success metrics:** (1) weekly report set produced in minutes not hours; (2) ≥90% of SKUs crossing a reorder threshold flagged automatically each cycle; (3) slow-mover/overstock list generated every cycle with no manual spreadsheet work; (4) reports auto-published to the correct SharePoint location with consistent formatting; (5) Buyer adoption — acts on generated reports rather than rebuilding in Excel.

## Personas & jobs-to-be-done (ratified — Checkpoint B)
- **Buyer (primary):** When stock is low or an item sells fast, I want an automatic list of what to reorder and how much, so I can order quickly and confidently. When reviewing the range, I want underperformers/overstock flagged, so I can decide what to pull or discount.
- **Leadership (secondary):** When I review performance, I want consistent, current reports in SharePoint, so I can make merchandising/financial calls without waiting on manual spreadsheet work.

## Domain model (ratified — Checkpoint B)
- **Ubiquitous Language:** see `docs/GLOSSARY.md`.
- **Bounded contexts & events:** see `docs/context-map.md`.
- **Summary:** three contexts — **Data Integration** (Fulfil → clean DataSnapshot), **Merchandising Intelligence** (core: velocity, reorder points, reorder/slow-mover/overstock guidance), **Reporting & Publishing** (Excel reports → SharePoint). Events: `SnapshotAggregated` → `RecommendationsReady` → `ReportPublished`.
- **Aggregates (inferred, not ratified):** DataSnapshot; ReorderPlan + AssortmentReview; Report.

## Rules Matrix (ratified)
_Pending — decided in Phase 4 (Checkpoint D). Note: the PII decision is explicitly required and not yet made._

## Hooks (ratified)
_Pending — decided in Phase 5 (Checkpoint E)._

## ADR ledger (draft)
1. Agent boundaries follow bounded contexts (standard). — proposed
2. Data Integration isolated as its own context (Anti-Corruption Layer around Fulfil). — proposed
3. Merchandising Intelligence holds both reorder and assortment logic in one context for v1. — proposed
_(Stack choice, rules calls, and output mode to be added in later phases.)_

## How this was generated
Intake run on 2026-07-19. Path: Fast Track. Output mode: not yet decided. Re-run the intake to revise any phase.
