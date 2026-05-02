# Silver Enriched — Subdirectory Context

> Load `docs/table_reference.md` → Silver Enriched section for full column specs.
> Load `docs/DATA_QUALITY.md` → Gate 2 for full assertion rules.

## What this layer does
Batch jobs that read from Silver Base facts → extract unique entity attributes →
compare with existing dimension → MERGE (insert new version if attributes changed,
close old version). Produces 4 SCD2 dimension tables.

## SCD2 structure (all 4 dims share this)
`surrogate_key` (PK), `business_key` (UK), `effective_from`, `effective_to`
(default: 9999-12-31), `is_current`

## SCD2 trigger columns (when these change → close old row + insert new version)
- `customer_dim`: `segment`, `loyalty_tier`, `city`, `zip`
- `product_dim`: `product_name`, `brand`, `category`
- `store_dim`: `store_type`, `region`, `city`, `state`
- `delivery_partner_dim`: `partner_name`, `partner_type`

## Gate 2 assertions — run BEFORE every MERGE
Bad data in SCD2 tables corrupts historical surrogate key resolution in Gold facts —
crash the job rather than write bad data. Full assertion rules in `docs/DATA_QUALITY.md` → Gate 2.

Quick reference:
- Business key not null
- No duplicate business keys in incoming batch
- Valid enum values (segment, loyalty_tier, store_type, partner_type)
- `zip` = 6 digits

## Generic SCD2 merge — critical rule
One function in `src/transformations/scd2.py` handles all 4 dims.
Do not write per-dim merge logic in notebooks.
Parameterize by: business key column, trigger columns, source table, target table.

## Databricks notes
- MERGE syntax is identical in Databricks — no code changes needed
- Table names will gain catalog prefix: `silver_enriched.X` → `prod_catalog.silver_enriched.X`
- Databricks Workflows will orchestrate these batch jobs with retry policy (3 retries, 5-min delay)