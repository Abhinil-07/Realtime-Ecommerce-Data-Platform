---
name: scd2-merge
description: >
  Implements SCD Type 2 (Slowly Changing Dimension) merge logic for dimension tables in the
  Medallion architecture. Use this skill whenever writing, modifying, debugging, or refactoring
  any of the 4 Silver Enriched dimension tables (customer_dim, product_dim, store_dim,
  delivery_partner_dim), or when creating the generic SCD2 merge function in
  src/transformations/scd2.py. Also trigger when the user mentions SCD2, slowly changing
  dimensions, dimension history, effective_from/effective_to, surrogate keys in the context
  of dimensions, or closing/expiring old dimension rows. This skill ensures the merge logic,
  Gate 2 assertions, and surrogate key generation all follow the project's non-negotiable rules.
---

# SCD2 Merge Skill

This skill guides the implementation of SCD Type 2 merge logic across the 4 Silver Enriched
dimension tables. The goal is a **single, generic, reusable merge function** in
`src/transformations/scd2.py` that handles all 4 dims — never write per-dim merge logic
inline in notebooks.

## Why SCD2 Matters in This Pipeline

Gold Curated fact tables (`fact_orders`, `fact_order_items`) resolve business keys to surrogate
keys using **time-range joins**:

```sql
JOIN silver_customer_dim c
  ON o.customer_id = c.customer_id
 AND o.order_time >= c.effective_from
 AND o.order_time < c.effective_to
```

If `effective_from` or `effective_to` is wrong, every downstream Gold fact gets the wrong
surrogate key — and this corruption is **retroactive**. That's why Gate 2 assertions crash
the job before a bad MERGE rather than writing corrupted history.

---

## Scope

This skill covers **merge + assertions + notebook calling pattern**. It does NOT cover the
upstream steps (reading Bronze CDF, parsing JSON, deduplicating incoming data) — those are
entity-specific and live in each notebook or in separate utility modules.

The boundary is clear: by the time data reaches the merge function, it must be a clean,
deduplicated DataFrame with one row per business key containing the latest attribute values.

---

## The 4 Dimension Tables

Each dimension shares this structure:

| Column | Type | Purpose |
|--------|------|---------|
| `{entity}_sk` | bigint | PK — auto-generated surrogate key |
| `{business_key}` | string | UK — the natural business key |
| _tracked attributes_ | varies | Columns whose changes trigger a new SCD2 version |
| `effective_from` | timestamp | When this version became active |
| `effective_to` | timestamp | When superseded (`9999-12-31 00:00:00` if current) |
| `is_current` | boolean | `true` for the latest version |

### Dimension Config

| Dimension | Surrogate Key | Business Key | SCD2 Trigger Columns | Source |
|-----------|---------------|-------------|----------------------|--------|
| `customer_dim` | `customer_sk` | `customer_id` | `segment`, `loyalty_tier`, `city`, `zip` | `silver_order_fact_RT` |
| `product_dim` | `product_sk` | `product_id` | `product_name`, `brand`, `category` | `silver_order_item_fact_RT` |
| `store_dim` | `store_sk` | `store_id` | `store_type`, `region`, `city`, `state` | `silver_order_fact_RT` |
| `delivery_partner_dim` | `delivery_partner_sk` | `partner_id` | `partner_name`, `partner_type` | `silver_delivery_fact_RT` |

---

## The Generic Merge Function

Lives in `src/transformations/scd2.py`. All 4 dims use the same code path.

### Function Signature

```python
def scd2_merge(
    spark: SparkSession,
    incoming_df: DataFrame,
    target_table: str,
    business_key: str,
    surrogate_key: str,
    tracked_columns: list[str],
    all_columns: list[str],
    dim_specific_checks: list[dict] | None = None,
) -> dict:
    """
    Perform SCD2 merge: validate → close changed rows → insert new versions.

    Gate 2 assertions run automatically before any write. There is no way to
    bypass them — this is intentional. If you need to test assertions in
    isolation, import run_gate2_assertions() directly.

    Returns:
        dict with keys: 'rows_closed', 'rows_inserted', 'rows_unchanged'
    """
```

