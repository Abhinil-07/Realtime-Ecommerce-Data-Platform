# Production-Grade Kafka to Delta Streaming (Medallion Architecture)

A robust, fully dockerized data platform demonstrating an end-to-end Kafka streaming pipeline using Apache Spark Structured Streaming and Delta Lake. This project implements a modern Medallion architecture (Bronze, Silver, Gold) with production-ready patterns including Dead Letter Queues (DLQ), Change Data Feed (CDF), and modular Python design.

---

## Architecture Overview

The pipeline strictly adheres to the Medallion Architecture data design pattern:

- **Landing (Raw Bytes):** Direct stream ingestion from Confluent Kafka. Data is stored as raw binary payload.
- **Bronze (Raw JSON):** Append-only stream that casts Kafka binaries to JSON strings alongside Kafka metadata (offsets, timestamps). Acts as our immutable history.
- **Silver Base (Streaming Facts):** Parses JSON into strongly-typed columns. Implements an inline **Dead Letter Queue (DLQ)** to quarantine bad records (missing PKs, invalid business logic) without crashing the stream.
- **Silver Enriched (Batch Dimensions):** Uses Delta Change Data Feed (CDF) against Bronze to incrementally process and run `MERGE` operations for Type-2 Slowly Changing Dimensions (SCD2). Validation gates ensure no bad data corrupts history.
- **Gold RT (Streaming KPIs):** Aggregated real-time dashboards utilizing `dropDuplicatesWithinWatermark` and Spark Watermarking to handle late-arriving data.
- **Gold Batch (Star Schema):** Nightly processing ensuring perfect financial reconciliation and deduplication via `ROW_NUMBER()`.

---

## Key Features
* **Self-Healing Streams:** Streams never fail. Bad data is routed to a Dead Letter Queue table. When upstream resends corrected data, dashboards heal automatically.
* **Modular Code:** Spark logic, I/O abstractions, and Kafka connection strings are decoupled from notebooks into testable `.py` modules in the `src/` directory.
* **Secure Secrets:** Uses `.env` and Docker Compose `env_file` native injection to securely handle Confluent API keys.
* **Local Spark Cluster:** Entire environment runs locally on Docker (Spark Master, Spark Worker 8-core/8GB, JupyterLab).

---

## Prerequisites & Setup

### 1. Requirements
* Docker Desktop installed and running.
* Git installed.
* A Confluent Cloud Kafka cluster (or adjust `.env` for local Kafka).

### 2. Configure Environment Variables
Create a `.env` file in the root directory (do not commit this file):

```text
KAFKA_BOOTSTRAP_SERVERS=your-broker.aws.confluent.cloud:9092
KAFKA_API_KEY=your_api_key
KAFKA_API_SECRET=your_api_secret
```

### 3. Start the Cluster
Spin up the Spark Master, Worker, and Jupyter environment:

```bash
docker-compose down && docker-compose up -d --build
```

---

## How to Run

1. **Access JupyterLab:**
   Open [http://localhost:8888/lab](http://localhost:8888/lab) in your browser. All notebooks are mounted in `/opt/spark-notebooks/`.

2. **Monitor Spark UI:**
   Open [http://localhost:8080](http://localhost:8080) for the Master UI, and [http://localhost:4040](http://localhost:4040) for the active Spark Session.

3. **Execution Order:**
   - Execute the `Landing.ipynb` orchestrator to start ingesting from Kafka.
   - Execute the Bronze -> Silver -> Gold layers sequentially.

---

## Project Structure

```text
├── .env                        # Local secrets (ignored in git)
├── docker-compose.yaml         # Spark Cluster orchestration
├── notebooks/                  # Thin Jupyter orchestrators
│   ├── landing/
│   ├── bronze/
│   ├── silver_base/
│   └── silver_enriched/
├── src/                        # Modular Python business logic
│   ├── streaming/              # Layer-specific transformations
│   │   └── landing.py
│   └── utils/                  # Shared utilities
│       ├── kafka_io.py         # Kafka SASL abstractions
│       ├── stream_io.py        # Generic Delta read/write streams
│       └── version_tracker.py  # Custom batch CDF tracker
├── research/                   # Architectural decisions & logs
└── future-plans/               # Production migration checklists
```
