# The API: FastAPI + spaCy + WordNet. Built by deploy/compose.yaml.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.7.13 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    VOCAB_DATA_DIR=/data

WORKDIR /app
# Dependencies first, so code changes don't reinstall them (Docker caches this layer).
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY alembic.ini ./
COPY app ./app

RUN useradd --create-home vocab && mkdir -p /data && chown vocab /data
USER vocab
EXPOSE 8000

# Migrate, fetch WordNet into the data volume the first time, then serve. One process on
# purpose: rate-limit counts live in memory.
CMD ["sh", "-c", "alembic upgrade head && python -m app.dictionary.install && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*'"]
