FROM python:3.11-slim AS base

WORKDIR /app

# System dependencies for asyncpg
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY app/ app/
RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir asyncpg slowapi

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
