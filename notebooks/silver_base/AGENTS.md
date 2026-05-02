# Silver Base — Subdirectory Context

> Load `docs/table_reference.md` → Silver Base section for full column specs.
> Load `docs/DATA_QUALITY.md` → Gate 1 for full DLQ validation rules.

## What this layer does
Reads from `bronze.orders_raw` via `readStream` → parses JSON → explodes arrays →
flattens structs → writes to 6 streaming fact tables. All tables use business keys only,
never surrogate keys.

## DLQ is mandatory on every table here — streams NEVER fail
Good/bad split must use `src/utils/dlq.py` — do not write inline writeStream splits.
Full pattern and validation rules in `docs/DATA_QUALITY.md` → Gate 1.

## Validation rules (Gate 1 — quick reference)
- `order_fact_RT`: `order_id`, `customer_id`, `store_id` not null. `order_status` in (CREATED, PAID, SHIPPED)
- `order_event_fact_RT`: composite PK = (`order_id`, `event_type`). Both not null
- `order_item_fact_RT`: `item_id`, `order_id` not null. `price > 0`, `quantity > 0`
- `payment_attempt_fact_RT`: `payment_id`, `order_id` not null. `payment_method` in (UPI, CARD, NET_BANKING)
- `delivery_fact_RT`: `order_id`, `partner_id` not null. `delivery_type` in (STANDARD, EXPRESS)
- `discount_fact_RT`: `order_id`, `item_id` not null. `amount > 0`

## Special parsing notes
- `discount_fact_RT` requires double-explode: `items[]` → then `items[].discounts[]`
- `order_item_fact_RT`: `discount_amount` = `SUM(discounts[].amount)` per item — aggregate before exploding discounts
- `order_event_fact_RT`: composite PK = (`order_id`, `event_type`) — both columns must be non-null

## Databricks notes
- Stream checkpoints path will change: `/opt/spark-data/checkpoints/` → `abfss://...`
- Table names will gain catalog prefix: `silver_base.X` → `prod_catalog.silver_base.X`