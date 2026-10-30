# Vocab Sensei

Learn the words of your next read before you read them.

Upload a book (EPUB / PDF / TXT). Vocab Sensei pulls out the harder words chapter by chapter and quizzes you on them
every day, starting with the chapter you're about to read. When you get there, you already know the words.

- Full plan: [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md)
- Status: Phase 1 in progress, see [docs/PROGRESS.md](docs/PROGRESS.md)

## Run it locally

Once, download the dictionary (Open English WordNet, ~125 MB, about a minute):
`cd backend && uv run python -m app.dictionary.install`.

Then three terminals (Python 3.12 via [uv](https://docs.astral.sh/uv/), Node 24, `brew install mailpit`):

```bash
mailpit                                                        # 1. catches emails: http://localhost:8025
cd backend && uv run alembic upgrade head && uv run uvicorn app.main:app --reload   # 2. API on :8000
cd frontend && npm ci && npm run dev                           # 3. app: http://localhost:5173
```

Create an account in the app, open the verification email in Mailpit, then log in.

## Stack
Python (FastAPI, spaCy, wordfreq, WordNet) · SQLite → PostgreSQL · React + Vite + TypeScript. All free & open source.

## License
MIT
