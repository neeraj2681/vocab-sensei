# Progress & Session Notes

Living log of what's built and where to pick up. Update it at the end of every session.

- Plan: [PROJECT_PLAN.md](PROJECT_PLAN.md) · Architecture: [ARCHITECTURE.md](ARCHITECTURE.md) ·
  Git workflow: [../CONTRIBUTING.md](../CONTRIBUTING.md)
- Repo: https://github.com/neeraj2681/vocab-sensei (public, `main` protected)

---

## ▶ Start here next session

**The user is testing the app for a few days** (from 31 Oct 2026). Ask how testing went and fix what they found
before starting anything new. The friends' stack runs in Docker on the user's Mac (Colima, starts at login) with
real email (Gmail SMTP), daily database backups and 8 built-in classics; it is reachable through a Cloudflare
**Tailscale Funnel** at a fixed address, https://neerajs-macbook-air.tail8cd657.ts.net (see
[../deploy/README.md](../deploy/README.md)).

Open items:
- **Mac must stay awake** while friends use it (user step: Battery → Options → prevent automatic sleeping).
- **Next work after testing** (ask): Phase 2 leftovers (difficulty setting per user, FSRS option, OCR for scanned
  PDFs), Phase 4 (recommendations, ready-made lists), Phase 5 (LLM-generated questions with a local model).

**First steps in the session:**

```bash
cd ~/vocab_sensei && git switch main && git pull
colima start                               # if the Mac rebooted
cd deploy && docker compose up -d --build  # the friends' stack (PostgreSQL) on http://localhost:8080
tailscale funnel status                 # the public address (fixed); Tailscale app must be running
```

For development, the old SQLite demo still works: `~/vocab_sensei-demo-data` (`e2e@example.com` /
`correct horse battery`), backend on :8000 + Vite on :5173.

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

### Phase 3: share with friends (code done)
| PR | What |
|----|------|
| #26 | Auth emails sent after the response: sign-up no longer fails when SMTP is down |
| #27 | Rate limits (limits library): logins 10/min, email-sending endpoints 5/hour; Cloudflare-aware client address |
| #28 | Delete your account (password check) with books, files and progress |
| #29 | PostgreSQL support (psycopg 3); CI runs all tests + migrations on PostgreSQL 17 |
| #30 | Docker Compose: PostgreSQL + API + Caddy, cloudflared tunnel profiles, deploy guide, CI starts the stack |
| #31 | Longer uv download timeout for image builds on slow connections |

Required CI checks on `main`: Pre-commit, Backend, Frontend, Backend on PostgreSQL, Docker deploy.

### Phase 2: better learning (in progress)
| PR | What |
|----|------|
| #33 | Reverse (meaning → word) and fill-in-the-blank (the book's sentence) questions, unlocked by word score: 0–29 meaning, 30–69 + reverse, 70+ + fill-in; the sentence's word form is stored (migration) |
| #34 | Phone layout (tap targets, wrapping, scrolling tables) and installable PWA (vite-plugin-pwa; never caches /api); new app icon |
| #35 | Chapter readiness (average word progress), shown on the book page and current reads; "Study this chapter" focused quiz |
| #37, #38 | Daily reminder by push notification (Web Push, VAPID) or email at a chosen time, only if the day's goal isn't met; Settings page; own service worker |
| #39 | Minimal sepia theme with a warm dark mode and a ☀/☾ toggle (system default, remembered) |
| #40, #41 | 8 built-in Gutenberg classics (no owner, readable by all, seeded on start); new users start on Pride and Prejudice; Classics shelf |
| #42 | Daily database backup (pg_dump, 7 days) in `deploy/backups/`, restore steps in the deploy guide |

**Tests:** backend 331 (99% coverage, also run on PostgreSQL), frontend 87. CI: 5 required jobs.

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
| DB | SQLite for development, PostgreSQL in Docker for friends (both tested in CI) |
| Frontend | React 19 + TypeScript + Vite, React Router, desktop first |
| Auth | Email + password (Argon2id), verification required, reset by email, httpOnly cookie sessions |
| Dictionary | Open English WordNet 2025 via `wn`; ≤3 senses per part of speech; the book's part of speech first |
| Reading | Several current reads, ordered by priority; the learning list starts at the current chapter (earlier chapters left out); books share new words n : n−1 : … : 1 |
| Question types | Formats unlock by word score: meaning (0–29), + reverse (30–69), + fill-in-the-blank from the book's sentence (70+) |
| Readiness | Average progress of a chapter's words; "Study this chapter" = focused endless quiz, says "Chapter ready!" at 100% |
| Quiz | **Never-ending** (no rounds). 4 options; spacing 10 questions (early repeats don't score); pools new/learning/review 6:3:1; feedback with the book's sentence after each answer |
| Score | Lifetime points at the top: +5 / −10 on every counted answer, total floored at 0; word scores separately (+5 / −10, floor 0, learned at 100, −5/week decay) |
| Daily goal | 10 answers a day keeps the streak (user's time zone) |
| Sorting | Optional, one card at a time, from a button (book page / current reads): Known (never quizzed), Unsure (50), New (0); changeable until answered |
| Progress | Profile menu → Progress page; graph of lifetime points after every answer |
| Backup | JSON with progress only (no book files); restore merges |
| Hosting | The user's Mac: Docker via Colima (starts at login), Caddy, Tailscale Funnel at a fixed *.ts.net address (Cloudflare tunnel profiles kept as alternatives); real email via Gmail SMTP app password |
| Reminders | Push (per device) or email, at a chosen local time, only if the daily goal isn't met; at most once a day |
| Look | Sepia light theme + warm dark theme, serif reading text, sans-serif controls |
| Classics | Alice, Sherlock Holmes, Pride and Prejudice, Frankenstein, Dorian Gray, Dracula, Jane Eyre, Moby-Dick; new users auto-start Pride and Prejudice |
| Backups | Nightly pg_dump kept 7 days (deploy/backups); users can also download their own progress |
| Rate limits | Per client address, in memory (single API process): login 10/min + 50/h, emails 5/h |
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

- Tools: `gh` (logged in as `neeraj2681`, `workflow` scope), `pre-commit`, `mailpit`, `colima`, `docker`,
  `docker-compose` via Homebrew; `uv`, Node 24. `~/.docker/config.json` lost a stale Docker Desktop `credsStore`
  (backup next to it).
- Commit with `UV_NO_SYNC=1 git commit …` if the pre-commit hooks try to download the spaCy model and hang.
- If `gh pr create`/`gh pr merge` fail with "GraphQL: Something went wrong", use the REST API via `gh api`.
- WordNet data: ~125 MB in `data/wordnet/` (per data dir); `uv run python -m app.dictionary.install`.
