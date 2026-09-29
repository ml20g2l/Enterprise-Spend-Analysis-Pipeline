FROM apache/airflow:3.3.2-python3.11

USER root
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential default-libmysqlclient-dev pkg-config \
    && python -m venv /opt/pipeline-venv \
    && chown -R airflow:root /opt/pipeline-venv \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=airflow:root airflow/requirements-pipeline.txt /tmp/requirements-pipeline.txt

USER airflow
RUN /opt/pipeline-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/pipeline-venv/bin/pip install --no-cache-dir -r /tmp/requirements-pipeline.txt \
    && /opt/pipeline-venv/bin/pip check
