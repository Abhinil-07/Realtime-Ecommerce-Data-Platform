# Pipeline Progress Tracker

> **How to use**: Claude reads this at the start of every session. Update it at the end of every session before /clear.

---

## Medallion Layer Build Status

| # | Layer | Table | Type | Status | Notes |
|---|---|---|---|---|---|
| 1 | Landing | `raw_events` | Streaming | ✅ Done | `src/streaming/landing.py` |
| 2 | Bronze | `orders_raw` | Streaming | ✅ Done | `notebooks/bronze.ipynb` |
| 3 | Silver Base | `order_fact_RT` | Streaming | ✅ Done | `notebooks/silver_base/order_fact_RT.ipynb` |
| 4 | Silver Base | `order_event_fact_RT` | Streaming | ✅ Done | `notebooks/silver_base/order_event_fact_RT.ipynb` |
| 5 | Silver Base | `order_item_fact_RT` | Streaming | ✅ Done | `notebooks/silver_base/order_item_fact_RT.ipynb` |
| 6 | Silver Base | `payment_attempt_fact_RT` | Streaming | ✅ Done | `notebooks/silver_base/payment_attempt_fact_RT.ipynb` |
| 7 | Silver Base | `delivery_fact_RT` | Streaming | ✅ Done | `notebooks/silver_base/delivery_fact_RT.ipynb` |
| 8 | Silver Base | `discount_fact_RT` | Streaming | ✅ Done | `notebooks/silver_base/discount_fact_RT.ipynb` |
| 9 | Silver Enriched | `customer_dim` | Batch SCD2 | ✅ Done | `notebooks/silver_enriched/customer_dim.ipynb` |
| 10 | Silver Enriched | `product_dim` | Batch SCD2 | ✅ Done | `notebooks/silver_enriched/product_dim.ipynb` |
| 11 | Silver Enriched | `store_dim` | Batch SCD2 | ✅ Done | `notebooks/silver_enriched/store_dim.ipynb` |
| 12 | Silver Enriched | `delivery_partner_dim` | Batch SCD2 | ✅ Done | `notebooks/silver_enriched/delivery_partner_dim.ipynb` |
| 13 | Gold Curated | `dim_customer` | Batch | ⬜ Not Started | |
| 14 | Gold Curated | `dim_product` | Batch | ⬜ Not Started | |
| 15 | Gold Curated | `dim_store` | Batch | ⬜ Not Started | |
| 16 | Gold Curated | `dim_delivery_partner` | Batch | ⬜ Not Started | |
| 17 | Gold Curated | `dim_date` | Static | ⬜ Not Started | |
| 18 | Gold Curated | `fact_orders` | Batch | ⬜ Not Started | Time-range join |
| 19 | Gold Curated | `fact_order_items` | Batch | ⬜ Not Started | Time-range join |
| 20 | Gold RT | `sales_summary_RT` | Streaming | ⬜ Not Started | |
| 21 | Gold RT | `category_sales_metrics_RT` | Streaming | ⬜ Not Started | |
| 22 | Gold RT | `payment_usage_metrics_RT` | Streaming | ⬜ Not Started | |
| 23 | Gold RT | `order_lifecycle_metrics_RT` | Streaming | ⬜ Not Started | |
| 24 | Gold Batch | `sales_summary` | Batch | ⬜ Not Started | |
| 25 | Gold Batch | `category_sales_metrics` | Batch | ⬜ Not Started | |
| 26 | Gold Batch | `discount_effectiveness` | Batch | ⬜ Not Started | |
| 27 | Gold Batch | `delivery_partner_metrics` | Batch | ⬜ Not Started | |

**Status key**: ⬜ Unknown | 🔄 In Progress | ✅ Done | ❌ Blocked

> **First session task**: Run `find . -name "*.py" -o -name "*.ipynb" | head -40` and update statuses above.

---

## Cross-Cutting Feature Checklist

### Code Quality (Section B)
- [ ] Refactor all notebooks into thin orchestrators
- [ ] Extract transformation logic into `src/transformations/*.py`
- [ ] Make SCD2 merge function generic (reusable across all 4 dims)
- [ ] Move shared utilities to `src/utils/*.py`

### Testing (Section C)
- [ ] Create `tests/` directory with pytest
- [ ] Unit tests for each transformation function (parse, deduplicate, merge)
- [ ] Edge case tests: null fields, duplicates, schema changes, empty batches

