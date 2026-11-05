# Progress & Session Notes

Living log of what's built and where to pick up. Update it at the end of every session.

- Plan: [PROJECT_PLAN.md](PROJECT_PLAN.md) · Architecture: [ARCHITECTURE.md](ARCHITECTURE.md) ·
  Git workflow: [../CONTRIBUTING.md](../CONTRIBUTING.md)
- Repo: https://github.com/neeraj2681/vocab-sensei (public, `main` protected)

---

## ▶ Start here next session

**Friends are testing the app** (since 1 Nov 2026). Ask what they found and fix it before new work.
The stack runs in Docker on the user's Mac (Colima, starts at login) with real email (Gmail SMTP), daily
database backups and 8 built-in classics, at the fixed **Tailscale Funnel** address
https://neerajs-macbook-air.tail8cd657.ts.net (see [../deploy/README.md](../deploy/README.md)).

Open items (waiting on the user):
- **Moving to a server this weekend (7–8 Nov 2026)**: Oracle Cloud Always Free (ARM) + domain is the plan; the
  API image is ~2.8 GB now (speech model). Restore normal rate limits there; set up the watchdog/backups.
- **Moving to a real server** (asked 2 Nov 2026): recommended **Oracle Cloud Always Free** (ARM, Mumbai /
  Hyderabad, ₹0) + a domain (~₹500–1,000/yr) + Caddy HTTPS + Cloudflare DNS; fallback AWS Lightsail Mumbai 2 GB
  (~$10/month). The user must create the Oracle account, buy the domain and add an SSH key; then migrate
  (pg_dump + data volume), off-site backups, retire the Mac/Funnel. This also fixes slow logins (Funnel's
  entry point is in Tokyo, ~250–300 ms per round trip).
- **Rate limits** are temporarily raised in `deploy/compose.yaml` (login 60/min;300/h, email 30/h). Funnel passes
  real client IPs, so restoring the normal limits is safe; the user hasn't decided.
- **Watchdog**: the launchd agent (`deploy/watchdog/`, every 30 min) still needs the user to install it
  (one command in deploy/README.md); a session cron ran it meanwhile.
- **Mac must stay awake** while friends use it (Battery → Options → prevent automatic sleeping).
- After a deploy, phones may show the previous version until reopened (PWA cache).
- **Next work** (ask which first; recommended: harder options): see the Phase 2 list in PROJECT_PLAN.md:
  harder look-alike options, picture questions, pronunciation, the Shop opening (name changes, streak freeze,
  coin ledger), culture themes, easter eggs, friends + leaderboards; Phase 3 affiliate book links.

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

| #45 | Legacy time-zone names (tzdata) and UTC fallback; a failed answer keeps the question |
| #46, #47, #55 | Uploads: WordNet usable from worker threads; fontTools for PDF fonts; NUL characters stripped |
| #48 | Your words: every answered word with a progress ring (green for the part done) |
| #49, #50 | Login page "How it works" intro; tagline shown on phones |
| #51 | Speaker button (Web Speech API) beside words; device's English, device's default voice |
| #52 | Words in progress pause while none of the current reads uses them; learned words still come back for review |
| #53 | Per-user daily goal (default 20 ≈ 5 min); raising it never breaks an earned streak |
| #54 | `chapter_words`: every chapter a word appears in; earlier chapters at 1 in 4; chapters cover all their words; `reindex_chapters` command |

### Redesign (1 Nov 2026, from an approved clickable preview)
| PR | What |
|----|------|
| #56 | Green light/dark themes + sepia option; Fredoka/Figtree (OFL, self-hosted); chunky buttons; Fluent Emoji 3D icons (MIT, `public/icons`) |
| #57 | Bottom tabs (Today · Books · Words · Me); Today home with goal ring, Continue, current book, week |
| #58 | Sessions of 10 with progress bar, sliding feedback panel, vibration, confetti, summary + milestones |
| #59 | Book page chapter path (readiness rings); word cards with the book sentence |
| #60 | First-run tour for new accounts with a daily goal choice up to 100 (`users.onboarded_at`) |

### Testing fixes and speed (2 Nov 2026)
| PR | What |
|----|------|
| #62 | Today's week strip judged like the streak (each day by that day's goal), sent by the server |
| #63 | Choosing the next word ~6× faster (one grouped query instead of a subquery per appearance) |
| #64, #65 | Tapping an option shows the whole result at once: questions carry the correct option, meaning, sentence and both outcomes; the save confirms in the background |
| #66 | No "Right!" / "Not quite." text (the colour says it; screen readers still hear it) |
| #67 | The next question is kept in hand (`include_next`), so Continue never waits; failed saves show a retry banner |
| #68 | Watchdog (launchd, every 5 min) restarts Colima, the stack, Tailscale and Funnel if any stopped |

Docker builds now use BuildKit (`brew install docker-buildx`): a code-only deploy takes ~20 s instead of
10–20 min. `colima ssh -- sudo fstrim -av` after builds gives disk space back.

