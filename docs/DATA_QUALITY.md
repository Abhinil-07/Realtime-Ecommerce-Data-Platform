# Data Quality Gate Strategy

> **Load this file** when working on: DLQ logic, assertion checks, validation rules,
> monitoring jobs, or anything touching good/bad data routing.

---

## Core Philosophy

**Two failure modes, two responses:**

| Situation | Response | Why |
|---|---|---|
| Streaming layer receives bad data | Route to DLQ, never stop the stream | Stopping a stream loses Kafka offsets and breaks downstream consumers |
| Batch layer receives bad data | Crash the job, leave the table untouched | A bad MERGE into SCD2 history is extremely hard to undo — better to fix and rerun |

**The self-healing guarantee**: When upstream resends corrected data, it flows through the
same pipeline. Good data lands in Silver/Gold. DLQ tables drain naturally. Dashboards heal
without manual intervention.

---

## Gate 0 — Schema Registry (Kafka, pre-ingest)

**Where**: Confluent Schema Registry, before data enters the pipeline
**Type**: Preventive — blocks structural corruption at the source

**What it catches**:
- Removed required fields
- Type changes (string → int)
- Broken JSON structure
- Missing root-level fields (`source_system`, `ingestion_time`)

**What it does NOT catch**:
- Null values in valid fields
- Invalid business values (negative prices, unknown payment methods)
- Format violations (wrong zip length, wrong phone length)

**Owned by**: Kafka/Confluent config — not Spark code

---

## Gate 1 — DLQ at Silver Base (Streaming)

**Where**: Every Silver Base streaming write
**Type**: Reactive routing — splits each micro-batch into good + bad before writing

**Implementation**: DLQ logic must be modular — `src/utils/dlq.py` owns the good/bad split
so notebooks never implement it inline. Claude Code is responsible for designing and
implementing that module.

**Conceptual pattern** (for reference — actual implementation owned by Claude Code):
```python
good_df = df.filter(validation_condition)
bad_df  = df.filter(~validation_condition) \
             .withColumn("rejection_reason", lit("..."))

good_df.writeStream → silver_base.{table_name}
bad_df.writeStream  → silver_base.{table_name}_dlq
```

**DLQ table naming convention**: `{source_table}_dlq` — always suffix, never a separate schema.

**Validation rules per table**:

| Table | PK / Not Null Checks | Business Rule Checks | Format Checks |
|---|---|---|---|
| `order_fact_RT` | `order_id`, `customer_id`, `store_id` | `order_status` in (CREATED, PAID, SHIPPED) | — |
| `order_event_fact_RT` | `order_id`, `event_type` (composite PK) | `event_type` in (CREATED, PAID, SHIPPED) | — |
| `order_item_fact_RT` | `item_id`, `order_id` | `price > 0`, `quantity > 0` | — |
| `payment_attempt_fact_RT` | `payment_id`, `order_id` | `payment_method` in (UPI, CARD, NET_BANKING), `status` in (SUCCESS, FAILED) | — |
| `delivery_fact_RT` | `order_id`, `partner_id` | `delivery_type` in (STANDARD, EXPRESS), `sla_days > 0` | — |
| `discount_fact_RT` | `order_id`, `item_id` | `amount > 0` | — |

**`rejection_reason` values** (use exact strings for ops diagnosis):
- `"null_primary_key"` — any PK field is null
- `"invalid_status"` — enum value not in allowed set
- `"invalid_price"` — price ≤ 0
- `"invalid_quantity"` — quantity ≤ 0
- `"invalid_payment_method"` — payment method not recognised
- `"invalid_amount"` — discount amount ≤ 0

**What the stream NEVER does**: stop, throw an exception, or drop a row silently.
Every row is either written to the main table or the DLQ table. No row is lost.

---

## Gate 2 — Assertions at Silver Enriched (Batch)

**Where**: Before every MERGE into SCD2 dimension tables
**Type**: Hard stop — job crashes, table stays untouched, fix and rerun

**Why crash instead of route**: Bad data in SCD2 tables creates incorrect historical versions.
A corrupted `effective_from`/`effective_to` range poisons every downstream Gold fact that
resolves surrogate keys via time-range join. The corruption is retroactive and very hard to remove.

**Assertion checks before MERGE** (all 4 dims):

| Check | Condition | All dims |
|---|---|---|
| Business key not null | `customer_id IS NOT NULL` etc. | ✅ |
| No duplicate business keys in incoming batch | `COUNT(*) = COUNT(DISTINCT biz_key)` | ✅ |
| `effective_from` not null | | ✅ |

**Dim-specific checks**:

| Table | Additional Checks |
|---|---|
| `customer_dim` | `segment` in (REGULAR, PREMIUM, VIP), `loyalty_tier` in (BRONZE, SILVER, GOLD, PLATINUM), `zip` = 6 digits |
| `product_dim` | `product_name` not null, `category` not null |
| `store_dim` | `store_type` in (OWNED, FRANCHISE), `region` not null, `state` not null |
| `delivery_partner_dim` | `partner_type` in (EXPRESS, STANDARD, HYPERLOCAL), `partner_name` not null |

