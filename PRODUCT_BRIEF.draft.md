# Buyer's Desk — Decision Record & Audit Trail (DRAFT)

> **This is a mid-intake draft**, saved via `save draft` on 2026-07-19 so the DDD work survives a
> long session. It is NOT the final brief. The full product story will live in `docs/PRD.md` once
> the intake completes. To resume, re-run `PRODUCT-OWNER-INTAKE.md` and say `resume`.

- **Product (working name):** Buyer's Desk
- **Company (working name):** Wholesome Paws — high-end pet food, snacks & toys ("Whole Foods for pets"). Real name not required per client.
- **One-liner:** An internal decision-support system that aggregates Fulfil sales & inventory data into the plans, reports, and reorder/assortment guidance the Buyer needs — automating the Excel work and publishing to SharePoint.

## Intake progress
- **Path:** Fast Track
- **Phases complete:** 0 (seed), 1 (product definition — ratified Checkpoint A), 2 (personas, glossary, contexts — ratified Checkpoint B), 3 (agent roster — ratified Checkpoint C)
- **In progress:** Phase 4 (rules → Checkpoint D) — proposed matrix below, awaiting ratification incl. the PII call.
- **Next:** Phase 5 (hooks → E), Phase 6 (review + go/no-go), then generation.
- **Not yet decided:** rules matrix (incl. final PII decision), hooks, output mode (A stamp-in-place vs B publish plugin).

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

## Agent roster (ratified — Checkpoint C)
Six agents: three domain (one per bounded context) + three read-only cross-cutting.

| Agent | Context | Mission | Owns | Invoke when | Tools | Model | Autonomy |
|---|---|---|---|---|---|---|---|
| data-integrator | Data Integration | Pull & validate Fulfil data into a clean DataSnapshot | DataSnapshot | New data cycle / Fulfil refresh | Read, Write, Edit, Bash, Glob, Grep | sonnet | ask (external + creds) |
| merchandising-analyst | Merchandising Intelligence (core) | Compute velocity/reorder points; reorder, slow-mover & overstock guidance | ReorderPlan, AssortmentReview | SnapshotAggregated | Read, Write, Edit, Bash, Glob, Grep | opus | free (internal) |
| report-publisher | Reporting & Publishing | Build Excel reports & publish to SharePoint | Report | RecommendationsReady | Read, Write, Edit, Bash, Glob | sonnet | ask (outward publish) |
| test-engineer | cross-cutting | Write/run tests; guard aggregation & calc correctness | test suite | After any logic change | Read, Write, Edit, Bash, Glob, Grep | sonnet | free |
| code-reviewer | cross-cutting | Review diffs for correctness/clarity/convention | (read-only) | Before merge | Read, Grep, Glob, Bash | sonnet | read-only |
| security-compliance-reviewer | cross-cutting | Enforce rules; check secret/credential handling for Fulfil & SharePoint | (read-only) | Creds/external/data changes | Read, Grep, Glob, Bash, WebSearch | opus | read-only |

Hand-offs (PO-routed, no agent-to-agent calls): `SnapshotAggregated` → merchandising-analyst; `RecommendationsReady` → report-publisher; `ReportPublished` → Buyer/PO. Code changes → test-engineer + code-reviewer (+ security-compliance-reviewer when creds/external/data touched).

## Rules Matrix (PROPOSED — Checkpoint D pending, not yet ratified)
Recommendation: all eight ON. `legal-compliance` flagged as the one defensibly switchable OFF; `no-pii` recommended ON because Fulfil (the data source) holds customer PII even though the product deliberately avoids it.

| Rule | Proposed | Severity | Binds | Note |
|---|---|---|---|---|
| no-pii | ON | Critical/MUST | global | Aggregate at source; never pull/store/log customer-level PII from Fulfil. |
| security-secrets | ON | Critical/MUST | global | Fulfil API keys + SharePoint auth via env/secrets only. |
| destructive-actions | ON | Critical/MUST | agents w/ Bash | No rm -rf / overwrite / force-ops without approval. |
| human-in-the-loop | ON | High/MUST | report-publisher + outward | SharePoint publish + any order action human-gated. |
| external-services | ON | High/MUST | data-integrator, report-publisher | Read-only default vs Fulfil; SharePoint writes gated. |
| legal-compliance | ON (optional) | High/SHOULD | global | Dependency licensing + personal-data retention. Candidate for OFF. |
| code-quality-testing | ON | Medium/MUST | code-writing agents | Build/lint/tests pass; bug fix needs failing→passing test. |
| scope-discipline | ON | Medium/MUST | all subagents | Stay in lane; hand off through PO. |

## Hooks (ratified)
_Pending — decided in Phase 5 (Checkpoint E)._

## ADR ledger (draft)
1. Agent boundaries follow bounded contexts (one agent per context). — accepted at Checkpoint C
2. Data Integration isolated as its own context (Anti-Corruption Layer around Fulfil). — accepted at Checkpoint C
3. Merchandising Intelligence holds both reorder and assortment logic in one context for v1. — accepted at Checkpoint C
_(Stack choice, any contested rule call — e.g. legal-compliance OFF — and output mode to be added in Phases 4–6.)_

## How this was generated
Intake run on 2026-07-19. Path: Fast Track. Output mode: not yet decided. Re-run the intake to revise any phase.