**Tests:** backend 356 (99% coverage, also run on PostgreSQL), frontend 116. CI: 5 required jobs.

### Features and fixes (2 Nov 2026, evening)
| PR | What |
|----|------|
| #70 | Rate limits raised temporarily (see open items) |
| #71 | "I know this" is instant (optimistic, with the next question in hand) |
| #72 | Book covers (EPUB cover image / PDF first page → `data/covers`), shelves of cards, a smaller Choose file |
| #73 | Reminders by notification, email or both (`push` / `email` booleans) |
| #74, #76 | Laptop layout: a side menu, dashboard cards, covers in Reading now / Currently reading |
| #77 | Coins instead of the diamond; a **Shop** tab (cartoon market, "The merchant isn't here yet"); scrolling shelves |
| #78 | Settings: profile photo, username change **once** (with a warning), gender → Me icon (man/woman/person), email change confirmed by link, password change; theme picker only in Settings; red 3D Log out; gear icon |
| #82, #83, #86 | Today: **Score this week** line graph (net points per day, `stats.week[].points`) under the Continue button; email/password behind 3D buttons + Reset password; animated green book on the login page |
| #84 | **Streak fix**: `goal_changes` table keeps every goal change (the old columns only kept the last one, so a second change on another day re-judged older days) |
| #85 | Shelf rows line up (covers never squeezed); three smaller covers per row on phones |
| #69, #75, #79–#81, #87 | Plan: pronunciation, picture questions, the Shop, culture themes, easter eggs, harder options, friends + leaderboards, affiliate links |

Migrations this stretch: covers, reminders push/email, profile (8c7b9f9e4cc0), goal history (9d225d8a45a4); each
deploy was preceded by a `pg_dump` to `deploy/backups/before-*.sql.gz`.

**Tests:** backend 380 (also run on PostgreSQL), frontend 133.

### 3–5 Nov 2026
| PR | What |
|----|------|
| #89, #90, #92 | Words: **Known** tab, "Learn it again", known words only sent on request (old cached apps) |
| #91, #85 | Books: one scrollable row per shelf, aligned covers |
| #95–#97, #107 | **Ninja Mode**: double coins after 5 right in a row, a 5-segment meter, a warning before stopping; ends on a new visit (only a quiz reload keeps it) |
| #99 | **Daily quests** on Today: 3 a day sized by the goal, Claim buttons, bonus chest |
| #100, #101 | Vibration on iPhone (switch haptic), **sound effects** (Web Audio) with volume in Settings |
| #102, #104 | New versions apply on first open (reload on SW takeover, no-cache headers); green icon renamed to beat icon caches |
| #103 | Green book app icon |
| #105, #106 | Keyboard: ↓/↑ + Enter for options, summary and warnings |
| #108, #109 | Book page: tap a chapter circle for a Practice bubble (chapter-only quiz) |
| #110, #111 | **Leaderboard** (today's coins), public **profiles**, new **Me** page (Progress merged), privacy switches, book covers on profiles |
| #112, #113 | **Shop opens on Sundays**: streak freeze (10k, ≤3, auto-used), double coins (50k, 30 min, 4× in Ninja Mode), extra username change (100k) |
| #114 | **Friends**: exact search, requests, Friends leaderboard tab |
| #115 | **Weekly/monthly recaps** on Today, Me and by email |
| #116 | **Pronunciation**: 🎤 Say it on word cards, "say this word" quiz questions; faster-whisper `base.en` on our server (image +1 GB) |
| #117 | **Learning cap**: ≤100 words in progress (top book, then closest to learned; rest "Later"), 10 right answers to learn, Almost-there group, learned banner |

Migrations this stretch (each preceded by a `pg_dump` in `deploy/backups/before-*.sql.gz`): combo, quest
claims, leaderboard opt-out + books visibility, shop purchases, friendships, recap emails.

**Tests:** backend 440, frontend 181. The routine watchdog cron was stopped on 5 Nov (the user is moving to a
server that weekend).

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
| Look | Green light/dark themes with sepia as a third choice; rounded fonts; 3D icons; bottom tabs on phones |
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
- The CSS is one global `index.css` (≈1,900 lines after the redesign); worth splitting per feature.
- Headless Chrome on the Mac stopped writing screenshots; visual checks use Playwright's Chromium in the
  job's scratch folder (delete `~/Library/Caches/ms-playwright` afterwards: disk space is tight).

---

## 🛠 Environment notes

- Tools: `gh` (logged in as `neeraj2681`, `workflow` scope), `pre-commit`, `mailpit`, `colima`, `docker`,
  `docker-compose` via Homebrew; `uv`, Node 24. `~/.docker/config.json` lost a stale Docker Desktop `credsStore`
  (backup next to it).
- Commit with `UV_NO_SYNC=1 git commit …` if the pre-commit hooks try to download the spaCy model and hang.
- If `gh pr create`/`gh pr merge` fail with "GraphQL: Something went wrong", use the REST API via `gh api`.
- WordNet data: ~125 MB in `data/wordnet/` (per data dir); `uv run python -m app.dictionary.install`.
