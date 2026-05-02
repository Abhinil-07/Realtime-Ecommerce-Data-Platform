---
name: dlq-writer
description: >
  Implements Dead Letter Queue (DLQ) routing logic for streaming tables in the Medallion
  architecture. Use this skill whenever adding DLQ logic, handling bad records, implementing
  good/bad data splits, writing rejection reasons, or working on any streaming validation.
  Also trigger when the user mentions DLQ, dead letter queue, bad records, rejection_reason,
  data routing, "streams never fail", or is editing any Silver Base or Gold RT streaming
  notebook that needs to handle invalid data without stopping the stream.
---

# DLQ Writer Skill

Streams **never fail, never drop data**. Every row lands in the main table or the DLQ table.

## Module Location

All DLQ logic lives in `src/utils/dlq.py`. Notebooks never implement validation inline.

### Core Function

```python
def split_good_bad(
    df: DataFrame,
    validation_rules: list[dict],
) -> tuple[DataFrame, DataFrame]:
    """
    Split DataFrame into good and bad rows.
    Bad rows get a 'rejection_reason' column.
    
    validation_rules format:
    [
        {"check": "not_null", "columns": ["order_id", "customer_id"]},
        {"check": "enum", "column": "order_status", "values": ["CREATED", "PAID", "SHIPPED"]},
        {"check": "positive", "column": "price"},
    ]
    """
```

Build a composite rejection reason using `coalesce(*conditions)` — first failing rule wins.
Good rows have `rejection_reason IS NULL`, bad rows have the reason string.

---

## DLQ Table Convention

- **Naming**: `{source_table}_dlq` — suffix, never a separate schema
- **Schema**: Same as source + `rejection_reason STRING`
- **Initialize BEFORE starting streams** — create empty Delta tables in setup cells

## Gate 1: Silver Base Rules

| Table | Not Null (PKs) | Business Rules |
|-------|---------------|----------------|
| `order_fact_RT` | `order_id`, `customer_id`, `store_id` | `order_status` ∈ {CREATED, PAID, SHIPPED} |
| `order_event_fact_RT` | `order_id`, `event_type` | `event_type` ∈ {CREATED, PAID, SHIPPED} |
| `order_item_fact_RT` | `item_id`, `order_id` | `price > 0`, `quantity > 0` |
| `payment_attempt_fact_RT` | `payment_id`, `order_id` | `payment_method` ∈ {UPI, CARD, NET_BANKING}, `status` ∈ {SUCCESS, FAILED} |
| `delivery_fact_RT` | `order_id`, `partner_id` | `delivery_type` ∈ {STANDARD, EXPRESS}, `sla_days > 0` |
| `discount_fact_RT` | `order_id`, `item_id` | `amount > 0` |

### Rejection Reason Values (exact strings for ops diagnosis)
`"null_primary_key"`, `"invalid_status"`, `"invalid_price"`, `"invalid_quantity"`,
`"invalid_payment_method"`, `"invalid_amount"`

## Gate 3: Gold RT Rules

**Order of operations matters:**
```python
df.withWatermark("event_time", "30 minutes")          # 1. Watermark FIRST
  .dropDuplicatesWithinWatermark(["business_key"])     # 2. Dedup SECOND
  # 3. THEN split good/bad
```
Watermark before dedup — `dropDuplicatesWithinWatermark` needs the watermark to bound state.

Validations: `window_start` not null, revenue/count not negative.
Rejections: `"null_window"`, `"negative_revenue"`, `"negative_count"`

## Notebook Pattern

```python
from src.utils.dlq import split_good_bad

rules = [
    {"check": "not_null", "columns": ["order_id", "customer_id", "store_id"]},
    {"check": "enum", "column": "order_status", "values": ["CREATED", "PAID", "SHIPPED"]},
]

def process_batch(batch_df, batch_id):
    good_df, bad_df = split_good_bad(batch_df, rules)
    good_df.write.format("delta").mode("append").save(GOOD_PATH)
    if bad_df.count() > 0:
        bad_df.write.format("delta").mode("append").save(DLQ_PATH)
        logger.warning(f"Batch {batch_id}: {bad_df.count()} rows to DLQ")

stream = (
    parsed_df.writeStream
    .foreachBatch(process_batch)
    .option("checkpointLocation", CHECKPOINT_PATH)
    .start()
)
```

## Self-Healing

Corrected upstream data flows through the same pipeline. Good data lands normally.
DLQ tables drain naturally. Dashboards heal without manual intervention.
