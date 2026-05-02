---
name: scale-review
description: >
  Reviews pipeline design through a scalability and production-readiness lens. Use this
  skill when the user asks about performance, bottlenecks, capacity planning, or what
  breaks at higher throughput. Trigger when the user mentions "what happens at 10x",
  "will this scale", "performance bottleneck", "production ready", "load testing",
  "memory pressure", "partition skew", "checkpoint overhead", "cluster sizing", or any
  question about whether the current design can handle growth. Also trigger when discussing
  Databricks cluster configuration or resource allocation for the production deployment.
---

# Scale Review Skill

Review the pipeline design through a "what breaks first" lens. This project currently
runs on a Docker cluster (1 master + 1 worker, 8-core/8GB). The target is Databricks
on Azure where cluster sizing matters for cost.

## How to Analyze

### 1. Identify the Bottleneck Chain

For any component the user asks about, trace the full path:
- **Input rate**: How fast is data arriving? (Kafka throughput)
- **Processing**: What operations are expensive? (joins, aggregations, state)
- **State**: How much state does this operation maintain? (watermarks, dedup)
- **Output**: How fast can we write? (Delta compaction, checkpointing)

### 2. Think in Terms of Scale Multipliers

| Multiplier | What Changes |
|-----------|-------------|
| 10x orders/min | Kafka partitions, micro-batch sizes, checkpoint frequency |
| 100x orders/min | Shuffle spills, state store size, Delta small file problem |
| 10x products | Product dim SCD2 merge time, Gold RT join fanout |
| 10x stores | Store dim size, partition strategy for sales_summary |

### 3. Common Bottleneck Patterns in This Pipeline

**Streaming State (Gold RT)**
- `dropDuplicatesWithinWatermark` maintains state for the watermark duration (30 min)
- At 10x throughput, state size grows linearly
- Monitor with `spark.streams.active[0].lastProgress["stateOperators"]`

**Delta Small File Problem (All Streaming Tables)**
- Streaming appends create many small files (one per micro-batch per partition)
- Fix: Enable auto compaction `spark.databricks.delta.autoCompact.enabled = true`
- Schedule `OPTIMIZE` + `VACUUM` regularly

**Shuffle in SCD2 Merge**
- The `LEFT ANTI JOIN` in Step 2 shuffles both the incoming batch and the full dimension
- At 10x dim size, this shuffle grows — but dims are small (thousands, not millions)
- Only becomes a problem if a dimension grows to millions of rows (unlikely for this domain)

**Checkpoint Overhead**
- Each stream has a checkpoint directory
- At high throughput, checkpoint writes become a bottleneck
- Monitor with `lastProgress["durationMs"]["triggerExecution"]`

**Partition Skew (Gold Batch)**
- If one store has 90% of orders, `GROUP BY store_id` creates hot partitions
- Fix: Salt the partition key or repartition before aggregation

### 4. Databricks Cluster Sizing

When the user asks about production cluster sizing:

| Layer | Workload | Recommended Cluster |
|-------|----------|-------------------|
| Landing + Bronze | Streaming (always on) | Small, single-node (low compute, high I/O) |
| Silver Base | Streaming (always on) | Medium, 2-4 nodes (parsing + DLQ split) |
| Silver Enriched | Batch (scheduled) | Medium, auto-scaling (SCD2 merge is bursty) |
| Gold RT | Streaming (always on) | Medium, 2-4 nodes (windowed aggregations) |
| Gold Batch | Batch (nightly) | Large, auto-scaling (star schema joins) |

**Key principle**: Streaming jobs need dedicated always-on clusters. Batch jobs should
use auto-scaling clusters that scale down to zero when idle.

## Production Readiness Checklist

- [ ] Checkpoint paths on reliable storage (not local disk)
- [ ] Auto compaction enabled on all streaming Delta tables
- [ ] OPTIMIZE + VACUUM scheduled for all tables
- [ ] Monitoring: data freshness, DLQ spike alerts, row reconciliation
- [ ] Alerting: PagerDuty/Slack for stream failures, SLA breaches
- [ ] Load test: Simulate 10x throughput and measure end-to-end latency
- [ ] Failure recovery: Kill a stream, verify clean restart from checkpoint
- [ ] Idempotency: Rerun a batch job, verify no duplicate data
