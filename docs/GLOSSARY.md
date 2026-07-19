# Ubiquitous Language — Glossary

> Single source of truth for what our words mean. If code, docs, or an agent uses a term below,
> it means exactly this. Add a row before you add the concept.
>
> **Status: DRAFT** — ratified at intake Checkpoint B (2026-07-19). The "Owning Agent" column is
> *proposed* and becomes authoritative only after the roster is ratified at Checkpoint C.

| Term | Definition (1–2 sentences, plain language) | Bounded Context | Owning Agent (proposed) |
|------|--------------------------------------------|-----------------|-------------------------|
| Product | A tracked item we carry — food, snack, or toy — identified by a SKU. | (shared) | — |
| DataSnapshot | One clean, aggregated pull of sales + inventory from Fulfil at a point in time; everything downstream is computed from it. | Data Integration | data-integrator |
| InventoryLevel | On-hand quantity of a Product right now. | Data Integration | data-integrator |
| SalesVelocity | How fast a Product is selling over a period (e.g. units/week). | Merchandising Intelligence | merchandising-analyst |
| ReorderPoint | The stock level at which a Product should be reordered. | Merchandising Intelligence | merchandising-analyst |
| ReorderSuggestion | A recommendation to buy N units of a Product from a Supplier — advisory, never auto-placed. | Merchandising Intelligence | merchandising-analyst |
| SlowMover | A Product selling below a performance bar; a candidate to pull or discount. | Merchandising Intelligence | merchandising-analyst |
| Overstock | Stock well above expected demand for the period. | Merchandising Intelligence | merchandising-analyst |
| Assortment | The set of Products we currently carry. | Merchandising Intelligence | merchandising-analyst |
| Supplier | A vendor we buy Products from. | (shared) | — |
| Report | A generated, Excel-compatible artifact for the Buyer or Leadership. | Reporting & Publishing | report-publisher |
| Fulfil | The ERP that is the system of record for sales & inventory (our data source). | Data Integration | data-integrator |
| SharePoint | Where finished Reports are published. | Reporting & Publishing | report-publisher |
