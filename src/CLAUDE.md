# src/ — Module Rules

> All business logic lives here. Notebooks import from here. Nothing in this directory
> should create a SparkSession directly — receive it as a parameter instead.

## Directory Structure
```
src/
  transformations/
    bronze.py          # Landing → Bronze parsing
    silver_base.py     # Bronze → Silver Base (explode, flatten, type casting)
    silver_enriched.py # Silver → SCD2 MERGE logic
    scd2.py            # Generic SCD2 merge function (used by all 4 dims)
    gold_rt.py         # Silver → Gold RT aggregations
    gold_batch.py      # Gold Curated + Gold Batch batch jobs
  utils/
    dlq.py             # DLQ writer (good/bad split, rejection_reason column) — see docs/DATA_QUALITY.md for validation rules and rejection_reason string constants
    secrets.py         # Secret access abstraction (env vars locally, dbutils on Databricks)
    spark.py           # SparkSession factory (detects environment)
    assertions.py      # Gate 2 + Gate 4 pre-write validation functions
    logging.py         # Structured JSON logger setup
  io/
    kafka.py           # Kafka connection config (reads from secrets.py)
    delta.py           # Delta read/write helpers (paths from config)
  tests/
    test_transformations.py
    test_dlq.py
    test_scd2.py
    conftest.py        # pytest fixtures including shared SparkSession
```

## Rules
- Every public function: type hints + docstring with Args/Returns
- No hardcoded paths, table names, or secrets anywhere in src/
- `scd2.py` must be generic — parameterized by business key, trigger columns, target table
- `dlq.py` must accept any DataFrame + validation condition + rejection message
- `secrets.py` must work identically locally (os.environ) and on Databricks (dbutils.secrets)
- `spark.py` must detect environment: if `dbutils` available → return existing session, else create one
- Use Python `logging` module only — no `print()` anywhere. This is a hard production
  requirement, not optional cleanup. `print()` output is lost in Spark executors and
  invisible in Databricks job logs. Structured logging is the only way ops can monitor
  this pipeline in production.
- Log format: `{"job": "...", "layer": "...", "table": "...", "rows_good": N, "rows_dlq": M}`

## Testing Rules
- Mirror `src/` structure in `tests/`
- Use `conftest.py` for a shared SparkSession fixture (scope="session" for performance)
- Test each transformation with: happy path, null PK, invalid business rule, empty batch, schema change
- Run with: `pytest src/tests/ -v`

## Databricks Compatibility Rules
- `spark.py` must NOT call `SparkSession.builder` if running on Databricks
- `secrets.py` must NOT read `.env` on Databricks (use `dbutils.secrets.get`)
- `delta.py` path helpers must build paths from a config dict, not concatenate hardcoded strings
- All table references must go through a central `TABLE_NAMES` config dict in `src/config.py`