---
name: new-streaming-layer
description: >
  Scaffolds new streaming pipeline layers or tables in the Medallion architecture. Use this
  skill when creating a new Landing, Bronze, Silver Base, or Gold RT streaming table, or
  when adding a new fact table to an existing layer. Also trigger when the user says
  "scaffold a new stream", "add a new table", "create a new pipeline", or mentions any
  new streaming table that doesn't exist yet. Ensures the correct architectural patterns
  are followed per layer — business keys for Silver Base, tumbling windows for Gold RT,
  DLQ initialization before stream start, append-only for Bronze, etc.
---

# New Streaming Layer Skill

This skill scaffolds new streaming tables following the Medallion architecture rules.
Each layer has specific patterns that must be followed.

## Layer-Specific Rules

### Landing (Raw Kafka Buffer)
- **Write mode**: Append only
- **Schema**: `key`, `value`, `topic`, `partition`, `offset`, `kafka_timestamp`, `landing_ingest_ts`
- **Purpose**: Replay buffer — never transform data here
- Read from Confluent Kafka using `spark.readStream.format("kafka")`
- Write to Delta: `writeStream.format("delta").outputMode("append")`

### Bronze (First Queryable Table)
- **Write mode**: Append only — never overwrite or delete
- **Schema**: `source_system`, `ingestion_time`, `raw_payload`, `kafka_topic`, `kafka_partition`, `kafka_offset`, `kafka_timestamp`, `bronze_ingest_ts`
- Extract `source_system` and `ingestion_time` from JSON root
- Keep `raw_payload` as full JSON string (not flattened)
- Enable Delta CDF: `ALTER TABLE SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')`
- CDF must be enabled BEFORE Silver Enriched runs

### Silver Base (Typed Fact Tables)
- **Keys**: Business keys ONLY — never surrogate keys
- **DLQ**: Initialize DLQ table BEFORE starting the stream
- **Validation**: Gate 1 — route bad data to DLQ, never stop the stream
- Parse `raw_payload` JSON using explicit schema (StructType)
- Explode arrays as needed (items[], payments[], discounts[])
- `discount_fact_RT` requires double-explode: items[] → discounts[]
- `order_item_fact_RT` denormalizes product attrs intentionally (streaming can't wait for dims)

### Gold RT (Real-Time KPIs)
- **Windows**: 5-minute tumbling windows on every table
- **Watermark**: `withWatermark("event_time", "30 minutes")` — always before dedup
- **Dedup**: `dropDuplicatesWithinWatermark` on business keys
- **DLQ**: Gate 3 — route bad windowed data to DLQ
- **Order**: watermark → dedup → validate → write

## Scaffold Template

When creating a new streaming table, follow this notebook structure:

```python
# Cell 1: Imports & Config
JOB_NAME = "{layer}_{table_name}"
TABLE_NAME = "{layer}.{table_name}"
CHECKPOINT = "/opt/spark-data/checkpoints/{layer}/{table_name}"
OUTPUT_PATH = "/opt/spark-data/delta/{layer}/{table_name}"

# Cell 2: Create Target Table (+ DLQ if streaming)
spark.sql(f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} (...) USING DELTA LOCATION '{OUTPUT_PATH}'")
# If Silver Base or Gold RT:
spark.sql(f"CREATE TABLE IF NOT EXISTS {TABLE_NAME}_dlq (...) USING DELTA LOCATION '{OUTPUT_PATH}_dlq'")

# Cell 3: Read Source Stream
source_df = spark.readStream.format("delta").load(SOURCE_PATH)

# Cell 4: Transform (layer-specific logic)
transformed_df = ...  # parsing, exploding, windowing

# Cell 5: Write Stream
query = (
    transformed_df.writeStream
    .format("delta")
    .outputMode("append")  # or "complete" for Gold RT aggregations
    .option("checkpointLocation", CHECKPOINT)
    .start(OUTPUT_PATH)
)
```

## Non-Negotiable Checklist

Before starting any new streaming table, verify:
- [ ] DLQ table created (Silver Base, Gold RT)
- [ ] Checkpoint path is unique per stream
- [ ] Business keys only at Silver Base (no surrogate keys)
- [ ] Delta CDF enabled on Bronze (if Silver Enriched depends on it)
- [ ] Watermark set before dedup (Gold RT)
- [ ] Validation rules defined and using `src/utils/dlq.py`
- [ ] Logging uses Python `logging`, not `print()`
- [ ] No hardcoded paths or table names — use config
