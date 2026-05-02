# ADR-0001: Retain Surrogate Keys for Dimensions and Facts

**Status**: Accepted
**Date**: 2026-05-02

## Context
In our Medallion architecture, we needed a strategy for linking our event facts to our slowly changing dimensions (SCD Type 2). We had to decide whether to rely entirely on business keys (natural keys) throughout the entire pipeline and let the BI layer resolve history, or to generate and maintain surrogate keys in our dimension tables and resolve them during fact ingestion.

## Options Considered

- **Option A**: Pure Business Keys with Date Resolution at Query Time
  - **Gains**: Simplifies the ingestion pipeline; no need for complex time-range joins during fact processing; Silver and Gold facts remain identical.
  - **Costs**: Pushes heavy point-in-time resolution logic to the BI layer (slow queries); makes fact tables effectively mutable if dimension history is restated; risks reporting inconsistencies.

- **Option B**: Surrogate Keys in Gold Dimensions + Time-Range Join in Facts
  - **Gains**: Facts are immutable once written (surrogate keys are frozen at event time); guaranteed point-in-time accuracy; Gold layer queries become simple, highly performant equi-joins.
  - **Costs**: Requires a time-range join during Gold pipeline ingestion; creates a dependency where dimensions must ideally be processed before facts to avoid "Unknown" key assignments.

## Decision
We will use **Option B: Surrogate Keys in Gold Dimensions + Time-Range Joins in Facts**.

*Note: Silver Base tables will continue to use BUSINESS KEYS ONLY to ensure our streaming ingestion remains stable, fast, and completely decoupled from batch dimension processing.*

## Rationale
Using surrogate keys allows us to permanently freeze the dimensional context of a fact at the exact moment the event occurred. This guarantees that historical reporting remains perfectly accurate even if a dimension undergoes a Type 2 change later (e.g., a product changes categories). The engineering cost of performing the time-range join during the batch transformation phase is heavily outweighed by the performance and simplicity gains in the Gold (curated) layer for end-users and downstream applications.

## Consequences
- **Positive**: Downstream BI queries are extremely fast (simple `JOIN` on integer surrogate keys); fact tables represent immutable, indisputable historical truth.
- **Negative**: The pipeline must handle the complexity of time-range joins (`fact.event_time BETWEEN dim.effective_from AND dim.effective_to`).
- **Risks**: Late-arriving dimension records could cause a fact to be assigned an incorrect or "Unknown" surrogate key. 
  - *Mitigation*: We intentionally denormalize critical product attributes into `silver_order_item_fact_RT` so streaming analytics don't have to wait for dimensions. For batch, we rely on our Gold Data Quality gates and allow facts to fallback to a `-1` (Unknown) SK if the dimension is missing at event time.

## Related Decisions
- *(None yet)*