### DLQ Coverage (Section F) — streams NEVER fail
- [ ] Landing stream DLQ
- [ ] Bronze stream DLQ
- [ ] Silver Base: `order_fact_RT` DLQ
- [ ] Silver Base: `order_event_fact_RT` DLQ
- [ ] Silver Base: `order_item_fact_RT` DLQ
- [ ] Silver Base: `payment_attempt_fact_RT` DLQ
- [ ] Silver Base: `delivery_fact_RT` DLQ
- [ ] Silver Base: `discount_fact_RT` DLQ
- [ ] Gold RT: `sales_summary_RT` DLQ
- [ ] Gold RT: `category_sales_metrics_RT` DLQ
- [ ] Gold RT: `payment_usage_metrics_RT` DLQ
- [ ] Gold RT: `order_lifecycle_metrics_RT` DLQ

### Data Quality Assertions (Section G)
- [ ] Null checks on primary keys at every layer
- [ ] Business rule checks (price > 0, quantity > 0, valid payment methods)
- [ ] Format-level checks (zip = 6 digits, phone = 10 digits)
- [ ] Schema validation before MERGE operations

### Duplicate Detection (Section H)
- [ ] `gold_fact_orders`: ROW_NUMBER dedup on `order_id`
- [ ] `gold_fact_order_items`: ROW_NUMBER dedup on `item_id`
- [ ] Gold RT: `dropDuplicatesWithinWatermark` on business keys

### Watermarking (Section I — Gold RT only)
- [ ] `gold_sales_summary_RT`: `withWatermark("event_time", "30 minutes")`
- [ ] `gold_category_sales_metrics_RT`: `withWatermark`
- [ ] `gold_payment_usage_metrics_RT`: `withWatermark`
- [ ] `gold_order_lifecycle_metrics_RT`: `withWatermark`

### Monitoring (Section J)
- [ ] Data freshness job: check `MAX(ingest_ts)` at each layer every 5 mins
- [ ] Pipeline SLA threshold: alert if any layer is >5 minutes stale
- [ ] Row count reconciliation: Landing = Bronze = Silver good + Silver DLQ

### Performance (Section M)
- [ ] Partition large tables by date or `store_id`
- [ ] Z-Order frequently queried columns (`OPTIMIZE table ZORDER BY col`)
- [ ] Schedule VACUUM to clean up old Delta file versions
- [ ] Enable auto compaction (small file problem from streaming appends)

### Logging (Section O)
- [ ] Replace all `print()` with Python `logging` module
- [ ] Include `job_name`, `version`, `row_count` in every log entry
- [ ] JSON log format for log analytics

### Databricks Migration (Section D + E + N — see `docs/DATABRICKS_MIGRATION.md`)
- [ ] Abstract paths into config
- [ ] Abstract secrets into `src/utils/secrets.py`
- [ ] Abstract table names into config dict
- [ ] Wrap SparkSession in `src/utils/spark.py`
- [ ] Databricks Workflows for batch jobs
- [ ] Job dependency chain + retry policies + failure alerts
- [ ] Unity Catalog PII masking + access control + lineage

---

## Last Session Summary

**Date**: 2026-05-02
**What was completed**: 
- Conducted architecture review on Medallion layering, Surrogate Key (SCD2) generation, and Time-Range Joins for frozen facts.
- Brainstormed the split between `silver_customer_dim` and `gold_dim_customer`.
- Audited the codebase and updated Medallion Layer Build Status (Landing through Silver Enriched are implemented).
- Evaluated Great Expectations for data quality. Decided against it due to streaming latency (Gates 1 & 3) and the future Databricks migration path.
**Open issues / blockers**: None.
**Exact next step**: Begin implementation of the Gold Curated Layer (specifically resolving frozen surrogate keys in fact tables).
**Databricks decisions made**: 
- Re-affirmed that `row_number()` will be used instead of `monotonically_increasing_id()` for SK generation to ensure Databricks/Delta compatibility.
- Decided against Great Expectations in favor of native Databricks Delta Live Tables (DLT) Expectations during migration to avoid 3rd-party overhead and streaming complexity.

---

## Schema Change Log
_Record any column additions, renames, or type changes made during development._

| Date | Table | Change | Reason |
|---|---|---|---|
| — | — | — | — |