# HY562 / CS-562 Big Data Processing & Analytics - Fall 2026
# Student lab image: Python 3.12 + OpenJDK 17 + PySpark 4.2.0 + JupyterLab (+ Qiskit for Lab 5)
#
# Build & run through docker-compose (recommended):   docker compose up -d --build
# Stand-alone:  docker build -t hy562/spark-lab:2026 .
#               docker run -p 8888:8888 -p 4040:4040 -v "$PWD/..:/home/jovyan/work" hy562/spark-lab:2026

# bookworm is pinned on purpose: Debian 13 (trixie) no longer ships openjdk-17.
FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.title="hy562-spark-lab" \
      org.opencontainers.image.description="CS-562 Fall 2026 lab environment (Spark 4.2.0, Java 17, JupyterLab)"

ARG NB_USER=jovyan
ARG NB_UID=1000
ARG SPARK_VERSION=4.2.0
ARG KAFKA_CONNECTOR=org.apache.spark:spark-sql-kafka-0-10_2.13:4.2.0

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk \
    SPARK_CONF_DIR=/opt/spark-conf \
    PYSPARK_PYTHON=python3 \
    PYSPARK_DRIVER_PYTHON=python3 \
    SPARK_KAFKA_PACKAGE=${KAFKA_CONNECTOR} \
    KAFKA_BOOTSTRAP=kafka:9092

# Java 17 runtime (Spark 4.x requires Java 17 or 21), procps (Spark launch scripts use `ps`), tini as PID 1
RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps tini curl ca-certificates \
 && ln -s "$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")" /usr/lib/jvm/java-17-openjdk \
 && rm -rf /var/lib/apt/lists/*

# Python stack used by the labs
RUN pip install \
        "pyspark==${SPARK_VERSION}" \
        "jupyterlab>=4.2,<5" \
        "pandas>=2.2,<3" \
        "pyarrow>=17" \
        "numpy>=2" \
        matplotlib \
        networkx \
        kafka-python \
        "qiskit>=2.0" \
        "qiskit-aer>=0.17"
# GraphFrames is optional in this course and not installed (use networkx / DataFrame joins instead).

# Spark defaults: Kafka connector for Structured Streaming, local UI on 4040
COPY conf/spark-defaults.conf ${SPARK_CONF_DIR}/spark-defaults.conf

RUN useradd -m -s /bin/bash -u ${NB_UID} ${NB_USER} \
 && mkdir -p /home/${NB_USER}/work \
 && chown -R ${NB_USER}:${NB_USER} /home/${NB_USER}

USER ${NB_USER}
WORKDIR /home/${NB_USER}/work

# Pre-fetch the Kafka connector (and its dependencies) into ~/.ivy2 so notebooks start offline.
# Non-fatal: if the build machine has no Maven access the jars are downloaded on first use instead.
RUN python -c "from pyspark.sql import SparkSession; s=SparkSession.builder.master('local[1]').getOrCreate(); print('Spark', s.version); s.stop()" \
    || echo "WARNING: could not pre-fetch ${KAFKA_CONNECTOR}; it will be downloaded at first SparkSession start"

EXPOSE 8888 4040

ENTRYPOINT ["/usr/bin/tini", "--"]
# Token is taken from $JUPYTER_TOKEN (set in docker-compose.yml); default below if run stand-alone.
CMD ["sh", "-c", "jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --ServerApp.root_dir=/home/jovyan/work --IdentityProvider.token=${JUPYTER_TOKEN:-hy562}"]
