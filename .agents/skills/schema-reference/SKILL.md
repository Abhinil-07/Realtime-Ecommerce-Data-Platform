---
name: schema-reference
description: >
  Provides column-level schema context for queries, joins, and transformations across the
  27-table Medallion architecture. Use this skill whenever the user is writing SQL queries,
  doing joins between tables, asking about column names or types, debugging schema mismatches,
  or doing any column-level work. Also trigger when the user asks "what columns does X have",
  "how do I join X with Y", "what's the primary key of X", or mentions any specific table
  name from the pipeline. This skill loads the relevant schema from docs/TABLE_REFERENCE.md
  so Claude doesn't guess column names.
---

# Schema Reference Skill

This skill ensures Claude always uses correct column names, types, and join keys when
working with any of the 27 tables in the Medallion architecture.

## When to Use

Before writing any query, join, or transformation, load the relevant table schemas from
`docs/TABLE_REFERENCE.md`. Never guess column names — always verify against the reference.

## How to Use

1. Read `docs/TABLE_REFERENCE.md` for the specific tables involved in the task
2. Use the exact column names, types, and key relationships from the reference
3. Pay attention to PK/FK/BK annotations — they define join paths

## Quick Reference: Table Inventory

| # | Layer | Table | Type | PKs |
|---|-------|-------|------|-----|
| 1 | Landing | `raw_events` | Streaming | — |
| 2 | Bronze | `orders_raw` | Streaming | — |
| 3 | Silver Base | `order_fact_RT` | Streaming | `order_id` |
| 4 | Silver Base | `order_event_fact_RT` | Streaming | `order_id` + `event_type` |
| 5 | Silver Base | `order_item_fact_RT` | Streaming | `item_id` |
| 6 | Silver Base | `payment_attempt_fact_RT` | Streaming | `payment_id` |
| 7 | Silver Base | `delivery_fact_RT` | Streaming | `order_id` |
| 8 | Silver Base | `discount_fact_RT` | Streaming | `order_id` + `item_id` |
| 9 | Silver Enriched | `customer_dim` | Batch SCD2 | `customer_sk` (BK: `customer_id`) |
| 10 | Silver Enriched | `product_dim` | Batch SCD2 | `product_sk` (BK: `product_id`) |
| 11 | Silver Enriched | `store_dim` | Batch SCD2 | `store_sk` (BK: `store_id`) |
| 12 | Silver Enriched | `delivery_partner_dim` | Batch SCD2 | `delivery_partner_sk` (BK: `partner_id`) |
| 13-17 | Gold Curated | Dims + `fact_orders` + `fact_order_items` | Batch | See reference |
| 18-21 | Gold RT | 4 KPI tables | Streaming | `window_start` + grouping keys |
| 22-25 | Gold Batch | 4 aggregation tables | Batch | date + grouping keys |

## Common Join Paths

### Silver Base → Silver Enriched (Business Key joins)
```
order_fact_RT.customer_id → customer_dim.customer_id
order_fact_RT.store_id → store_dim.store_id
order_item_fact_RT.product_id → product_dim.product_id
delivery_fact_RT.partner_id → delivery_partner_dim.partner_id
```

### Silver → Gold Curated (Time-Range joins for surrogate key resolution)
```
order_fact_RT → customer_dim ON customer_id AND order_time BETWEEN effective_from AND effective_to
order_fact_RT → store_dim ON store_id AND order_time BETWEEN effective_from AND effective_to
order_item_fact_RT → product_dim ON product_id AND order_time BETWEEN effective_from AND effective_to
```

### Gold Star Schema (Surrogate Key joins)
```
fact_orders.customer_sk → dim_customer.customer_sk
fact_orders.store_sk → dim_store.store_sk
fact_orders.order_date_key → dim_date.date_key
fact_order_items.product_sk → dim_product.product_sk
```

## Key Rule

For full column-level schemas, always read `docs/TABLE_REFERENCE.md`. This skill provides
the quick lookup; the full reference has every column, type, and source mapping.
