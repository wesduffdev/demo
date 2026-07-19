# Buyer's Desk — Decision Record & Audit Trail (DRAFT)

> **This is a mid-intake draft**, saved via `save draft` on 2026-07-19 so the DDD work survives a
> long session. It is NOT the final brief. The full product story will live in `docs/PRD.md` once
> the intake completes. To resume, re-run `PRODUCT-OWNER-INTAKE.md` and say `resume`.

- **Product (working name):** Buyer's Desk
- **Company (working name):** Wholesome Paws — high-end pet food, snacks & toys ("Whole Foods for pets"). Real name not required per client.
- **One-liner:** An internal decision-support system that aggregates Fulfil sales & inventory data into the plans, reports, and reorder/assortment guidance the Buyer needs — automating the Excel work and publishing to SharePoint.

## Intake progress
- **Path:** Fast Track
- **Phases complete:** 0 (seed), 1 (Checkpoint A), 2 (Checkpoint B), 3 roster (Checkpoint C), 4 rules incl. PII=ON (Checkpoint D), 5 hooks (Checkpoint E), 6 ADR ledger (Checkpoint F) + output mode.
- **Output mode:** A — stamp in place (write setup into this repo; no plugin/Phase 8).
- **Next:** Phase 7 generation — **awaiting explicit `go`**. Nothing final written yet.
- **All decisions ratified.** Remaining action is generation on `go`.

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

## Rules Matrix (RATIFIED — Checkpoint D)
All eight ON. **PII = ON confirmed** because Fulfil (the data source) holds customer PII even though the product deliberately avoids it. `legal-compliance` kept ON (was the one candidate for OFF). No rules switched OFF.

| Rule | On/Off | Severity | Binds | Note |
|---|---|---|---|---|
| no-pii | ON | Critical/MUST | global | Aggregate at source; never pull/store/log customer-level PII from Fulfil. |
| security-secrets | ON | Critical/MUST | global | Fulfil API keys + SharePoint auth via env/secrets only. |
| destructive-actions | ON | Critical/MUST | agents w/ Bash | No rm -rf / overwrite / force-ops without approval. |
| human-in-the-loop | ON | High/MUST | report-publisher + outward | SharePoint publish + any order action human-gated. |
| external-services | ON | High/MUST | data-integrator, report-publisher | Read-only default vs Fulfil; SharePoint writes gated. |
| legal-compliance | ON | High/SHOULD | global | Dependency licensing + personal-data retention. |
| code-quality-testing | ON | Medium/MUST | code-writing agents | Build/lint/tests pass; bug fix needs failing→passing test. |
| scope-discipline | ON | Medium/MUST | all subagents | Stay in lane; hand off through PO. |

## Hooks (ratified — Checkpoint E)
Four accepted (jq present, so they enforce):
- **guard-secret-files** (PreToolUse `Edit|Write`) — hard-blocks writes to `.env`/`*.pem`/keys/credential files. Enforces security-secrets.
- **guard-dangerous-commands** (PreToolUse `Bash`) — hard-blocks `rm -rf`, force-push, `git reset --hard`, `DROP`/`TRUNCATE`, `curl … | sh`. Enforces destructive-actions.
- **guard-no-pii** (PreToolUse `Bash|WebFetch`) — scans OUTBOUND actions only for PII; allowlists synthetic test ranges. Enforces no-pii.
- **session-context** (SessionStart) — prints product summary, agent list, git status into each new session.

Deferred: format-file, inject-context, run-affected-tests (add once the stack stabilizes).

## ADR ledger (ratified — Checkpoint F)
- **0000** Record significant decisions as ADRs (seed). — Accepted
- **0001** Agent boundaries follow bounded contexts (one agent per context); Data Integration isolated behind an anti-corruption layer around Fulfil; Merchandising keeps reorder + assortment together for v1. — Accepted
- **0002** Tech stack: Python pipeline; file-based snapshots (CSV/Parquet), no database in v1 (Fulfil is system of record); openpyxl for Excel; Fulfil REST API + Microsoft Graph for SharePoint. — Accepted
- **0003** Promote security-secrets, destructive-actions, no-pii from guidance to hard-hook enforcement. — Accepted
- **0004** Output mode A — stamp in place (no plugin/marketplace). — Accepted

No contested rule-OFF ADR needed: all rules kept ON.

## How this was generated
Intake run on 2026-07-19. Path: Fast Track. Output mode: A (stamp in place). Re-run the intake to revise any phase.
