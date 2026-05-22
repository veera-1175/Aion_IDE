FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
COPY noesis/ noesis/
COPY config/ config/
COPY scripts/ scripts/
COPY examples/ examples/

RUN pip install --no-cache-dir -r requirements.txt -e ".[api]"

RUN mkdir -p /app/data

ENV NOESIS_DB=/app/data/noesis.db
EXPOSE 8080 8765

CMD ["python", "scripts/run_server.py", "--host", "0.0.0.0", "--port", "8080"]
