# Progress & Session Notes

Living log of what's built and where to pick up. Update it at the end of every session.

- Plan: [PROJECT_PLAN.md](PROJECT_PLAN.md) · Architecture: [ARCHITECTURE.md](ARCHITECTURE.md) ·
  Git workflow: [../CONTRIBUTING.md](../CONTRIBUTING.md)
- Repo: https://github.com/neeraj2681/vocab-sensei (public, `main` protected)

---

## ▶ Start here next session

**The MVP (Phase 1) is complete** as of 31 Oct 2026: upload a book → sort its words → never-ending quiz with a live
score → progress graph → backup. Next is a choice of direction; ask the user:

| Option | What | Why |
|--------|------|-----|
| **A. Phase 3: share with friends** (chosen, in progress) | Login rate limiting, sign-up working without SMTP (done, #26), PostgreSQL, Docker Compose + a deploy target, account deletion | The app is usable daily; friends are the stated next audience |
| B. Phase 2: better learning | Chapter primer + readiness %, fill-in-the-blank questions from the book, mobile layout/PWA, OCR for scanned PDFs | Makes daily use better before inviting others |
| C. Tuning from real use | Stricter difficulty threshold (Loomings has 188 words), sense choice within a part of speech (*spleen*: organ vs anger) | Quality issues seen in real data |

**First steps in the session:**

```bash
cd ~/vocab_sensei && git switch main && git pull
cd backend && uv sync --frozen && uv run alembic upgrade head   # 3 new migrations since session 1
uv run python -m app.dictionary.install                           # once per data dir (already done in ~/vocab_sensei/data)
```

Demo data with a test account lives in `~/vocab_sensei-demo-data` (gitignored copy, outside the repo):
`VOCAB_DATA_DIR=~/vocab_sensei-demo-data VOCAB_DATABASE_URL=sqlite:///$HOME/vocab_sensei-demo-data/demo.db`,
log in as `e2e@example.com` / `correct horse battery`.

---

## ✅ Done so far

### Phase 0: setup (complete except Docker Compose)
| PR | What |
|----|------|
| #1–#5 | Git workflow, architecture doc, pre-commit, CI, backend + frontend skeletons, decisions, LLM phase |

### Phase 1: MVP (complete)
| PR | What |
|----|------|
| #6 | Scoring rules: +5 / −10, floor 0, learned at 100, lazy weekly decay, triage start scores |
| #7 | All DB tables + initial migration |
| #8, #10 | Accounts API and pages: register, verify email, log in/out, password reset |
| #9 | EPUB 2/3 parser, chapters cut at table-of-contents anchors |
| #11 | Progress notes, CLAUDE.md |
| #12 | Upload (multipart, 50 MB), background processing, Gutenberg boilerplate stripped |
| #13 | Word extraction: spaCy lemmas + POS, wordfreq Zipf 1.0–4.0, context sentence |
| #14 | Open English WordNet 2025 definitions (`wn`, CC BY 4.0); words without a definition dropped |
| #15 | Library page, current reads with priorities and chapter, chapter-by-chapter word view |
| #16 | Part of speech per book word; matching definitions first ("damp" → "slightly wet") |
| #17 | Learning list: current chapter onward, books mixed 3:2:1 by priority; "Up next" panel |
| #18 | Quiz engine: never-ending questions, synonym-free distractors of similar length, spacing 10, pools 6:3:1, stats, history |
| #19 | Quiz page: live score with +5/−10 pops, sparkline, streak, Today x/10, keys 1–4 / Enter, "I know this" |
| #20 | Profile menu → Progress page: tiles + Recharts graph of lifetime points per answer, table view |
| #21 | Every wrong answer takes 10 off the lifetime total (word scores keep their floor) |
| #22 | Sorting a book's words one card at a time: Known / Unsure / New (K/U/N, undo) |
| #23 | PDF (pypdf; bookmarks or headings, scanned rejected) and TXT parsers; contents lists skipped |
| #24 | Backup: download progress as JSON, merge-restore (keyed by word and book title) |

**Tests:** backend 257 (99% coverage), frontend 63. CI: 3 required jobs.

### What works end to end today
Sign up → verify → upload an EPUB / PDF / TXT → book ready in ~20 s with chapters and ~6,700 defined words →
start reading, set the chapter → optionally sort words → Quiz (endless, live score) → Progress graph → backup.

---

## 🧭 Decisions made (don't re-litigate)

| Topic | Decision |
|-------|----------|
| Tools | Free & open source only; prefer the most popular option (ESLint over oxlint, Recharts for charts) |
| Repo | Public GitHub (branch protection is free only for public repos) |
| Git | One branch per feature, worktrees for parallel work, squash-merge PRs, Conventional Commits, no direct commits to `main` |
| Attribution | Commits/PRs carry **no** Claude co-author lines or "Generated with" footers; the user is the sole author |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, uv |
| DB | SQLite now, PostgreSQL in Phase 3 |
| Frontend | React 19 + TypeScript + Vite, React Router, desktop first |
| Auth | Email + password (Argon2id), verification required, reset by email, httpOnly cookie sessions |
| Dictionary | Open English WordNet 2025 via `wn`; ≤3 senses per part of speech; the book's part of speech first |
| Reading | Several current reads, ordered by priority; the learning list starts at the current chapter (earlier chapters left out); books share new words n : n−1 : … : 1 |
| Quiz | **Never-ending** (no rounds). 4 options; spacing 10 questions (early repeats don't score); pools new/learning/review 6:3:1; feedback with the book's sentence after each answer |
| Score | Lifetime points at the top: +5 / −10 on every counted answer, total floored at 0; word scores separately (+5 / −10, floor 0, learned at 100, −5/week decay) |
| Daily goal | 10 answers a day keeps the streak (user's time zone) |
| Sorting | Optional, one card at a time, from a button (book page / current reads): Known (never quizzed), Unsure (50), New (0); changeable until answered |
| Progress | Profile menu → Progress page; graph of lifetime points after every answer |
| Backup | JSON with progress only (no book files); restore merges |
| PDFs | Text PDFs only; OCR in Phase 2 |
| EPUB | No `ebooklib` (AGPL); zipfile + BeautifulSoup/lxml |
| LLM | Phase 5, local via Ollama by default; `QuestionGenerator` protocol and stored questions are ready |

---

## ⚠️ Known issues / tech debt

- Tests print a Starlette deprecation warning (`httpx` → `httpx2`); installing `httpx2` was blocked in-session.
- Many words per chapter (Loomings: 188). Sorting helps; a stricter Zipf threshold (≈3.5) is worth trying.
- Within a part of speech, WordNet's first sense isn't always the book's (*spleen*: organ vs anger) → LLM phase.
- The CSS is one global `index.css`; fine for now, revisit if the UI grows.

---

## 🛠 Environment notes

- Tools: `gh` (logged in as `neeraj2681`, `workflow` scope), `pre-commit`, `mailpit` via Homebrew; `uv`, Node 24.
  Docker is **not** installed.
- Commit with `UV_NO_SYNC=1 git commit …` if the pre-commit hooks try to download the spaCy model and hang.
- If `gh pr create`/`gh pr merge` fail with "GraphQL: Something went wrong", use the REST API via `gh api`.
- WordNet data: ~125 MB in `data/wordnet/` (per data dir); `uv run python -m app.dictionary.install`.
