# The health API and the migration runner. Built from the repository root.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    PATH="/app/.venv/bin:$PATH" \
    HEALTH_DB_DIR=/app/db \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so source changes do not reinstall them.
COPY pyproject.toml uv.lock ./
COPY api/pyproject.toml api/pyproject.toml
COPY importers importers
RUN uv sync --locked --package health-api --no-dev --no-install-workspace

COPY api api
COPY db db
RUN uv sync --locked --package health-api --no-dev

EXPOSE 8000
CMD ["health-api", "--host", "0.0.0.0", "--port", "8000"]
