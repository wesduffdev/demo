# Buyer's Desk

Internal decision-support for the **Buyer**. Buyer's Desk aggregates **Fulfil** sales &
inventory data into the reorder / assortment guidance and reports the Buyer needs — automating
the Excel work and (when connected) publishing to **SharePoint**.

> **The system recommends; the human Buyer commits every order.** No auto-purchasing, no
> auto-publish. See [`CLAUDE.md`](CLAUDE.md) and [`docs/PRD.md`](docs/PRD.md) for the full product
> definition, and [`plans/PRD-WAR-Automation.md`](plans/PRD-WAR-Automation.md) for the Weekly
> Analysis Report (WAR) automation ("Bob").

---

## Current status (v1)

The boundary building blocks are in place — config/credential loading, a **read-only** Fulfil
client, sales & inventory staging pulls, the Excel workbook engine, and the human-gated SharePoint
publisher. A **mock report command** (`make mock-report`) generates output from the local sample
data today; the full live `pull → snapshot → analyze → report → publish` cycle and unattended
scheduling are still on the roadmap (see [Roadmap](#roadmap)).

**v1 runs on mock / local data — no live Fulfil pulls or real credentials are required to work in
this repo.** The mock dataset is the sample WAR workbook,
`data/samples/WAR_Executive_Overview_6.29.26.xlsx` — see [Mock / local mode](#mode-a--mock--local-default)
below, which is the default. [Automatic / live mode](#mode-b--automatic--live) is how it runs once
real Fulfil & SharePoint credentials are supplied.

---

## Prerequisites

- **Python ≥ 3.11**
- `make` (the targets below wrap the venv + tooling)

## Setup

```bash
make install      # create .venv and install the package (editable) + dev deps
```

`make help` lists every target. The common ones:

| Target | What it does |
|---|---|
| `make install` | Create `.venv`, install the package + dev deps |
| `make mock-report` | Generate a report from the local mock data → `./output/` |
| `make test` | Run the pytest suite |
| `make lint` | `ruff check` |
| `make format` | Apply `ruff format` |
| `make ci` | Full gate: lint + format-check + test (what CI runs) |
| `make clean` | Remove the venv and build/test artifacts |

---

## Mode A — Mock / local (default)

Runs against the **local sample data with no live credentials or Fulfil connection**. The mock
dataset is the sample WAR workbook — the canonical reference the pipeline is built against.

### 1. Point the mock at the sample WAR workbook

The mock data source is:

```
data/samples/WAR_Executive_Overview_6.29.26.xlsx
```

This is the hand-built Weekly Analysis Report for the week of 6/29/26 — the canonical output format
and the source of every example figure in [`plans/PRD-WAR-Automation.md`](plans/PRD-WAR-Automation.md).
It has 7 sheets: `Executive Summary`, `Store Inventory & Turn`, `Sales & Margin`, `Replenishment`,
`TURN`, `Sales`, `DC trucks`.

> ⚠️ **The file is local-only and git-ignored — a fresh clone will not include it.** It holds real
> company financials (PII-clean, but confidential), so **keep it local, never commit it, and never
> paste its figures** into code, logs, issues, or commits. Obtain the workbook and place it at the
> path above before running Mode A. See [`data/samples/README.md`](data/samples/README.md) and
> [`.claude/rules/no-pii.md`](.claude/rules/no-pii.md).

### 2. Generate the output

One command reads the mock workbook and writes a formatted, Excel-openable report to `./output/`:

```bash
make mock-report
# -> wrote output/WAR_<today>.xlsx
```

Equivalently, with options:

```bash
python -m buyers_desk.mock_report \
    --source data/samples/WAR_Executive_Overview_6.29.26.xlsx \
    --output-dir output \
    --report-date 2026-06-29        # optional; defaults to today (UTC)
```

| Flag | Default | Meaning |
|---|---|---|
| `--source` | `data/samples/WAR_Executive_Overview_6.29.26.xlsx` | Mock workbook to render |
| `--output-dir` | `output` | Folder to write into (created if missing) |
| `--report-date` | today (UTC) | Date used in the `WAR_<date>.xlsx` filename / report id |

The command renders every sheet of the mock workbook faithfully through the shared report engine
(`data_only=True`, so computed values are read, not formulas) — it does **not** yet compute KPIs,
flags, or recommendations. That analysis (`aggregate → analyze → report`, BD-011+ / BD-022) is the
roadmap wiring; today this exercises the full `mock data → Report → .xlsx` path with no credentials
and no network. If the source file is missing (a fresh clone won't have it), the command exits with
a clear message instead of a traceback.

> The generated file lands in `./output/`, which is git-ignored — a mock render carries the source's
> real figures, so **never commit it or paste its values**.

To inspect the source directly instead of rendering it, load it with openpyxl (already a
dependency):

```python
from openpyxl import load_workbook

wb = load_workbook("data/samples/WAR_Executive_Overview_6.29.26.xlsx", read_only=True, data_only=True)
print(wb.sheetnames)
# ['Executive Summary', 'Store Inventory & Turn', 'Sales & Margin',
#  'Replenishment', 'TURN', 'Sales', 'DC trucks']
wb.close()
```

### 3. Run the correctness suite (no data file needed)

```bash
make test
```

The tests drive every module on **synthetic, clearly-fake fixtures** — the Fulfil client and the
SharePoint publisher are mocked, so no network call, no credentials, and **not** the local WAR file
are needed (the suite is fully self-contained and CI-safe). This is the fastest way to see the
staging, reporting, and publish-path logic run end to end.

> The staging pulls (`pull_sales_rows` / `pull_inventory_rows`) take an **injected client**, so a
> fake can feed records in place of a live Fulfil connection — see `tests/test_sales_staging.py`
> for the pattern.

---

## Mode B — Automatic / live

How Buyer's Desk runs against **real Fulfil & SharePoint** — an on-command cycle that pulls the
latest data, produces the reports, and (only after human approval) publishes them.

### 1. Provide credentials

Credentials come from the **environment only** — never hardcoded, never committed. Copy the
template and fill in real values in the git-ignored `.env`:

```bash
cp .env.example .env
# then edit .env — Fulfil (FULFIL_API_KEY, FULFIL_SUBDOMAIN) and
# SharePoint (SHAREPOINT_TENANT_ID / _CLIENT_ID / _CLIENT_SECRET / _SITE_ID)
```

Load those into your process environment however your shell / CI / secrets manager does it (there's
no `.env` parser dependency — `buyers_desk/config.py` reads `os.environ`). A missing required
variable fails fast, naming the variable but **never** printing its value.

### 2. Confirm connectivity (read-only)

```python
from buyers_desk.data_integration.fulfil_client import FulfilClient

client = FulfilClient.from_env()   # reads FULFIL_* from the environment
client.ping()                      # read-only health check against Fulfil → True
```

The Fulfil client is **read-only by construction** (GET only; no create/update/delete). Point it at
a sandbox with `FULFIL_BASE_URL` before using live production credentials.

### 3. Run the cycle

The full **pull → snapshot → analyze → report → publish** cycle is driven by the orchestrator
("Bob") described in [`plans/PRD-WAR-Automation.md`](plans/PRD-WAR-Automation.md). The single
one-command entry point (ticket **BD-022**) is still being built (see [Roadmap](#roadmap)); today
the boundary steps above run individually, wired together by the orchestrator.

> **Publishing is human-gated and never automatic.** `SharePointPublisher.stage_upload()` prepares
> a preview (target location + payload) with **no** network call; `publish()` only sends when
> called with an explicit `approved=True` — otherwise it refuses and sends nothing. See
> [`.claude/rules/human-in-the-loop.md`](.claude/rules/human-in-the-loop.md).

---

## Where things land

| Path | Contents | Tracked in git? |
|---|---|---|
| `output/` | Generated `.xlsx` reports (e.g. `WAR_<report-date>.xlsx`) | ❌ git-ignored (real financials) |
| `data/samples/` | Local sample/reference data | ❌ data files git-ignored (only the README is tracked) |
| `logs/` | Orchestrator run logs (metadata only — no secrets/PII) | ✅ checked in |

## Safety & rules

- **No customer PII** ever enters a dataset, log, report, or commit — data is aggregated at the
  product level.
- **Secrets** live in the environment / a secrets manager only; `.env`, `*.pem`, and credential
  files are git-ignored and never printed or logged.
- **Human-in-the-loop** for anything outward-facing: SharePoint publish and any order action are
  human-gated. The system recommends; it never spends or auto-publishes.

Full rule set: [`.claude/rules/`](.claude/rules/). Product & agent orchestration model:
[`CLAUDE.md`](CLAUDE.md).

## Contributing

The default branch is PR-only — work on a feature branch and open a PR. CI runs
`ruff check` + `ruff format --check` + `pytest` on every PR (`make ci` is the local equivalent).
See [`.claude/rules/code-quality-testing.md`](.claude/rules/code-quality-testing.md).

## Roadmap

Post-v1, from [`plans/PRD-WAR-Automation.md`](plans/PRD-WAR-Automation.md) §9 and
[`plans/wave-plan.yml`](plans/wave-plan.yml):

1. **One-command end-to-end cycle** (BD-022) — a single entry point for pull → snapshot → analyze →
   report → (human-approved) publish.
2. **Scheduled automation** — run unattended on a Sunday-night cadence (cloud scheduled agent / cron
   / GitHub Actions) producing a Monday-dated report.
3. **Real delivery** — publish to a permissioned SharePoint location and/or notify by email.
</content>
</invoke>
