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

## Accounts and email

Email + password login with cookie sessions (`/api/auth/*`: register, verify-email, resend-verification, login,
logout, me, forgot-password, reset-password). Passwords are Argon2 hashes; session and email tokens are stored as
SHA-256 hashes only.

Emails are sent over SMTP. Locally, run [Mailpit](https://mailpit.axllent.org) (FOSS) to catch them:

```bash
brew install mailpit
mailpit                     # SMTP on :1025, inbox UI at http://localhost:8025
```

To send real email later, copy `.env.example` to `.env` and fill in an SMTP account (e.g. a Gmail app password).
