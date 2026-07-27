FROM python:3.12-slim AS base

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" || pip install --no-cache-dir .

COPY . .

RUN adduser --disabled-password --gecos "" appuser && \
    mkdir -p /workspaces && \
    chown -R appuser:appuser /app /workspaces

USER appuser

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
