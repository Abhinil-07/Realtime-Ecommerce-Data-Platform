from pyspark.sql.functions import col, current_timestamp

# landing_df = kafka_df.select(
#     col("key"),
#     col("value").cast("string").alias("value"),     # Kafka value is binary, cast to string
#     col("topic"),
#     col("partition"),
#     col("offset"),
#     col("timestamp").alias("kafka_timestamp"),       # Kafka's own timestamp
#     current_timestamp().alias("landing_ingest_ts")   # When we ingested it
# )

def transform_landing(kafka_df):
    
    return kafka_df.select(
        col("key").cast("string").alias("key"),
        col("value").cast("string").alias("value"),
        col("topic"),
        col("partition"),
        col("offset"),
        col("timestamp").alias("kafka_timestamp"),
        current_timestamp().alias("landing_ingest_ts")

    )