### Merge Strategy (2-Step)

The merge uses two steps because Delta Lake's MERGE cannot both UPDATE existing rows and
INSERT new rows that reference the updated state in a single pass.

**Step 1 — Close changed rows:**
```sql
MERGE INTO {target_table} AS target
USING {incoming_view} AS source
ON target.{business_key} = source.{business_key} AND target.is_current = true
WHEN MATCHED AND (
    target.{col1} <=> source.{col1} IS FALSE OR
    target.{col2} <=> source.{col2} IS FALSE OR ...
)
THEN UPDATE SET
    target.is_current = false,
    target.effective_to = current_timestamp()
```

Use null-safe comparison (`<=>` operator or `COALESCE`) for trigger column checks.
A tracked column going from a value to NULL is a real change and must trigger a new version.

**Step 2 — Insert new versions (changed + brand new entities):**
```sql
INSERT INTO {target_table}
SELECT
    {max_sk} + row_number() OVER (ORDER BY {business_key}) AS {surrogate_key},
    src.{business_key}, src.{col1}, src.{col2}, ...,
    current_timestamp() AS effective_from,
    CAST('9999-12-31 00:00:00' AS TIMESTAMP) AS effective_to,
    true AS is_current
FROM {incoming_view} src
LEFT ANTI JOIN {target_table} dim
    ON src.{business_key} = dim.{business_key} AND dim.is_current = true
```

Where `{max_sk}` is computed once before the insert:
```python
max_sk = spark.sql(f"SELECT COALESCE(MAX({surrogate_key}), 0) FROM {target_table}").collect()[0][0]
```

### Why `row_number()` instead of `monotonically_increasing_id()`

`monotonically_increasing_id()` generates IDs as `(partition_id << 33) + sequence`, producing
large gaps like `0, 1, 8589934592, 8589934593...` across partitions. This causes:
- Massive gaps in surrogate keys
- Potential collisions on crash + retry scenarios

`row_number() OVER (ORDER BY business_key) + max_sk` produces sequential, deterministic,
gap-free surrogate keys. The shuffle cost is negligible for dimension tables (thousands of
rows, not millions).

### First-Run Seeding

When the dimension table is empty (`COUNT(*) = 0`), skip the MERGE and directly INSERT
all incoming rows with `row_number() OVER (ORDER BY business_key)` as the surrogate key.

---

## Gate 2 Assertions (Hybrid Approach)

Gate 2 assertions are **baked into the merge function** — they run automatically before any
write, with no bypass flag. But `run_gate2_assertions()` is also a standalone importable
function so you can test assertions in isolation.

```python
# In the merge function (automatic, no bypass):
def scd2_merge(...):
    run_gate2_assertions(incoming_df, business_key, dim_specific_checks)
    # ... proceed with merge only if assertions pass

# In tests (standalone):
from src.transformations.scd2 import run_gate2_assertions
run_gate2_assertions(bad_df, "customer_id", customer_checks)  # test independently
```

### Assertion Function

```python
def run_gate2_assertions(
    incoming_df: DataFrame,
    business_key: str,
    dim_specific_checks: list[dict] | None = None,
) -> None:
    """
    Run Gate 2 data quality assertions before SCD2 merge.
    Raises AssertionError with diagnostic info if any check fails.
    Logs failure with row count and sample bad values before raising.

    dim_specific_checks format:
    [
        {"column": "segment", "check": "enum", "values": ["REGULAR", "PREMIUM", "VIP"]},
        {"column": "zip", "check": "regex", "pattern": r"^\d{6}$"},
        {"column": "product_name", "check": "not_null"},
    ]
    """
```

### Universal Checks (All 4 Dims)

| Check | How | Failure Action |
|-------|-----|----------------|
| Business key not null | `incoming_df.filter(col(biz_key).isNull()).count() == 0` | Raise with count of null rows |
| No duplicate business keys | `count == count_distinct` on business key | Raise with sample duplicates |

### Dimension-Specific Checks

