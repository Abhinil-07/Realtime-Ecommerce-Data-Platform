---
name: tech-radar
description: >
  Evaluates technology choices and alternatives for the data platform. Use this skill when
  the user is comparing tools, evaluating migration options, or questioning technology
  decisions. Trigger when the user mentions Spark vs Flink, Delta vs Iceberg, managed vs
  self-hosted Kafka, Databricks vs Synapse, or asks "should we use X instead of Y",
  "is X the right choice", "what about switching to", or any technology comparison
  question. Provides structured pros/cons analysis relative to the project's specific
  context (scale, team, migration timeline), not generic comparisons.
---

# Tech Radar Skill

When evaluating technology choices, always analyze relative to this project's context:
- **Current stack**: Spark Structured Streaming, Delta Lake, Confluent Kafka, Docker
- **Target**: Databricks on Azure
- **Scale**: Single-store e-commerce, growing
- **Team**: Small — favoring simplicity and managed services

## How to Evaluate

For every technology comparison, provide:

### 1. Structured Comparison Table

| Criteria | Option A | Option B |
|----------|----------|----------|
| Learning curve | ... | ... |
| Migration effort from current | ... | ... |
| Databricks compatibility | ... | ... |
| Community / ecosystem maturity | ... | ... |
| Cost at current scale | ... | ... |
| Cost at 10x scale | ... | ... |
| Operational overhead | ... | ... |

### 2. Context-Specific Analysis

Don't give generic "X is better than Y" answers. Analyze relative to:
- **What we already have**: Migration cost from current stack
- **Where we're going**: Databricks compatibility
- **Our scale**: Don't recommend tools designed for Netflix-scale if we're processing
  thousands of orders per day
- **Our team**: Small team means managed > self-hosted, simple > powerful

### 3. Recommendation with Reasoning

Give a clear recommendation, but acknowledge when "it depends" and explain what it
depends on.

## Common Technology Questions for This Project

### Spark Structured Streaming vs Flink
- Spark SSS: already in use, Databricks-native, single engine for batch+stream
- Flink: better true-streaming semantics, lower latency, but separate engine
- **Default recommendation**: Stay with Spark — dual-engine complexity isn't justified
  until sub-second latency is needed

### Delta Lake vs Apache Iceberg
- Delta: Databricks-native, CDF support (critical for SCD2), deep Spark integration
- Iceberg: more vendor-neutral, growing ecosystem
- **Default recommendation**: Stay with Delta — CDF dependency and Databricks target
  make this clear-cut

### Confluent Kafka (managed) vs Self-Hosted Kafka
- Confluent: Schema Registry, managed operations, higher cost
- Self-hosted: cheaper at scale, full control, operational burden
- **Default recommendation**: Confluent for now — operational overhead of self-hosted
  Kafka isn't justified for a small team

### Databricks vs Azure Synapse
- Databricks: Delta-native, Unity Catalog, Structured Streaming first-class
- Synapse: tighter Azure integration, serverless SQL pools
- **Default recommendation**: Databricks — the pipeline is Spark+Delta, and Databricks
  is the best home for that stack

## Rules

- Always load `docs/DATABRICKS_MIGRATION.md` when discussing Azure/Databricks options
- Never recommend a technology without addressing migration cost from current stack
- If recommending a change, provide a concrete migration path (not just "switch to X")
- Acknowledge lock-in risks when they exist
