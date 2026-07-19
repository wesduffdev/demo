# data/samples/

Local sample data for Buyer's Desk.

> ⚠️ **Real / confidential business data in this folder is git-ignored and must never be
> committed or pushed.** See `.claude/rules/no-pii.md`, `.claude/rules/security-secrets.md`, and
> `docs/adr/0003`. Only synthetic, clearly-fake fixtures should ever be committed.

**Git-ignored here:** `*.xlsx`, `*.xls`, `*.xlsm`, `*.csv`, `*.parquet` (this `README.md` is the
only tracked file in the folder).

## Files (local only — not in git)
- `WAR_Executive_Overview_6.29.26.xlsx` — executive overview report (2026-06-29). 7 sheets:
  Executive Summary, Store Inventory & Turn, Sales & Margin, Replenishment, TURN, Sales, DC trucks.
  Contains real company financials (inventory value, net sales, margin %, inventory turn by store).
  PII scan: clean. Kept **local only** as a reference for the report format `report-publisher`
  produces and the data shape `merchandising-analyst` reasons over.
