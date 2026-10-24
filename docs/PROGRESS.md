# Progress & Session Notes

Living log of what's built and where to pick up. Update it at the end of every session.

- Plan: [PROJECT_PLAN.md](PROJECT_PLAN.md) · Architecture: [ARCHITECTURE.md](ARCHITECTURE.md) ·
  Git workflow: [../CONTRIBUTING.md](../CONTRIBUTING.md)
- Repo: https://github.com/neeraj2681/vocab-sensei (public, `main` protected)

---

## ▶ Start here next session

**Phase 1 (MVP), step 2: get from an uploaded book to a word list.** Suggested order, one branch each:

| # | Branch | What | Notes |
|---|--------|------|-------|
| 1 | `feat/pdf-txt-parser` | `PdfParser`, `TxtParser` behind the existing `DocumentParser` protocol; register them in `extraction/registry.py` | PDF: `pypdf` (BSD) or `pdfminer.six` (MIT); chapters from the PDF outline, else heading heuristics. Scanned PDF (no text) → `ParseError("scanned PDFs aren't supported yet")`. TXT: split on "CHAPTER …" style headings, else one chapter. |
| 2 | `feat/upload` | `POST /api/documents` (multipart), list/get/delete own documents | Save file under `data/uploads/<user_id>/`, create `Document` + `Chapter` rows, status `processing → ready / failed`. Validate type + size. Needs `python-multipart`. Only the owner can see a document. |
| 3 | `feat/word-extraction` | spaCy lemmatize + POS, drop stopwords/PROPN/numbers, `wordfreq` Zipf < ~4.0, context sentence | Pure module in `extraction/`; writes `words` + `document_words` via a service. **Filter Project Gutenberg header/license sections.** Run it as part of upload. |
| 4 | `feat/dictionary` | Open English WordNet via `wn`; fill `definitions` | Keep only words that have a definition. Attribution (CC BY 4.0) on an About page. |
| 5 | `feat/library-ui` | Upload page, my books list, current-reading chooser with priority | Frontend, can start in parallel with 3–4 once 2 is merged. |

After that: learning list ordering, triage screen, quiz engine (`QuestionGenerator` + WordNet distractors), quiz UI, progress page. See the Phase 1 checklist in the plan.

**First steps in the session:**

```bash
cd ~/vocab_sensei && git switch main && git pull
git worktree add ../vocab_sensei-pdf -b feat/pdf-txt-parser
git worktree add ../vocab_sensei-upload -b feat/upload
```

A real test book is handy: Project Gutenberg *Moby-Dick* EPUB (`https://www.gutenberg.org/ebooks/2701.epub3.images`)
parses into 142 sections. Use a Gutenberg PDF/TXT of the same book for the new parsers.

---

## ✅ Done so far (as of 24 Oct 2026)

### Phase 0: setup (complete)
| PR | What |
|----|------|
| #1 | Git workflow guide, architecture doc, pre-commit hooks, CI |
| #2 | MVP decisions recorded in the plan |
| #3 | Backend skeleton: FastAPI, SQLAlchemy 2, Alembic, ruff, mypy `--strict`, import-linter, pytest |
| #4 | Frontend skeleton: React 19 + TS strict, Vite, ESLint (strict type-checked), Prettier, Vitest |
| #5 | Plan: LLM-generated questions as Phase 5 |

### Phase 1: MVP (in progress)
| PR | What |
|----|------|
| #6 | `scoring/rules.py`: +5 / −10, floor 0, learned at 100, −5 per full week (lazy decay), triage start scores |
| #7 | All 13 DB tables + initial migration (users, auth_sessions, email_tokens, documents, chapters, words, definitions, document_words, current_readings, user_words, quiz_sessions, questions, quiz_answers) |
| #8 | Accounts API: register, verify-email, resend, login, logout, me, forgot/reset password |
| #9 | EPUB 2/3 parser, chapters cut at table-of-contents anchors |
| #10 | Frontend auth pages + React Router + `AuthProvider` |

**Test counts:** backend 70 tests (~99% coverage), frontend 16 tests. CI: 3 required jobs
(Pre-commit checks, Backend checks, Frontend checks).

### What works end to end today
Sign up in the browser → verification email (caught by Mailpit) → verify → log in → home page → log out.
Books can be parsed (EPUB) in code but can't be uploaded yet.

---

## 🧭 Decisions made (don't re-litigate)

| Topic | Decision |
|-------|----------|
| Tools | Free & open source only; prefer the most popular option (ESLint over oxlint) |
| Repo | Public GitHub (branch protection is free only for public repos) |
| Git | One branch per feature, worktrees for parallel work, squash-merge PRs, Conventional Commits, no direct commits to `main` |
| Attribution | Commits/PRs carry **no** Claude co-author lines; the user is the sole author |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, uv |
| DB | SQLite now, PostgreSQL in Phase 3 |
| Frontend | React 19 + TypeScript + Vite, React Router, desktop first |
| Auth | Email + password (Argon2id), email verification required, password reset by email, httpOnly cookie sessions (not JWT) |
| Email | SMTP; Mailpit locally; Gmail SMTP (app password) later, see `backend/.env.example` |
| Reading | Several current reads, ordered by priority |
| Quiz | Rounds of 10; first round per day = daily goal/streak; "I know this" button |
| Triage | Optional after upload: Known / Unsure (starts at 50) / New (0) |
| PDFs | Text PDFs only in MVP; OCR in Phase 2 |
| EPUB | No `ebooklib` (AGPL); zipfile + BeautifulSoup/lxml |
| LLM | Phase 5, local via Ollama by default; MVP already has the `QuestionGenerator` seam and a `questions` table |

---

## ⚠️ Known issues / tech debt

- Tests print a Starlette deprecation warning (`httpx` → `httpx2`). Harmless. Swapping it was blocked in-session because
  the package couldn't be verified; revisit.
- No login rate limiting yet (needed before exposing the app on the internet).
- Emails are sent inside the request (synchronous SMTP, 10 s timeout); move to a background task if slow.
- Gutenberg boilerplate (header, license) comes out as chapters; filter it in word extraction or upload.
- Alembic's migration template leaves a trailing space after `Revises:`; the pre-commit hook fixes it on commit.

---

## 🛠 Environment notes

- Tools installed with Homebrew: `gh` (logged in as `neeraj2681` with the `workflow` scope), `pre-commit`, `mailpit`.
  `uv` and Node 24 were already there. Docker is **not** installed.
- Run locally: see the README (Mailpit, backend on :8000, frontend on :5173 with an `/api` proxy).
- `pre-commit install` was run in the main clone; new worktrees share the same hooks.
