# Vocab Sensei — Project Plan

> Learn the words of your *next* read before you read them.

Source: original rough plan (Notion, 24 Oct 2026), expanded with brainstorming notes.

---

## 1. Motivation

Classics and advanced texts are full of intermediate/advanced English words. Looking them up mid-read breaks the flow
and hurts comprehension. Vocab Sensei prepares the reader with **the exact words they will meet in their next chapter**,
so reading becomes fluent, and words are reinforced by seeing them in real context right after learning them.

## 2. Success conditions (from the original plan)

| # | Condition | What it means for the design |
|---|-----------|------------------------------|
| 1 | **Simple to use** | One-click daily quiz; upload → words appear automatically; no manual list curation required. |
| 2 | **Long-term usable** | Progress must never be lost: versioned DB migrations, an append-only answer log, export/backup. Multi-user ready schema from day one. |
| 3 | **Gives results** | Visible progress: words learned, per-book "readiness %", streaks, upcoming chapter coverage. |
| 4 | **No policy violation** | Only open-licensed dictionaries (WordNet, Wiktionary); no scraping of Vocabulary.com or other sites; uploaded books stay private to the uploader and are never redistributed. |

## 3. Goals

**Short term:** personal use, runs locally, 100% free & open-source stack.

**Long term:** expandable without losing current progress; multiple users with accounts.

---

## 4. Core user flow

```
Upload book (PDF / EPUB / TXT)
        │
        ▼
Extract text per chapter ──► tokenize + lemmatize ──► filter (stopwords, names, common words)
        │                                                     │
        ▼                                                     ▼
 document_words (book, chapter, position, context)      words (global, de-duplicated)
        │                                                     │
        └────────────► "Currently reading" picks books ◄──────┘
                                   │
                                   ▼
                    learning_list (ordered by book → chapter → position)
                                   │
                                   ▼
                   Daily quiz: 10 MCQs, 4 options each
                                   │
                                   ▼
                answer log ──► learning_score per (user, word)
```

## 5. Core functionality (MVP)

### 5.1 File upload & word extraction
- Accept **EPUB** (best: real chapter structure via spine/TOC), **PDF** (chapters from outline/bookmarks, fallback to
  heading heuristics or fixed page ranges), **TXT**, later **DOCX**.
- **Text PDFs only** in the MVP. A PDF with no extractable text (scanned) is rejected with a clear "scanned PDFs
  aren't supported yet" message. OCR (Tesseract) is a Phase 2 item.
- Store original file locally (`data/uploads/`), metadata in DB.
- Pipeline:
  1. Extract text per chapter.
  2. Tokenize, POS-tag and lemmatize (spaCy) — so *perambulated*, *perambulating* → *perambulate*.
  3. Drop stopwords, numbers, proper nouns (POS = PROPN / NER person & place).
  4. **Difficulty filter** using word frequency (`wordfreq` Zipf score). E.g. keep words with Zipf < ~4.0
     (configurable). Common words like *house* are dropped; *lugubrious* stays.
  5. Keep only words that exist in the dictionary (removes OCR noise / typos).
- **Brainstorm note — de-duplication:** the original plan says "save only new words; discard already-saved ones".
  We keep that for the global `words` table, *but* still record the occurrence per book/chapter in
  `document_words`. Otherwise a word already learned from Book A would never be linked to Book B's chapter 3, and the
  per-chapter ordering for Book B would be incomplete.
- Save one **context sentence** per word per book — used later for "see it in use" and fill-in-the-blank questions.
- **Optional triage after upload:** a fast screen listing the book's new words (chapter order) where each can be
  marked **Known** (status `known`, never quizzed), **Unsure** (starts at score **50**) or left as **New** (score 0).
  Skippable; untriaged words count as New.

### 5.2 Current reading chooser
- **Up to two current reads at once.** `current_readings`, ordered by a user-set priority (drag to reorder). The
  books take turns for new words, and the words in progress are shared in equal halves (a book with too few
  words leaves its spare places to the other), so both books move along together. Starting a third is refused
  until one is stopped.
- **How many words in progress:** the daily goal, between 15 and 50 (20 answers a day → 20 words), so each word
  comes up about once a day and a new user learns their first word in about a week (with 100 at once, a 20-a-day
  user learned none in a month). Half the practice goes to the word closest to learned, half to the one waiting
  longest; a word answered wrong comes back after 3 other questions.
