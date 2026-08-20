# Build stage
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY openmeteo_reader ./openmeteo_reader
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY openmeteo_reader ./openmeteo_reader

ENTRYPOINT ["/app/.venv/bin/python", "-m", "openmeteo_reader"]
CMD ["main"]
