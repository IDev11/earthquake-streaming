FROM apache/spark:3.5.1-python3
USER root

RUN pip install --no-cache-dir psycopg2-binary==2.9.9

# Download connector JARs directly into Spark's classpath dir (no --packages needed at runtime)
RUN apt-get update && apt-get install -y --no-install-recommends wget && rm -rf /var/lib/apt/lists/* && \
    cd /opt/spark/jars && \
    wget -q "https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.1/spark-sql-kafka-0-10_2.12-3.5.1.jar" && \
    wget -q "https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.1/spark-token-provider-kafka-0-10_2.12-3.5.1.jar" && \
    wget -q "https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.4.1/kafka-clients-3.4.1.jar" && \
    wget -q "https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar" && \
    wget -q "https://repo1.maven.org/maven2/org/lz4/lz4-java/1.8.0/lz4-java-1.8.0.jar" && \
    wget -q "https://repo1.maven.org/maven2/org/xerial/snappy/snappy-java/1.1.10.3/snappy-java-1.1.10.3.jar" && \
    wget -q "https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.3/postgresql-42.7.3.jar"

COPY streaming_job.py /app/streaming_job.py
ENV PATH="/opt/spark/bin:${PATH}"
CMD ["spark-submit", "--master", "local[2]", "--conf", "spark.sql.shuffle.partitions=4", "/app/streaming_job.py"]
