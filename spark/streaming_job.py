import os

import psycopg2
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import (
    BooleanType, FloatType, IntegerType, StringType, StructField, StructType,
)

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = "raw.earthquakes"
PG_HOST = os.environ.get("PG_HOST", "postgres")
PG_DB = os.environ.get("PG_DB", "earthquakes")
PG_USER = os.environ.get("PG_USER", "quake")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "quake")
CHECKPOINT_DIR = "/tmp/spark-checkpoint/earthquakes"

EVENT_SCHEMA = StructType([
    StructField("event_id",   StringType()),
    StructField("magnitude",  FloatType()),
    StructField("place",      StringType()),
    StructField("event_time", StringType()),
    StructField("latitude",   FloatType()),
    StructField("longitude",  FloatType()),
    StructField("depth_km",   FloatType()),
    StructField("alert",      StringType()),
    StructField("tsunami",    BooleanType()),
    StructField("sig",        IntegerType()),
    StructField("mag_type",   StringType()),
    StructField("title",      StringType()),
])

spark = SparkSession.builder \
    .appName("EarthquakeStreaming") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

raw_stream = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
    .option("subscribe", TOPIC)
    .option("startingOffsets", "earliest")
    .option("failOnDataLoss", "false")
    .load()
)

parsed = (
    raw_stream
    .select(from_json(col("value").cast("string"), EVENT_SCHEMA).alias("d"))
    .select("d.*")
    .withColumn("event_time", col("event_time").cast("timestamp"))
    .filter(col("event_id").isNotNull())
    .filter(col("magnitude").isNotNull())
)


def write_batch(batch_df, batch_id: int) -> None:
    total = batch_df.count()
    print(f"Batch {batch_id}: raw count from Kafka = {total}")

    if total == 0:
        return

    # Show first row to verify parsing
    batch_df.show(1, truncate=False)

    rows = batch_df.collect()
    valid = [r for r in rows if r.event_id is not None and r.magnitude is not None]
    print(f"Batch {batch_id}: {len(valid)}/{total} rows passed null filter")

    if not valid:
        return

    conn = psycopg2.connect(
        host=PG_HOST, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )
    try:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO raw.earthquakes
                    (event_id, magnitude, place, event_time,
                     latitude, longitude, depth_km,
                     alert, tsunami, sig, mag_type, title)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (event_id) DO NOTHING
                """,
                [
                    (
                        r.event_id, r.magnitude, r.place, r.event_time,
                        r.latitude, r.longitude, r.depth_km,
                        r.alert, r.tsunami, r.sig, r.mag_type, r.title,
                    )
                    for r in valid
                ],
            )
        conn.commit()
        print(f"Batch {batch_id}: {len(valid)} events committed → raw.earthquakes")
    except Exception as exc:
        conn.rollback()
        print(f"Batch {batch_id}: DB write FAILED: {exc}")
        raise
    finally:
        conn.close()


query = (
    parsed.writeStream
    .foreachBatch(write_batch)
    .option("checkpointLocation", CHECKPOINT_DIR)
    .trigger(processingTime="30 seconds")
    .start()
)

query.awaitTermination()
