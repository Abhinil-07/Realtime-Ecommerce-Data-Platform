---
name: databricks-migration-check
description: >
  Guardrail skill that ensures code is Databricks-compatible. Use this skill whenever
  touching file paths, secrets, SparkSession creation, table names, or any infrastructure
  code. Also trigger when the user mentions Databricks, Azure, Unity Catalog, abfss://,
  dbutils, migration, or is writing code that hardcodes paths like /opt/spark-data/,
  reads secrets from os.environ, creates SparkSession manually, or uses 2-level table
  names. This skill prevents patterns that would break during the Databricks migration.
---

# Databricks Migration Check

This project will migrate from local Docker to Databricks on Azure. This skill ensures
every piece of code written today is migration-ready by catching the "Big Four" patterns
that will change.

## The Big Four

### 1. Storage Paths
| Current (Docker) | Target (Databricks) |
|---|---|
| `/opt/spark-data/landing/` | `abfss://medallion@<storage>.dfs.core.windows.net/landing/` |
| `/opt/spark-data/bronze/` | `abfss://medallion@<storage>.dfs.core.windows.net/bronze/` |

**Rule**: Never hardcode paths. Always read from a config object or environment variable.
```python
# BAD
df.write.save("/opt/spark-data/delta/silver/customer_dim")

# GOOD
from src.utils.config import get_path
df.write.save(get_path("silver", "customer_dim"))
```

### 2. Secrets
| Current | Target |
|---|---|
| `.env` + `os.environ["KAFKA_API_KEY"]` | `dbutils.secrets.get(scope="kafka", key="api-key")` |

**Rule**: Abstract behind `src/utils/secrets.py` with a `get_secret(key)` helper.
```python
# BAD
api_key = os.environ["KAFKA_API_KEY"]

# GOOD
from src.utils.secrets import get_secret
api_key = get_secret("kafka_api_key")
```

### 3. Table Names
| Current (2-level) | Target (Unity Catalog 3-level) |
|---|---|
| `silver_enriched.customer_dim` | `prod_catalog.silver_enriched.customer_dim` |

**Rule**: All table names from a config dict, never hardcoded inline.
```python
# BAD
spark.sql("SELECT * FROM silver_enriched.customer_dim")

# GOOD
from src.utils.config import get_table
spark.sql(f"SELECT * FROM {get_table('silver_enriched', 'customer_dim')}")
```

### 4. SparkSession
| Current | Target |
|---|---|
| `SparkSession.builder...getOrCreate()` | Auto-provided by Databricks |

**Rule**: Wrap in `src/utils/spark.py` with `get_spark()` that detects the environment.
```python
# BAD — in notebook
spark = SparkSession.builder.master("spark://...").getOrCreate()

# GOOD
from src.utils.spark import get_spark
spark = get_spark()
```

## What Does NOT Change
- Delta Lake format — fully supported
- All Spark Structured Streaming logic — identical API
- DLQ pattern — same good/bad split
- SCD2 MERGE logic — identical SQL
- Watermarking and window aggregations — identical API

## Quick Checklist

When reviewing any code, check for:
- [ ] No literal `/opt/spark-data/` paths
- [ ] No `os.environ` for secrets
- [ ] No inline table name strings like `"silver_enriched.X"`
- [ ] No manual `SparkSession.builder`
- [ ] All abstracted behind `src/utils/` helpers
