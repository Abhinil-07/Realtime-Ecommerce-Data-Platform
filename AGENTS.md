# Kafka Streaming Medallion Platform — Project Context

## Architecture
Medallion pattern: Landing → Bronze → Silver Base → Silver Enriched → Gold RT → Gold Batch

- **Landing**: Raw bytes from Confluent Kafka (replay buffer)
- **Bronze**: Append-only JSON + Kafka metadata (immutable history)
- **Silver Base**: Typed columns + inline DLQ — streams NEVER fail, bad data is routed not dropped
- **Silver Enriched**: Delta CDF + MERGE for SCD2 dimensions (batch)
- **Gold RT**: Streaming KPIs with 5-min tumbling windows + watermarking
- **Gold Batch**: Nightly star schema with ROW_NUMBER() dedup

## Stack
- Apache Spark Structured Streaming (local Docker cluster)
- Delta Lake with Change Data Feed (CDF) enabled
- Confluent Kafka (cloud-managed)
- JupyterLab notebooks + modular `src/` Python modules
- Docker Compose (Spark Master + Worker 8-core/8GB + Jupyter)

## Future Target: Databricks on Azure
This project will migrate to Databricks. When writing any code, prefer patterns that are
Databricks-compatible. See `docs/DATABRICKS_MIGRATION.md` for the full migration plan.
Key differences to keep in mind:
- Paths will change: `/opt/spark-data/` → `abfss://container@storage.dfs.core.windows.net/`
- Secrets will change: hardcoded .env → Databricks Secrets / Azure Key Vault
- Table naming will change: 2-level → 3-level Unity Catalog (`catalog.schema.table`)
- SparkSession will be auto-provided by Databricks (no manual creation needed)

## Table Inventory (27 tables — full schemas in `docs/table_reference.md`)

| Layer           | Tables | Type |
|----------------|--------|------|
| Landing         | `raw_events` | Streaming |
| Bronze          | `orders_raw` | Streaming |
| Silver Base     | `order_fact_RT`, `order_event_fact_RT`, `order_item_fact_RT`, `payment_attempt_fact_RT`, `delivery_fact_RT`, `discount_fact_RT` | Streaming |
| Silver Enriched | `customer_dim`, `product_dim`, `store_dim`, `delivery_partner_dim` | Batch SCD2 |
| Gold Curated    | `dim_customer`, `dim_product`, `dim_store`, `dim_delivery_partner`, `dim_date`, `fact_orders`, `fact_order_items` | Batch |
| Gold RT         | `sales_summary_RT`, `category_sales_metrics_RT`, `payment_usage_metrics_RT`, `order_lifecycle_metrics_RT` | Streaming |
| Gold Batch      | `sales_summary`, `category_sales_metrics`, `discount_effectiveness`, `delivery_partner_metrics` | Batch |

A potential 28th table (`gold_delivery_status_RT`) exists as an option if live BI joins on
`delivery_fact_RT` + `delivery_partner_dim` prove too slow. See `docs/table_reference.md`.

## Non-Negotiable Design Rules
- Silver Base tables use BUSINESS KEYS only — never surrogate keys
- SCD2 dims always have: `surrogate_key`, `effective_from`, `effective_to`, `is_current`
- Gold fact surrogate keys are FROZEN at event time via time-range join — never re-computed
- Gold RT tables use 5-min tumbling windows + `withWatermark("event_time", "30 minutes")`
- `silver_order_item_fact_RT` denormalizes product attrs intentionally (streaming can't wait for dims)
- `silver_discount_fact_RT` requires a double-explode: `items[]` → `discounts[]`
- `gold_dim_date` is static — generated once, never updated by streams
- Bronze is append-only — never overwrite or delete records
- DLQ tables must be initialized BEFORE any stream is started
- Delta CDF must be enabled on Bronze BEFORE Silver Enriched runs

## Data Quality Gates (4-gate strategy — full spec in `docs/DATA_QUALITY.md`)
- **Gate 0**: Schema Registry (Kafka) — blocks structural corruption before ingest
- **Gate 1**: DLQ at Silver Base (Streaming) — null PKs, business rules, format rules
- **Gate 2**: Assertions at Silver Enriched (Batch) — validates before MERGE (crash > corrupt)
- **Gate 3**: DLQ at Gold RT (Streaming) — dedup + watermark + good/bad split
- **Gate 4**: Assertions at Gold Batch (Batch) — ROW_NUMBER dedup + validation before star schema write

## Environment
```bash
docker-compose down && docker-compose up -d --build
# JupyterLab: http://localhost:8888/lab
# Spark Master UI: http://localhost:8080
# Spark Session UI: http://localhost:4040
```

## Execution Order
Landing.ipynb → Bronze → Silver Base → Silver Enriched → Gold RT → Gold Batch

## Project Layout
```
src/
  transformations/   # Pure transformation functions (no Spark session here)
  utils/             # Shared utilities (schema helpers, DLQ writers, etc.)
  io/                # Kafka config, Delta read/write abstractions
  tests/             # pytest unit tests (mirrors src/ structure)
notebooks/
  landing/
  bronze/
  silver/
  gold/
docs/
  table_reference.md      # Full 27-table schema reference (load on demand)
  DATABRICKS_MIGRATION.md # Full migration plan (load on demand)
.env                      # NEVER commit — holds Kafka API keys
PROGRESS.md               # Session handoff tracker — read this every session
```

## Code Rules
- Notebooks are thin orchestrators — business logic lives in `src/`
- All reusable Spark transforms go in `src/transformations/`
- SCD2 merge function must be generic and reusable across all 4 dims
- Type hints and docstrings on every public function
- Use Python `logging` module — never `print()`
- Log format: JSON with `job_name`, `version`, `row_count` in every entry
- NEVER hardcode secrets, paths, or table names — use config/environment

## Session Protocol
**Start of every session:**
1. Read `PROGRESS.md` — know what's done and what's next
2. Load `docs/table_reference.md` ONLY if the task involves schema, columns, or joins
3. Load `docs/DATABRICKS_MIGRATION.md` ONLY if the task involves infrastructure or migration

**End of every session** — update `PROGRESS.md`:
- Mark completed items with ✅ and today's date
- Note any schema changes (table name + what changed)
- Write the exact next step (specific file and line, not just "continue Silver")
- Note any Databricks migration decisions made this session