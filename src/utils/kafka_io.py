# kafka_df = (
#     spark.readStream
#     .format("kafka")
#     .option(
#         "kafka.bootstrap.servers",
#         "pkc-921jm.us-east-2.aws.confluent.cloud:9092"
#     )
#     .option("kafka.security.protocol", "SASL_SSL")
#     .option("kafka.sasl.mechanism", "PLAIN")
#     .option(
#         "kafka.sasl.jaas.config",
#         "org.apache.kafka.common.security.plain.PlainLoginModule required "
#         "username='XUVDS246PHDWGIVJ' "
#         "password='cflt04rhDXHY/n4denCZpYZoHFc6G0l7rRGNrsT3DMY/LaKNkIlTwLUdvP0HMdaw';"
#     )
#     .option("subscribe", "orders") 
#     .option("startingOffsets", "earliest")
#     .load()
# )
 
def read_kafka_stream(
    spark,
    bootstrap_servers,
    topic,
    username,
    password,
    starting_offsets,
    **options
):
    """
    Creates a Spark DataFrame reading from a Confluent Kafka topic.
    Handles SASL_SSL authentication automatically.
     Args:
        spark: SparkSession object
        bootstrap_servers (str): The Kafka broker connection string
        topic (str): The name of the Kafka topic to subscribe to
        username (str): Confluent API Key
        password (str): Confluent API Secret
        starting_offsets (str): 'earliest' or 'latest'. Default is 'earliest'.
        **options: Any additional native Kafka Spark options (e.g., maxOffsetsPerTrigger=1000)
    """


    jass_config =(
        f"org.apache.kafka.common.security.plain.PlainLoginModule required "
        f"username='{username}' "
        f"password='{password}';"
    )

    stream_reader =(
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers",bootstrap_servers)
        .option("subscribe",topic)
        .option("kafka_security_protocols","SASL_SSL")
        .option("kafka_sasl_mechanism","PLAIN")
        .option("kafka_sasl_jaas_config",jass_config)
        .option("startingOffsets",starting_offsets)
        .load()
    )

    return stream_reader.options(**options).load()
    


