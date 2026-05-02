---
name: gold-batch-pattern
description: >
  Implements Gold Batch table patterns in the Medallion architecture. Use this skill when
  working on any Gold Curated or Gold Batch table — fact_orders, fact_order_items,
  dim_customer, dim_product, dim_store, dim_delivery_partner, dim_date, sales_summary,
  category_sales_metrics, discount_effectiveness, delivery_partner_metrics. Also trigger
  when the user mentions ROW_NUMBER dedup, star schema, time-range joins, frozen surrogate
  keys, Gold batch aggregations, or nightly batch jobs. Ensures dedup with ROW_NUMBER(),
  surrogate key resolution via time-range join, and Gate 4 assertions are correct.
---

# Gold Batch Pattern Skill

Gold Batch tables form the star schema used by BI tools. They have two critical patterns
that must be implemented correctly.

## Pattern 1: Surrogate Key Resolution (Time-Range Join)

Gold fact tables convert business keys → surrogate keys using time-range joins against
SCD2 dimensions. The surrogate key is **frozen at event time** — never re-computed.

```sql
-- fact_orders: resolve customer_sk and store_sk
SELECT
  o.order_id,
  CAST(DATE_FORMAT(o.order_time, 'yyyyMMdd') AS INT) AS order_date_key,
  c.customer_sk,
  s.store_sk,
  o.order_status, o.total_items, o.shipping_fee, o.tax, o.currency, o.platform
FROM silver_order_fact_RT o
JOIN silver_customer_dim c
  ON o.customer_id = c.customer_id
 AND o.order_time >= c.effective_from AND o.order_time < c.effective_to
JOIN silver_store_dim s
  ON o.store_id = s.store_id
 AND o.order_time >= s.effective_from AND o.order_time < s.effective_to
```

```sql
-- fact_order_items: resolve product_sk (needs order_time from fact)
SELECT
  i.order_id, i.item_id, p.product_sk,
  i.price, i.quantity, i.discount_amount
FROM silver_order_item_fact_RT i
JOIN silver_order_fact_RT o ON i.order_id = o.order_id
JOIN silver_product_dim p
  ON i.product_id = p.product_id
 AND o.order_time >= p.effective_from AND o.order_time < p.effective_to
```

**Why frozen**: If a customer changes from PREMIUM to VIP, orders placed while they were
PREMIUM must keep the PREMIUM `customer_sk`. Re-computing would give them the VIP key,
corrupting historical analysis.

## Pattern 2: ROW_NUMBER Dedup

Before writing Gold facts, deduplicate using ROW_NUMBER — not DISTINCT, not GROUP BY:

```sql
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY order_id ORDER BY bronze_ingest_ts DESC
  ) AS rn
  FROM silver_order_fact_RT
) WHERE rn = 1
```

This keeps the **latest version** of each record. Run dedup before the time-range join.

## Gate 4 Assertions

Run before writing Gold Curated facts and Gold Batch aggregations:

| Check | What | Why |
|-------|------|-----|
| Zero duplicate PKs after dedup | `COUNT(order_id) == COUNT(DISTINCT order_id)` | Dedup must be complete |
| No orphan surrogate keys | Every `order_id` resolves to non-null `customer_sk` and `store_sk` | Gap in SCD2 history |
| Non-negative amounts | `shipping_fee >= 0`, `tax >= 0` | Business rule |
| Row count sanity | After dedup ≥ 90% of before dedup | Large drop = pipeline bug |

If any assertion fails, **crash the job** — don't write partial/corrupted data.

## Gold Dim Tables (Enriched Dimensions)

Gold dims add pre-computed business metrics to Silver dims:
- `dim_customer`: total_orders, total_spend, avg_order_value, preferred_payment_method
- `dim_product`: total_units_sold, total_revenue, discount_rate
- `dim_store`: total_orders, total_revenue, avg_delivery_time_hours
- `dim_delivery_partner`: total_deliveries, sla_breach_rate, first_attempt_success_rate

These are computed by joining Silver dims with Gold facts and aggregating per surrogate key.

## `dim_date` — Static Table

Generated once, never updated:
```python
# Generate all dates from 2024-01-01 to 2030-12-31
# Columns: date_key (YYYYMMDD int), full_date, day_of_week, month, quarter, year, is_weekend
```

## Gold Batch Aggregation Tables

| Table | Grain | Group By |
|-------|-------|----------|
| `sales_summary` | Daily | date, store_id, region, category |
| `category_sales_metrics` | Daily | date, category |
| `discount_effectiveness` | Daily | date, discount_code, category |
| `delivery_partner_metrics` | Weekly | week_start_date, partner_id |

All join Gold facts with Silver dims using surrogate keys, then aggregate.
