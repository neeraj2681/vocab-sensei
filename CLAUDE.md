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

## Agent roles: manager + light workers
Work is split by model strength. Follow your role; if you don't know it, you are the **manager** when the user talks
to you directly, and a **worker** when you were started by another agent with a handoff (below).

- **Manager** (Opus 5.5, `claude-opus-5-5`): turns a request into tasks, writes each task's handoff, makes every
  design, data-model and UX decision (asking the user first, per the working agreements), reviews every diff, merges,
  asks the user before any deploy, and updates `docs/PROGRESS.md`. Does no bulk or mechanical work itself.
- **Worker, Haiku 5.5** (`claude-haiku-5-5`): fully specified, mechanical tasks: tests from a given spec, a migration
  from a given schema, config, copy/docs, fixtures, renames, moving code to a given place, grep audits.
- **Worker, Sonnet 5.5** (`claude-sonnet-5-5`): one module or component against a clear interface.
- **Manager only, never a light worker**: scoring and decay (`app/scoring/`, `app/quiz/selection.py`), wrong-option
  safety (an option that is a synonym makes two answers right), migrations that change existing data, database
  session or pool handling, debugging flaky or failing integration tests, legal/attribution text, anything
  touching `deploy/` or the server. Workers never touch the server.
- Run independent tasks in parallel: one worker per task, each in its own worktree and branch
  (`git worktree add ../vocab_sensei-<name> -b <type>/<name> origin/main`), one PR per task.

### Handoff (manager → worker)
The manager sends one message with exactly these parts; a worker does nothing the handoff doesn't list:
1. **Goal**: two sentences.
2. **Spec**: exact function signatures, types and example input → output.
3. **May touch**: an explicit list of files. **Do not touch**: everything else, always including `app/scoring/`,
   `app/quiz/selection.py`, `deploy/`, `docs/PROJECT_PLAN.md` and migrations that change data.
4. **Acceptance tests**: test names and what they assert (or a fixture path).
5. **Branch/worktree** name.

The worker returns: the PR link, a diff summary by file, the full output of the checks below, any new dependency with
its licence, and open questions as a list. **A worker never guesses**: if the spec is unclear, a decision is needed,
or the change would go beyond the listed files, it stops and asks the manager.

### Checks before handing back (worker) and before merging (manager)
- Backend: `uv run ruff format . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest`,
  plus `uv run alembic check` after model changes. Frontend: `npm run lint && npm run format:check &&
  npm run typecheck && npm test && npm run build`. CI must be green on the PR.
- **Escalate Haiku → Sonnet** when the task turns out to need new logic rather than wiring, or the first attempt
  fails the checks. **Escalate to the manager** after two failed attempts, when a test the worker didn't write fails,
  when the spec is ambiguous, or when the change would reach a "do not touch" file.

Every agent follows the working agreements above: Conventional Commits, no Claude attribution, FOSS-only (no AGPL),
never commit to `main`, explain git briefly, and **no production deploy without the user's explicit approval**.
Current ideas and per-idea task breakdowns: `docs/IDEAS.md`.

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