**Implementation**: Raise a Python exception with a clear message if any assertion fails.
Log the failure with row count and sample bad values before raising.

---

## Gate 3 — DLQ at Gold RT (Streaming)

**Where**: Every Gold RT streaming write (4 tables)
**Type**: Same routing pattern as Gate 1, with additional dedup layer

**Order of operations matters** — always in this sequence:
```python
df.withWatermark("event_time", "30 minutes")          # 1. Watermark first
  .dropDuplicatesWithinWatermark(["business_key"])     # 2. Dedup second
  .filter(validation_condition)                        # 3. Validate third
  # good → Gold RT table, bad → DLQ
```

**Why watermark before dedup**: `dropDuplicatesWithinWatermark` requires a watermark to be
set first — it uses the watermark to bound the dedup state store. Calling it without a
watermark falls back to unbounded dedup, which causes unbounded state and OOM.

**Business keys for dedup per table**:
| Table | `dropDuplicatesWithinWatermark` keys |
|---|---|
| `sales_summary_RT` | `order_id`, `window_start` |
| `category_sales_metrics_RT` | `order_id`, `item_id`, `window_start` |
| `payment_usage_metrics_RT` | `payment_id`, `window_start` |
| `order_lifecycle_metrics_RT` | `order_id`, `event_type`, `window_start` |

**Validation at Gate 3**:
- `window_start` not null (malformed window → DLQ)
- Revenue/count columns not negative
- `rejection_reason` values: `"null_window"`, `"negative_revenue"`, `"negative_count"`

---

## Gate 4 — Assertions at Gold Batch (Batch)

**Where**: Before writing Gold Curated facts and Gold Batch aggregations
**Type**: Hard stop — same philosophy as Gate 2

**Deduplication** (run before assertion checks):
```sql
-- fact_orders
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY bronze_ingest_ts DESC) AS rn
  FROM silver_order_fact_RT
) WHERE rn = 1

-- fact_order_items
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY bronze_ingest_ts DESC) AS rn
  FROM silver_order_item_fact_RT
) WHERE rn = 1
```

**Assertion checks**:
- After dedup: zero duplicate `order_id` in `fact_orders`
- After dedup: zero duplicate `item_id` in `fact_order_items`
- Every `order_id` in `fact_orders` resolves to exactly one `customer_sk` and one `store_sk`
  (time-range join must be non-null — orphan orders indicate a gap in SCD2 history)
- `shipping_fee >= 0`, `tax >= 0`
- Row count after dedup ≥ 90% of row count before (large drop = pipeline bug, not data issue)

---

## Monitoring (Across All Layers)

**Data freshness job** (runs every 5 minutes):
```python
# Check MAX(ingest_ts) at each layer — alert if > 5 minutes stale
layers = {
    "landing":  ("landing.raw_events",              "landing_ingest_ts"),
    "bronze":   ("bronze.orders_raw",               "bronze_ingest_ts"),
    "silver":   ("silver_base.order_fact_RT",       "bronze_ingest_ts"),
    "gold_rt":  ("gold_rt.sales_summary_RT",        "window_end"),
}
```

**Row count reconciliation** (runs after each Silver Base micro-batch):
```
Landing rows = Bronze rows = Silver good rows + Silver DLQ rows
```
Any gap indicates silent data loss — alert immediately.

**DLQ spike alert**: If DLQ row count increases by > 1% of total rows in a 5-minute window,
alert ops team. Likely causes: upstream schema change, bad deployment, data source issue.

---

## DLQ Coverage Checklist (12 streams total)

### Streaming layers that need DLQ
- [ ] `landing.raw_events` (Landing stream)
- [ ] `bronze.orders_raw` (Bronze stream)
- [ ] `silver_base.order_fact_RT`
- [ ] `silver_base.order_event_fact_RT`
- [ ] `silver_base.order_item_fact_RT`
- [ ] `silver_base.payment_attempt_fact_RT`
- [ ] `silver_base.delivery_fact_RT`
- [ ] `silver_base.discount_fact_RT`
- [ ] `gold_rt.sales_summary_RT`
- [ ] `gold_rt.category_sales_metrics_RT`
- [ ] `gold_rt.payment_usage_metrics_RT`
- [ ] `gold_rt.order_lifecycle_metrics_RT`

### Batch layers that use assertions (crash, not DLQ)
- [ ] Before MERGE into `silver_enriched.customer_dim`
- [ ] Before MERGE into `silver_enriched.product_dim`
- [ ] Before MERGE into `silver_enriched.store_dim`
- [ ] Before MERGE into `silver_enriched.delivery_partner_dim`
- [ ] Before writing `gold_curated.fact_orders`
- [ ] Before writing `gold_curated.fact_order_items`

---

## Databricks Notes
- DLQ pattern is identical on Databricks — same `writeStream` split
- Table names gain catalog prefix: `silver_base.order_fact_RT_dlq` → `prod_catalog.silver_base.order_fact_RT_dlq`
- Databricks Lakehouse Monitoring can be enabled on DLQ tables to auto-track DLQ row counts over time
- Assertion failures in Databricks Workflows trigger the job retry policy (3 retries, 5-min delay)