| Dimension | Checks |
|-----------|--------|
| `customer_dim` | `segment` ∈ {REGULAR, PREMIUM, VIP}; `loyalty_tier` ∈ {BRONZE, SILVER, GOLD, PLATINUM}; `zip` matches `^\d{6}$` |
| `product_dim` | `product_name` not null; `category` not null |
| `store_dim` | `store_type` ∈ {OWNED, FRANCHISE}; `region` not null; `state` not null |
| `delivery_partner_dim` | `partner_type` ∈ {EXPRESS, STANDARD, HYPERLOCAL}; `partner_name` not null |

---

## Notebook Calling Pattern

Notebooks are thin orchestrators. Here's what a dimension notebook should look like:

```python
# ── Imports ──────────────────────────────────────────────
from src.transformations.scd2 import scd2_merge
from src.utils.batch_tracker import (
    get_last_processed_version,
    save_last_processed_version,
    read_bronze_cdf,
    get_current_bronze_version,
)

# ── Config ───────────────────────────────────────────────
JOB_NAME = "delivery_partner_dim_scd2"
TARGET_TABLE = "silver_enriched.delivery_partner_dim"
BUSINESS_KEY = "partner_id"
SURROGATE_KEY = "delivery_partner_sk"
TRACKED_COLUMNS = ["partner_name", "partner_type"]
ALL_COLUMNS = ["partner_id", "partner_name", "partner_type"]
DIM_CHECKS = [
    {"column": "partner_type", "check": "enum", "values": ["EXPRESS", "STANDARD", "HYPERLOCAL"]},
    {"column": "partner_name", "check": "not_null"},
]

# ── Read New Data ────────────────────────────────────────
last_version = get_last_processed_version(spark, JOB_NAME)
bronze_df = read_bronze_cdf(spark, last_version)
new_row_count = bronze_df.count()

if new_row_count == 0:
    logger.info("No new data. Skipping.")
else:
    # ── Parse & Deduplicate (entity-specific) ────────────
    incoming_df = parse_and_dedup_partners(bronze_df)  # notebook-specific logic

    # ── Merge (generic — handles assertions internally) ──
    result = scd2_merge(
        spark=spark,
        incoming_df=incoming_df,
        target_table=TARGET_TABLE,
        business_key=BUSINESS_KEY,
        surrogate_key=SURROGATE_KEY,
        tracked_columns=TRACKED_COLUMNS,
        all_columns=ALL_COLUMNS,
        dim_specific_checks=DIM_CHECKS,
    )

    logger.info(f"Merge complete: {result}")

    # ── Bookmark ─────────────────────────────────────────
    current_version = get_current_bronze_version(spark)
    save_last_processed_version(spark, JOB_NAME, current_version, new_row_count)
```

The key principle: parsing and deduplication are entity-specific (each dim extracts different
JSON fields), but everything from `scd2_merge()` onward is identical across all 4 dims.

---

## Databricks Compatibility

These patterns are fully Databricks-compatible with no code changes:
- `MERGE INTO` syntax is identical
- Delta CDF works the same way
- `row_number()` works the same way

What changes (handled by config, not this skill):
- Table names gain catalog prefix: `silver_enriched.X` → `prod_catalog.silver_enriched.X`
- Paths: `/opt/spark-data/` → `abfss://...`
- SparkSession: auto-provided, no `getOrCreate()`

---

## Common Mistakes to Avoid

1. **Writing per-dim merge SQL in notebooks** — always call the generic function
2. **Using `monotonically_increasing_id()` for surrogate keys** — use `row_number() + MAX(sk)`
3. **Single-step MERGE** — Delta can't UPDATE + INSERT referencing updated state in one pass
4. **Forgetting Gate 2 assertions** — they're baked into the merge function, but if you're
   writing a new dim, you must pass the correct `dim_specific_checks`
5. **Non-null-safe trigger comparison** — use `<=>` or `COALESCE` to detect changes when
   a tracked column goes from a value to NULL
6. **Skipping the batch job tracker** — without bookmarking, reruns reprocess all data
