"""
Shared utility functions for Silver Enriched SCD2 batch jobs.
Used by: customer_dim, product_dim, store_dim, delivery_partner_dim notebooks.
"""


def get_last_processed_version(spark, job_name):
    """
    Read the last processed Bronze version from the batch_job_tracker Delta table.
    Returns None if this is the first run for the given job.
    """
    result = spark.sql(f"""
        SELECT last_processed_version 
        FROM silver_enriched.batch_job_tracker
        WHERE job_name = '{job_name}'
        ORDER BY run_timestamp DESC
        LIMIT 1
    """).collect()
    return result[0][0] if result else None


def save_last_processed_version(spark, job_name, version, rows):
    """
    Save the current Bronze version to the batch_job_tracker Delta table.
    Creates an audit trail of every batch run.
    """
    spark.sql(f"""
        INSERT INTO silver_enriched.batch_job_tracker
        VALUES ('{job_name}', {version}, current_timestamp(), {rows})
    """)
    print(f"Saved bookmark → job: {job_name}, version: {version}, rows: {rows}")


def read_bronze_cdf(spark, last_version):
    """
    Read Bronze table using Change Data Feed.
    First run (last_version=None): reads entire table.
    Subsequent runs: reads only new changes since last_version.
    Returns empty DataFrame if no new data exists.
    """
    if last_version is None:
        print("First run: reading entire Bronze table...")
        return spark.read.format("delta").load("/opt/spark-data/delta/bronze/orders_raw")
    else:
        # Check if there are actually new versions to read
        current_version = get_current_bronze_version(spark)
        if last_version >= current_version:
            print(f"No new data. Bronze is still at version {current_version}.")
            return spark.createDataFrame([], spark.read.format("delta").load("/opt/spark-data/delta/bronze/orders_raw").schema)
        
        print(f"Reading Bronze changes from version {last_version + 1} to {current_version}...")
        return (
            spark.read.format("delta")
            .option("readChangeFeed", "true")
            .option("startingVersion", last_version + 1)
            .load("/opt/spark-data/delta/bronze/orders_raw")
        )


def get_current_bronze_version(spark):
    """Get the latest version number of the Bronze table."""
    return spark.sql("DESCRIBE HISTORY bronze.orders_raw LIMIT 1").select("version").collect()[0][0]
