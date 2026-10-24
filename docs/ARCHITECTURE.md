# Architecture & Code Guidelines

Goal: **modular, clean, robust**. Each module has one job, a small public interface, and tests.

## Layers (backend)

```
api/          HTTP only: request parsing, response models, status codes. No business logic.
  │
services/     Use cases: "upload book", "build learning list", "start quiz", "submit answer".
  │           Orchestrates domain modules + repositories.
  │
domain modules (pure Python, no web / no DB imports):
  extraction/   file → chapters → candidate words
  dictionary/   lemma → definitions, POS, synonyms
  quiz/         question selection, distractor generation
  scoring/      score rules, decay, status transitions
  │
repositories/ DB access only (SQLAlchemy). One repository per aggregate.
  │
db/           models, session, Alembic migrations
core/         config (pydantic-settings), logging, shared types
```

**Dependency rule:** arrows point down only. Domain modules never import `api`, `services` or `db`. This keeps
the core logic testable without a server or database, and lets the storage (SQLite → Postgres) or UI change
without touching it.

## Principles
1. **Pure core, thin edges.** Scoring and distractor logic are pure functions: same input → same output, easy to test.
2. **Interfaces at module boundaries.** e.g. `DocumentParser` protocol with `EpubParser`, `PdfParser`, `TxtParser`
   implementations, picked by a registry. Adding DOCX later means adding one class, not editing others.
3. **Configuration over constants.** Scoring numbers (+5 / −10 / 100 / −5 per week), difficulty threshold and quiz size
   live in `core/config.py`, overridable via environment variables.
4. **Type everything.** Full type hints, checked by `mypy --strict` in CI. Pydantic models at the API boundary.
5. **Fail loudly, early.** Validate uploads (type, size), raise specific exceptions, map them to HTTP errors in one place.
6. **Data safety.** Every schema change is an Alembic migration; answer log is append-only; export/backup tested.
7. **Tests mirror the source tree.** Unit tests for domain modules, integration tests for services + DB,
   a few API tests. Target ≥ 80 % coverage on domain modules.

## Tooling (all FOSS)

| Purpose | Tool |
|---------|------|
| Python env & deps | uv |
| Lint + format | ruff |
| Type check | mypy |
| Tests | pytest, pytest-cov |
| Frontend lint/format | ESLint, Prettier |
| Frontend tests | Vitest |
| Git hooks | pre-commit |
| CI/CD | GitHub Actions (free tier) |
| Containers | Docker / Podman, Docker Compose |
