# ADR-0002: Data Quality Handling Pattern (DLQ vs. Crash)

**Status**: Accepted
**Date**: 2026-05-02

## Context
In our Medallion pipeline (Landing → Bronze → Silver → Gold), data is ingested continuously via Spark Structured Streaming, while complex transformations (SCD2 Dimensions, Star Schema aggregations) run in batch. We needed a robust data quality strategy that prevents corrupt data from polluting downstream layers without sacrificing the real-time availability of our streaming applications.

## Options Considered

- **Option A: "Crash on Invalid Data" Everywhere**
  - **Gains**: Guarantees zero bad data moves downstream. Simple to implement (just throw exceptions).
  - **Costs**: Streaming pipelines will constantly halt when a single malformed event arrives, breaking SLAs for real-time dashboards and requiring manual intervention to restart.

- **Option B: Silently Drop Invalid Data**
  - **Gains**: Streams never crash and remain highly available.
  - **Costs**: Silent data loss. Violates auditability and compliance requirements, as there is no way to trace or replay the dropped events.

- **Option C: 4-Gate Hybrid Strategy (DLQ for Streaming, Crash for Batch)**
  - **Gains**: High availability for streams (bad records are routed to a Dead Letter Queue) combined with strict integrity for batch (crashing prevents complex table corruption).
  - **Costs**: Higher engineering complexity. Requires building and maintaining DLQ tables and routing logic in Spark Streaming, plus assertion frameworks for batch jobs.

## Decision
We will use **Option C: 4-Gate Hybrid Strategy (DLQ for Streaming, Crash for Batch)**.

Our 4-Gate Strategy is structured as follows:
- **Gate 0 (Landing/Kafka)**: Schema Registry blocks structural corruption before ingestion.
- **Gate 1 (Silver Base - Streaming)**: DLQ pattern. Null primary keys, format errors, or business rule violations are routed to a DLQ table. The stream *never* fails.
- **Gate 2 (Silver Enriched - Batch)**: Assertions pattern. We validate data *before* performing the `MERGE` operation for SCD2 dimensions. If validations fail, the batch job crashes ("crash > corrupt").
- **Gate 3 (Gold RT - Streaming)**: DLQ pattern. Late-arriving data beyond the watermark or deduplication failures are routed away to maintain accurate tumbling windows.
- **Gate 4 (Gold Batch - Batch)**: Assertions pattern. `ROW_NUMBER()` deduplication and validation occur before writing to the final star schema. If bad data made it this far, the job crashes.

## Rationale
Streaming and batch workloads have fundamentally different reliability requirements. 
For streaming, **availability is paramount**. A poison-pill record cannot be allowed to stop the entire pipeline. The Dead Letter Queue (DLQ) pattern allows the stream to continue processing healthy records while bad records are safely isolated for alerting and eventual replay.
For batch, **data integrity is paramount**. Batch jobs (like SCD2 merges) are idempotent and heavily stateful. It is far safer to crash a batch job, fix the upstream data, and re-run it than to let bad data corrupt a complex dimension table that serves the entire business.

## Consequences
- **Positive**: Real-time dashboards remain highly available. No silent data loss. Batch processes are protected from corruption. Idempotent batch design allows easy recovery from crashes.
- **Negative**: Developers must maintain explicit DLQ routing logic in all `src/transformations/` streaming functions. We must build operational tooling to monitor and replay DLQ tables.
- **Risks**: DLQ tables could grow unbounded if not monitored. 
  - *Mitigation*: Implement alerting on DLQ row counts to ensure data engineers investigate and resolve underlying schema or source system issues promptly.
