# Vocab Sensei backend

FastAPI service. Layering rules: [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

## Run locally

```bash
cd backend
uv sync                              # create .venv and install deps from uv.lock
uv run alembic upgrade head          # create / migrate data/vocab_sensei.db
uv run uvicorn app.main:app --reload # http://localhost:8000/api/health, docs at /docs
```

## Checks (same as CI)

```bash
uv run ruff format . && uv run ruff check .
uv run mypy
uv run lint-imports   # architecture layer contracts
uv run pytest
```

## Settings

Environment variables with the `VOCAB_` prefix (or a `backend/.env` file), nested with `__`:

```bash
VOCAB_DATABASE_URL=sqlite:///path/to/db.sqlite
VOCAB_SCORING__CORRECT_DELTA=5
VOCAB_QUIZ__ROUND_SIZE=10
```