- Each current read tracks **current chapter** (user updates it, or "I finished chapter N" button).
- `learning_list` is derived (not hand-maintained): words from current reads, ordered by
  `book priority → chapter (starting at current chapter) → first position in chapter`, excluding learned/known words.
  **Decided:** books share new-word slots n : n−1 : … : 1 by priority. Within a book, 1 in 4 new words (and sorting
  cards) comes from chapters before the current one, in reading order (was: left out, changed 2026-11-01).
- **Every chapter a word appears in** is stored (`chapter_words`: first use per chapter, with that chapter's sentence).
  A word counts for the next chapter the reader meets it in, not only where the book first used it; a chapter's
  readiness and "Study this chapter" cover every word the chapter uses.
- **Chapter primer** view: "Before you read Chapter 4, these 23 words are new to you" + readiness %.

### 5.3 Daily quiz
- **Never-ending quiz** (decided, replaces rounds): the screen always shows a question (the word; 4 definitions,
  exactly one correct). Answering, right or wrong, leads straight to the next one; there is no end screen.
  An unanswered question stays on screen when the user comes back (reloading can't skip a hard word).
- **Live score** at the top: **lifetime points**. Every counted answer moves it: +5 right, −10 wrong, even when
  the word's own score is already 0 (decided 30 Oct 2026). Only the total never goes below 0. Word scores keep
  their own rules (§5.4); the two are logged separately (`quiz_answers.points` and `score_delta`). A green "+5" or red "−10" pops over it on each
  answer, next to a sparkline of the visit's last ~20 answers.
- After each answer: ✓/✗, the correct meaning and the sentence from the book, then "Next".
- **Daily goal:** 10 answers a day keeps the streak (days are counted in the user's time zone).
- **Progress page** (under the profile menu): a graph of lifetime points after every answer since the first one.
- Every question has an **"I know this"** button: marks the word `known` and replaces it with another question.
- **Close-but-wrong distractors** (the hard part):
  - Prefer definitions of words with the **same part of speech** and **similar difficulty**.
  - Optionally semantically *near* words (WordNet siblings / embedding neighbours) — **but never synonyms**, otherwise
    two answers are right. Rule: reject a distractor if it shares a synset or is a listed synonym of the target.
- Options are reshuffled (and regenerated) every time a word is asked; options close in length to the answer are
  preferred so the longest one isn't a giveaway.
- **Spacing:** a word isn't asked again within 10 questions. With fewer than 10 words available it can come back
  sooner, but then the answer is practice and scores nothing. A missed word simply returns later.
- Each next word comes from one of three pools, picked at random 6 : 3 : 1 (configurable):
  - new: next words from the learning list frontier
  - learning: words in progress, least recently reviewed first; paused (progress kept) while none of
    the user's current reads uses them
  - review: learned words whose decayed score fell below 100, from any book (even a stopped one)
- Show the context sentence from the book after answering (reinforces usage).

### 5.4 Scoring rules (as specified, all configurable)

| Event | Effect |
|-------|--------|
| Correct answer | `+5` |
| Wrong answer | `−10` |
| Score ≥ 100 | status = **learned**, removed from learning list |
| Every week after learned | `−5` (decay) |
| Learned word drops below 100 | back to **learning** list |

**Brainstorm notes on the numbers:**
- At +5 per correct answer a word needs **20 correct answers** to be learned. With 10 questions/day spread over many
  words, the first learned word may take weeks. Options: a higher starting score for words you partly know, a
  "**I already know this**" button (marks known, skip quiz), or a larger reward on first-try correct answers.
- −10 / +5 means you need **> 67 % accuracy** on a word just to make progress — intentionally strict.
- Weekly −5 decay drops a fresh 100 to 95 after one week → it re-enters the list and needs one more correct answer.
  This acts as a lightweight weekly review. Fine, but it means "learned" words keep returning forever; consider
  slowing decay as a word survives more reviews (spaced-repetition style, later phase: SM-2 / FSRS).
- **Decided:** score is floored at **0**, so a few bad days don't bury a word.
- **Decided:** "Unsure" words from triage start at **50**; "Known" words skip the quiz entirely.
- **Implement decay lazily** — compute `effective_score = score − 5 × weeks_since(learned_at or last_review)` at
  read time instead of a weekly cron job. A local app isn't always running; lazy decay is always correct.
- Every answer is stored in an append-only `quiz_answers` log. If the scoring rules change later, scores can be
  **recomputed from history** — progress is never lost (condition #2).

### 5.5 Progress dashboard
- Words learned / learning / known, per book and overall.
- Book & chapter readiness % (share of hard words in the chapter already learned).
- Daily streak, accuracy trend.

### 5.6 Ready for LLM-generated questions (Phase 5)

Long-term goal: an LLM writes questions personalized to the user's reading history. The MVP doesn't use an LLM, but
it is built so one can be added without reworking anything:

- **One interface for question generation.** `quiz/` defines a `QuestionGenerator` protocol
  (`generate(word, context) -> Question`). The MVP ships a rule-based WordNet generator; an `LLMQuestionGenerator`
  is added later as another implementation, chosen per question type in config.
- **Questions are stored as data**, not built on the fly and thrown away: a `questions` table records type, prompt,
  options, correct answer and **which generator/model made it**. Answers reference the question, so the answer log
  shows which generator teaches better.
- **Reading history is already collected** for this: current books and chapters, context sentences, per-word
  scores and every answer. That's what the prompt will be built from ("words this user keeps missing, in the style of
  the book they're reading now").
- **Extensible question types** (an enum): `definition_mcq` now; `fill_in_blank`, `correct_usage`, `nuance`,
  `reverse` later.

How it will work in Phase 5:
- **Model:** FOSS by default. [Ollama](https://ollama.com) (MIT) runs an open-weight model locally, e.g. Qwen or
  Mistral (Apache 2.0). A provider-agnostic `LLMClient` interface allows an optional hosted model (opt-in, paid).
- **Never trust raw output:** responses must match a JSON schema; the correct option must agree with the dictionary
  sense; distractors that are WordNet synonyms are rejected. Anything that fails falls back to the rule-based
  generator.
- **Fast quizzes:** the next questions are pre-generated in the background and cached.
- **Privacy:** with a local model, book text never leaves the machine. A hosted model would only receive short
  snippets, and only if the user opts in.

---

## 6. Tech stack (all free & open source)

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | **Python 3.12 + FastAPI** | Best ecosystem for text/NLP; simple REST API; async; auto OpenAPI docs. |
| NLP | **spaCy** (en_core_web_sm), **wordfreq** | Lemmatization, POS, NER; word-difficulty scores. |
| File parsing | **zipfile + BeautifulSoup/lxml** (EPUB), **pypdf / pdfminer.six** (PDF) | MIT/BSD. `ebooklib` avoided: AGPL-3.0 would force copyleft on the project. |
| Dictionary | **Open English WordNet** (via `wn`), optionally **Wiktionary** (kaikki.org dumps) | Open licences; offline; definitions, POS, synonyms (needed for distractor safety). |
| DB | **SQLite** now → **PostgreSQL** later | Zero-setup locally; SQLAlchemy keeps the switch cheap. |
| ORM / migrations | **SQLAlchemy 2 + Alembic** | Schema evolves without losing data. |
| Frontend | **React + Vite + TypeScript** (+ Tailwind) | Fast, simple; can later become a PWA for phone use. |
| Tests | **pytest**, **Vitest** | |
| Packaging | **uv** (Python), **pnpm/npm**, later **Docker Compose** | One-command local start. |

Alternative considered: a single full-stack JS app (Next.js). Rejected for now because the NLP/parsing libraries are
much stronger in Python.

## 7. Data model (multi-user ready from day one)

Every user-specific table has `user_id`, even though only one local user exists in phase 1. This is the single most
important decision for "expand without affecting current progress".

```
users            (id, email UNIQUE, password_hash, display_name, is_active, email_verified_at, created_at, updated_at)
auth_sessions    (id, user_id, token_hash UNIQUE, user_agent, created_at, last_used_at, expires_at)
email_tokens     (id, user_id, purpose[verify_email|reset_password], token_hash UNIQUE, created_at, expires_at, used_at)
documents        (id, owner_user_id, title, author, original_filename, file_path, format, status, error, uploaded_at)
chapters         (id, document_id, index, title)
words            (id, lemma UNIQUE, pos, zipf_frequency)
definitions      (id, word_id, pos, text, source, sense_rank)
document_words   (document_id, chapter_id, word_id, first_position, occurrences, context_sentence)
current_readings (user_id, document_id, current_chapter_index, priority, started_at)
user_words       (user_id, word_id, score, status[new|learning|learned|known], learned_at, last_reviewed_at)
quiz_sessions    (id, user_id, started_at, finished_at)
questions        (id, word_id, type, prompt, options_json, correct_index, generator, model, source_sentence, created_at)
quiz_answers     (id, session_id, user_id, word_id, question_id, chosen, correct, score_delta, answered_at)
```

## 8. Project structure

```
vocab_sensei/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers (books, readings, quiz, progress), HTTP only
│   │   ├── services/       # use cases orchestrating domain modules + repositories
│   │   ├── extraction/     # pdf/epub/txt parsers, chapter splitting, NLP pipeline (pure)
│   │   ├── dictionary/     # WordNet loader, definition lookup (pure)
│   │   ├── quiz/           # question selection, distractor generation (pure)
│   │   ├── scoring/        # score rules, decay, status transitions (pure)
│   │   ├── repositories/   # DB access per aggregate
│   │   ├── db/             # models, session, alembic migrations
│   │   ├── core/           # config (scoring constants, thresholds), logging
│   │   └── main.py
│   └── tests/
├── frontend/               # React + Vite app
├── data/                   # local uploads + sqlite db (git-ignored)
├── .github/workflows/      # CI/CD
└── docs/
```

Layering rules and coding guidelines: [ARCHITECTURE.md](ARCHITECTURE.md). Git workflow: [CONTRIBUTING.md](../CONTRIBUTING.md).

## 8a. Engineering workflow & CI/CD

**Git:** GitHub Flow. One branch per feature (`feat/…`, `fix/…`, `chore/…`), several in parallel via `git worktree`,
merged into a protected `main` through a PR with green CI (squash merge). Conventional Commits. Releases are tagged
`vX.Y.Z` (SemVer).

**CI (GitHub Actions, on every PR and push to main):**
1. pre-commit hygiene checks *(done)*
2. backend: `ruff check`, `ruff format --check`, `mypy`, `pytest --cov`
3. frontend: `eslint`, `prettier --check`, `tsc`, `vitest`, `vite build`
4. (later) dependency audit: `pip-audit`, `npm audit`; Dependabot for updates

**CD:**
- Phase 1 (local): `docker compose up` runs everything; no deployment needed.
- On a `v*` tag: build Docker images → publish to GitHub Container Registry (GHCR) → create a GitHub Release with
  changelog.
- Phase 3 (friends): auto-deploy the tagged image to a self-hosted box (home server / Raspberry Pi / free-tier VM)
  pulled via Docker Compose; HTTPS via Caddy (FOSS). Access for friends over the internet or Tailscale/Headscale.

**Note on "FOSS only":** every library and tool in the code is open source. GitHub and GitHub Actions are free, but
they are proprietary services. A fully FOSS alternative is Codeberg + Forgejo Actions, and moving there later is easy
because git and the workflow files carry over.

## 9. Roadmap

### Phase 0 — Setup
- [x] Repo, README, licence, `.gitignore`
- [x] Git workflow guide, PR template, pre-commit, CI hygiene job (`chore/dev-workflow`)
- [x] Public GitHub repo, squash-merge only, auto-delete merged branches, `main` protected (CI must pass,
      linear history, no force-push, applies to admins too)
- [x] Backend skeleton: FastAPI, SQLAlchemy, Alembic, ruff, mypy, pytest + CI job (`feat/backend-skeleton`)
- [x] Frontend skeleton: Vite + React + TS, ESLint, Prettier, Vitest + CI job (`feat/frontend-skeleton`)
- [ ] Docker Compose for local run; release workflow (tag → GHCR image)

### Phase 1 — MVP (personal, local)
- [x] DB models + initial migration, incl. account tables (`feat/db-models`)
- [x] Scoring rules with lazy decay (`feat/scoring`)
- [x] Accounts: email + password, email verification, password reset, cookie sessions (`feat/auth`)
- [x] Login / sign-up / verify / reset pages in the frontend (`feat/auth-ui`)
- [x] EPUB parsing into chapters (`feat/epub-parser`)
- [x] Upload endpoint: store file, parse in the background, strip Gutenberg boilerplate (`feat/upload`)
- [x] PDF + TXT parsing: pypdf with bookmarks or heading detection, contents skipped, scanned PDFs rejected (`feat/pdf-txt-parser`)
- [x] NLP pipeline: lemmatize, filter, difficulty threshold, context sentences; runs on upload (`feat/word-extraction`)
- [x] WordNet dictionary import (`feat/dictionary`)
- [x] Library page (upload, my books, chapter-by-chapter words) + current-reading chooser with priorities and current chapter (`feat/library-ui`)
- [x] Part of speech per book word, so the matching definitions come first (`feat/word-pos`)
- [x] Learning list ordering: current chapter onward, books mixed 3:2:1 by priority, "Up next" preview (`feat/learning-list`)
- [x] Quiz engine: never-ending MCQs, safe distractors, spacing, 6:3:1 pools, scoring + answer log, stats, history (`feat/quiz-engine`)
- [ ] Quiz page: live score with +5/−10 pops and sparkline, feedback with the book's sentence (`feat/quiz-ui`)
- [x] Optional sorting of a book's words, one card at a time (Known / Unsure / New, K/U/N keys, undo) + "I know this" button (`feat/triage`)
- [x] Daily goal (10 answers a day) + streak (API, in `feat/quiz-engine`)
- [ ] Progress page under the profile menu: lifetime points graph since the first answer (`feat/progress-page`)
- [x] Export / backup (JSON: progress, answers, current reads; keyed by word and title) and merge-restore (`feat/backup`)

### Phase 2 — Better learning
- [x] Chapter primer & readiness % (average progress) + "Study this chapter" focused quiz (`feat/chapter-primer`)
- [x] Fill-in-the-blank questions using sentences from the book (`feat/question-types`)
- [x] Reverse questions (definition → word); formats unlock by word score: 0–29 meaning, 30–69 + reverse, 70+ + fill-in
- [ ] Adjustable difficulty threshold per user
- [ ] **Harder options for well-known words** (requested 2 Nov 2026, next phase): once a word's score passes
  a threshold (e.g. 70, alongside fill-in), its wrong options become look-alikes, so it's harder to guess.
  - Today wrong options are other words of the same part of speech with meanings of similar length. Close
    options instead: near-meanings (WordNet siblings, e.g. *melancholy* vs *wistful*, *sombre*), words
    that look or sound alike (*affect/effect*, *elicit/illicit*), or the same root.
  - Never a true synonym, so exactly one answer is still right.
  - Steps by score: 0–69 the usual options, 70–89 one or two close ones, 90+ all close.
  - A little badge ("Tricky") on the question, and the threshold configurable in settings.
- [ ] Spaced-repetition option (FSRS) alongside the point system
- [ ] **Next-word recommender** (requested 9 Nov 2026): choose each quiz word with a model of the learner instead of
  fixed rules (pools, closest-or-oldest, retries). Start from each person's word level (the placement check) and a
  per-word difficulty learned from everyone's answers (a Rasch/IRT model: P(right) = σ(ability − difficulty)); predict
  how likely each candidate is to be answered right and how soon it will be forgotten, and ask the word that teaches
  most (about 70–85% expected success, due for review, from the chapters being read). Compare it with today's rules
  on the answer log before switching (offline replay), then as an A/B test.
- [x] Mobile-friendly layout + installable PWA (`feat/mobile-pwa`)
- [x] Daily reminder by push notification or email at a chosen time, only if the goal isn't met (`feat/reminders`, `feat/reminders-ui`)
- [ ] **OCR for scanned PDFs** (requested again 3 Nov 2026): a PDF made of page photos has no text to read, so
  today its upload fails. Read the text from the page images instead.
  - **Tools** (all free, run on our server, nothing sent elsewhere): render each page with **pypdfium2** (already
    used for covers), read it with **Tesseract** (Apache-2.0) through `pytesseract`. Not `ocrmypdf`: it needs
    Ghostscript, which is AGPL.
  - **When**: only if a PDF has (almost) no text layer; text PDFs keep the fast path.
  - **Speed**: ~1–3 s a page on this CPU, so a 300-page book takes several minutes. Run in the background with
    the book showing "Reading the scanned pages… 40%", and a page limit (e.g. 600) to protect the server.
  - **Quality**: OCR noise is mostly dropped by the existing "only dictionary words" filter; chapter headings
    are still found by the heading rules. English first (`tesseract-ocr-eng`); more languages later.
  - **Docker**: adds the `tesseract-ocr` package to the API image (~30 MB).
- [x] Hear a word: speaker button using the browser's speech (Web Speech `speechSynthesis`) (#51)
- [ ] **Pronunciation practice** (requested 2 Nov 2026): a mic button beside the word; the learner says
  it and gets feedback (✓ / try again, then which sound was off).
  - Record in the browser (`MediaRecorder`, needs mic permission; HTTPS is already in place).
  - Check the speech with a **free, local** recogniser so audio never leaves our server: Vosk
    (Apache-2.0, small models) or whisper.cpp (MIT), run in the API container; compare the heard
    word with the target, later phoneme by phoneme (CMUdict / espeak-ng IPA, both free).
  - Avoid the browser's built-in `SpeechRecognition`: it's missing in Firefox and sends audio to
    Google/Apple.
  - Could become a fourth question type ("Say this word"), unlocked once a word is well known.

- [ ] **Picture questions** (requested 2 Nov 2026, next phase): show the word and four pictures; the
  learner taps the one that matches. Works for concrete words (nouns, many verbs, colours); abstract
  words (*melancholy*) keep the text questions.
  - Pictures need a free licence and no per-request cost: Wikimedia Commons / Openverse (CC-licensed,
    attribution shown), or Fluent-style illustrations generated once with a local open model.
  - Pick distractor pictures from words of the same part of speech; cache images on our server.
  - Becomes a fifth question type, mixed in like the others.
- [x] **The Shop opens** (built 5 Nov 2026: open all of Sunday; streak freezes (1,500, up to 3), double coins (1,000, 30 min) and an extra name change (5,000); prices lowered 5 Nov to fit ~400 coins a day): coins (the score) buy things in the Shop
  tab, which today shows the cartoon market with "The merchant isn't here yet".
  - **Extra username change**: everyone gets one free change (Settings); more cost coins.
  - **Streak freeze**: keeps the streak alive through one missed day; bought ahead, used automatically.
  - Needs a coin ledger (earned vs spent) so spending never lowers the score history.
- [ ] **Culture themes** (requested 2 Nov 2026, next phase): in Settings → Theme, pick a world theme such as
  **Japanese**, **Chinese** or **Arabian** (more later, e.g. Indian, Persian). One choice changes the whole app.
  - **Colours and fonts**: each theme sets its own palette and display font (free OFL fonts only). Examples:
    vermilion and ink with sakura accents (Japanese), red and gold (Chinese), sand, teal and gold (Arabian).
  - **Shop**: each theme has its own market and merchant: a Japanese street stall with lanterns, a Chinese
    night market, the Arabian souk we have today.
  - **Decorations**: theme icons and patterns on cards, the tab bar and the celebration screens.
  - **Light and dark**: each culture theme also works in light and dark, so the choice becomes "culture ×
    light/dark" and replaces today's Light / Dark / Sepia picker.
  - **Saving it**: kept with the account so it follows you across devices, not just per browser. Some
    themes could later be sold in the Shop for coins.
- [ ] **Easter eggs** (requested 2 Nov 2026, next phase): small hidden surprises that reward curiosity.
  They never get in the way of learning and never change scores.
  - **Hidden taps**: tap the camel in the Shop five times and it spits a coin. Long-press the logo for a
    sensei quote. Tap the moon to make it a full moon.
  - **Word-based**: learning certain words triggers a little animation, e.g. *ebullient* (confetti),
    *melancholy* (rain), *serendipity* (a four-leaf clover).
  - **Dates and milestones**: festival decorations (Diwali lamps, New Year fireworks), your sign-up
    anniversary, the 100th and 1,000th word learned.
  - **Secret code**: typing a hidden word (or the Konami code on a laptop) unlocks a secret look.
  - **Collection**: found eggs go into a "Secrets found: 3 / 12" corner on the Me page, with no hints beyond a
    silhouette. Some could pay a few coins once the Shop opens.
  - Stored as a list of found egg ids on the account. Animations respect "reduce motion".
- [ ] **Friends** (requested 2 Nov 2026, next phase): find people and send a friend request; they accept or
  decline.
  - **Search** by exact email or username. Exact matches only, so the site can't be used to list everyone's
    email addresses. A profile switch can turn off being found.
  - **Contacts sync**: on phones, the Contact Picker API (Chrome on Android) lets you choose contacts to look
    up. Only the email addresses you pick are sent, hashed (SHA-256), and matched against hashed account
    emails. The address book is never uploaded or stored. iPhone Safari has no picker, so it falls back to
    search and an invite link.
  - **Invite link**: share a link (WhatsApp etc.) that opens sign-up and sends the request automatically.
  - Requests: pending → accepted / declined. Remove or block a friend at any time.
  - Data: a `friendships` table (requester, addressee, status, timestamps).
- [ ] **Leaderboards** (global board of today's coins with profiles built 4 Nov 2026, #110; the Friends tab waits for Friends): **Friends** and **Global** tabs.
  - **Ranked by points earned this week**, resetting every Monday, so newcomers can compete. An all-time
    tab can come later.
  - Each row: rank, picture or figure, username, weekly points and streak. You're always shown, even outside
    the top 50.
  - Global shows usernames only, never emails. You can opt out of Global and stay on Friends only.
  - Weekly points come from the answers table (as for the score graph). Cache the global board for a few
    minutes.

#### Fun and coming back (requested 3 Nov 2026, next phase)
Goal: a reason to return today (quests, combo, word of the day), this week (boss rounds, recaps, duels) and for
months (belts, garden, badges). None of it changes how words are scored.

- [ ] **Sensei belts**: levels from words learned, white → yellow → orange → green → blue → brown → black (e.g. 0,
  50, 150, 300, 600, 1,000, 2,000 words). A small sensei mascot wears your belt on the Me page and cheers in the
  quiz; a belt ceremony screen when you move up. Original art (Fluent-style), no existing characters.
- [ ] **Chapter boss round**: before reading a chapter, an optional timed challenge (e.g. 10 of its words, 60 s).
  Win → the chapter is stamped "Ready to read ✓" with a celebration and bonus coins; lose → try again tomorrow.
- [ ] **Word garden**: each learned word is a plant; as its score decays it wilts (the weekly decay already
  exists); "water" = a quick review of the wilting ones. Garden grows with belts.
- [x] **Daily quests** (built 3 Nov 2026, #99): three a day, e.g. "Learn 5 words from Dracula", "10 right in a row", "Finish your goal
  before noon"; each pays coins; a small chest when all three are done.
- [x] **Combo meter** (built 3 Nov 2026 as **Ninja Mode**, #95–#97): right answers in a row fill a meter; at 5 the coins double until a mistake. A short sound
  and phone vibration (`navigator.vibrate`), both switchable off in Settings.
- [ ] **Word of the day**: a push/email with one of your own words and the sentence from your book; tapping it
  opens that word's card.
- [ ] **Playful reminders**: the daily reminder in the sensei's voice, from a rotating set of lines ("Your words
  miss you…"), never guilt-tripping; same opt-in and times as today.
- [ ] **Badges**: first 100 words, 7/30/100-day streaks, a whole book learned, night owl, early bird, combo of 20,
  boss rounds won…; a badge shelf on the Me page, locked ones shown as silhouettes.
- [ ] **Weekly and monthly recaps**: "Your week / your month": words learned, best day, favourite book, toughest
  word, streak; shown on Monday / the 1st, also by email if reminders are on; shareable as a card.
- [ ] **Duels**: challenge a friend to the same 10 questions from a book; each plays when they like; the result
  screen shows both scores (needs Friends).
- [ ] **Share cards**: an image made on our server (Pillow, no outside service) like "I learned *ebullient* from
  *Digital Minimalism*" or a recap, shared with the phone's share sheet (Web Share API) to WhatsApp / Instagram.
- [ ] **Privacy-friendly analytics** to see what actually brings people back (D1/D7 return): Umami (MIT),
  self-hosted; not Plausible (AGPL).

### Phase 3 — Multi-user (future plan items 1–2)
- [x] Accounts & auth (pulled forward into Phase 1)
- [x] Login rate limiting, account deletion / data export per user
- [x] Personal profiles & settings (photo, username once, gender icon, email/password; #78)
- [x] Move to PostgreSQL; Docker deployment (on the Mac; a real server is still to come)
- [ ] Per-user privacy of uploaded files
- [ ] **Affiliate book links in the Shop** (requested 2 Nov 2026): the merchant sells real books. Each classic and
  each book on someone's shelf links to buy it, e.g. "Buy the paperback" / "Get it on Kindle".
  - **Programmes**: Amazon Associates (India: affiliate.amazon.in) is the most common. Others: Flipkart
    Affiliate, Bookshop.org (UK/US, supports independent bookshops). Each needs its own sign-up and approval.
  - **Matching**: look a book up by ISBN (from the EPUB's metadata) or by title and author with the free Open
    Library API; store the product link per book.
  - **Honesty**: a clear "affiliate link: we may earn a small commission" note next to the links (both
    Amazon's rules and Indian advertising guidelines require disclosure); links open in a new tab.
  - **Privacy**: no tracking scripts; plain links with the affiliate tag only.
  - **Prerequisite**: a public site address that isn't a personal machine name (the custom domain idea),
    since programmes ask for the website during approval.

### Phase 4 — Smart features (future plan items 3–5)
- [ ] Recommendations based on usage (weak words, next books)
- [ ] Usage suggestions: example sentences similar to the user's reading style
- [ ] Ready-to-use lists (e.g. from public-domain classics on Project Gutenberg, themed lists)

### Phase 5 — LLM-generated questions (see §5.6)
- [ ] `LLMClient` interface + Ollama adapter (local, open-weight model)
- [ ] `LLMQuestionGenerator` behind the existing `QuestionGenerator` interface
- [ ] Personalized question types: book-style fill-in-the-blank, "which sentence uses the word correctly",
      near-synonym nuance, explanation of why a wrong option is wrong
- [ ] Prompt built from reading history: current books/chapters, weak words, recent mistakes
- [ ] Validation layer (schema, single correct answer, no synonym distractors) + rule-based fallback
- [ ] Background pre-generation and caching so quizzes stay instant
- [ ] "Report a bad question" button; compare generators using the answer log
- [ ] Optional hosted-model adapter (opt-in, not FOSS)

## 10. Policy & licensing checklist
- Dictionaries: Open English WordNet (CC BY 4.0), Wiktionary (CC BY-SA) — keep attribution in the app's About page.
- Word frequencies: `wordfreq` (code MIT, data CC BY-SA 4.0) and spaCy `en_core_web_sm` (MIT) — attribution on the About page too.
- No scraping of Vocabulary.com, Merriam-Webster, etc.
- Uploaded books: stored only for the uploader; in multi-user mode never shared across users. Only short context
  snippets shown back.
- Ready-made lists built only from public-domain or openly licensed sources.
- Project licence: MIT (suggested).

## 11. Decisions (24 Oct 2026)

| # | Question | Decision |
|---|----------|----------|
| 1 | One book or several current reads? | **Up to two**, sharing quiz words equally (§5.2) |
| 2 | Quiz length | **Never-ending quiz** with a live lifetime score; 10 answers a day = daily goal/streak (§5.3). Replaced "rounds of 10" on 30 Oct 2026 |
| 3 | Words already known | **Optional triage after upload** (Known / Unsure / New) **+ "I know this" button** in quizzes (§5.1, §5.3) |
| 4 | Devices | **Desktop first**; mobile-friendly layout and PWA in Phase 2 |
| 5 | Scanned PDFs | **Text PDFs only** in MVP; OCR (Tesseract) in Phase 2 (§5.1) |
| 6 | "Unsure" starting score | **50** |
| 7 | Score floor | **0** |
| 8 | Linter / database | **ESLint** (most popular); **SQLite** now, PostgreSQL in Phase 3 |
| 9 | LLM question generation | **Phase 5**; MVP keeps the `QuestionGenerator` interface and stores questions as data (§5.6) |
