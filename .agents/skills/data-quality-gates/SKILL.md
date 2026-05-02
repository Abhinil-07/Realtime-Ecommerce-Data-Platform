---
name: data-quality-gates
description: >
  Implements the 4-gate data quality strategy for the Medallion pipeline. Use this skill
  when writing validation logic, assertion checks, DLQ routing rules, or any code that
  decides whether data is "good" or "bad". Also trigger when the user mentions data quality,
  validation, assertions, gate 0/1/2/3/4, crash vs route, good/bad split, or asks how to
  handle bad data at any layer. This skill ensures the correct gate strategy is applied —
  DLQ routing for streaming (Gates 1, 3) and hard-crash assertions for batch (Gates 2, 4).
---

# Data Quality Gates Skill

Two failure modes, two responses:

| Layer Type | Response | Why |
|-----------|----------|-----|
| **Streaming** (Gates 1, 3) | Route to DLQ, never stop | Stopping loses Kafka offsets |
| **Batch** (Gates 2, 4) | Crash the job, leave table untouched | Bad MERGE into SCD2 is retroactively destructive |

## Gate Overview

| Gate | Where | Type | Handles |
|------|-------|------|---------|
| 0 | Confluent Schema Registry | Preventive | Structural corruption (removed fields, type changes) |
| 1 | Silver Base streaming writes | DLQ routing | Null PKs, invalid enums, negative values |
| 2 | Before Silver Enriched MERGE | Hard crash | Duplicate business keys, invalid dim attributes |
| 3 | Gold RT streaming writes | DLQ routing | Null windows, negative counts (after watermark+dedup) |
| 4 | Before Gold Batch writes | Hard crash | Duplicate PKs post-dedup, orphan surrogate keys |

## Gate 0 — Schema Registry (Kafka)

Owned by Confluent config, not Spark code. Blocks:
- Removed required fields, type changes, broken JSON
- Does NOT catch: null values, invalid business values, format violations

## Gate 1 — Silver Base DLQ

See `dlq-writer` skill for full implementation. Key points:
- Every Silver Base table gets a `{table}_dlq` companion
- Use `src/utils/dlq.py` → `split_good_bad()` function
- `rejection_reason` column with exact diagnostic strings
- DLQ tables initialized BEFORE stream starts

## Gate 2 — Silver Enriched Assertions

See `scd2-merge` skill for full implementation. Key points:
- Assertions baked into the merge function (hybrid approach)
- Universal: null business key check, duplicate check
- Dim-specific: enum values, format checks (zip = 6 digits)
- Raises `AssertionError` with sample bad values — never writes bad data

## Gate 3 — Gold RT DLQ

Same DLQ pattern as Gate 1, with additional constraints:
- **Order**: watermark → dedup → validate → write
- Watermark MUST come before `dropDuplicatesWithinWatermark`
- Validates: `window_start` not null, non-negative metrics

## Gate 4 — Gold Batch Assertions

See `gold-batch-pattern` skill for full implementation. Key points:
- ROW_NUMBER dedup runs before assertions
- Zero duplicate PKs after dedup
- Every business key resolves to exactly one surrogate key (time-range join)
- Row count sanity check (after dedup ≥ 90% of before)

## Monitoring

- **Data freshness**: Check `MAX(ingest_ts)` every 5 minutes per layer
- **Row reconciliation**: `Landing rows = Bronze rows = Silver good + Silver DLQ`
- **DLQ spike alert**: DLQ > 1% of total in 5-min window → alert ops

## Implementation Checklist

When adding data quality to any table:
1. Identify which gate applies (streaming → DLQ, batch → assertions)
2. Define validation rules (null checks, enums, business rules)
3. Implement using the appropriate pattern (`split_good_bad` or `run_gate2_assertions`)
4. Add logging with `job_name`, `row_count`, validation result
5. Test with intentionally bad data to verify routing/crashing works
