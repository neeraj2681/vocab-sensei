# Vocab Sensei

Book-based vocabulary learner: upload a book, learn its harder words chapter by chapter through daily quizzes.

**At the start of a session, read `docs/PROGRESS.md`** ("Start here next session"), then `docs/PROJECT_PLAN.md` as
needed. Update `docs/PROGRESS.md` at the end of a session.

## Working agreements
- The user is learning git: briefly explain git commands and concepts as you use them.
- One branch per change (`feat/`, `fix/`, `chore/`, `docs/`, `refactor/`, `test/`), parallel work in worktrees
  (`../vocab_sensei-<name>`), PR into `main`, squash merge after CI passes. Never commit to `main`.
- Rebase on `origin/main` before merging (branch must be up to date); push rebased branches with `--force-with-lease`.
- Conventional Commits. **No Claude attribution**: no `Co-Authored-By`/`Claude-Session` trailers, no
  "Generated with Claude Code" in PRs.
- Free & open-source tools only; prefer the most popular option; flag licences (avoid AGPL deps, e.g. `ebooklib`).
- Ask before decisions that shape the data model or user experience; give a recommended option.

## Layout
- `backend/`: FastAPI (Python 3.12, uv). Layers: `api` → `services` → domain (`extraction`, `dictionary`, `quiz`,
  `scoring`) → `repositories` → `db` → `core`. Domain modules are pure (no FastAPI/SQLAlchemy); import-linter enforces it.
- `frontend/`: React 19 + TS + Vite. `src/api/` is the only place that calls the backend; features in `src/features/<name>/`.
- `docs/`: plan, architecture, progress.

## Commands
```bash
# backend (from backend/)
uv run ruff format . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest
uv run alembic revision --autogenerate -m "..."   # after model changes; CI runs `alembic check`
uv run uvicorn app.main:app --reload

# frontend (from frontend/)
npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
npm run dev

# everything at once (repo root)
pre-commit run --all-files
```

Local email: `mailpit` (SMTP :1025, inbox http://localhost:8025).
