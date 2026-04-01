
def write_stream_table(
    df, 
    query_name, 
    checkpoint_path, 
    table_name, 
    output_mode="append", 
    trigger_time="10 seconds", 
    **options
):
    """
    Writes a streaming DataFrame natively to a catalog table.
    Accepts extra dynamic Delta options.
    """
    return (
        df.writeStream
        .format("delta")
        .queryName(query_name)
        .outputMode(output_mode)
        .option("checkpointLocation", checkpoint_path)
        .trigger(processingTime=trigger_time)
        .options(**options)
        .toTable(table_name)
    )
