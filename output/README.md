# output/

Delivery target for generated reports. Bob (the orchestrator) writes the finished WAR workbook
here — see `plans/PRD-WAR-Automation.md`.

> ⚠️ **Everything in this folder is git-ignored** (except this `README.md`). Generated reports
> contain real company financials and must never be committed or pushed. See `.gitignore`,
> `.claude/rules/no-pii.md`, and `docs/adr/0003`.

Example output: `WAR_<report-date>.xlsx` (e.g. `WAR_2026-06-29.xlsx`).
