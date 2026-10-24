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
- **Several current reads at once, with priority.** Multi-select of uploaded books → `current_readings`, ordered by
  a user-set priority (drag to reorder). New-word slots in a quiz are shared across current reads, weighted by
  priority (e.g. 1st book gets most of the slots), so the main book moves fastest while others keep progressing.
- Each current read tracks **current chapter** (user updates it, or "I finished chapter N" button).
- `learning_list` is derived (not hand-maintained): words from current reads, ordered by
  `book priority → chapter (starting at current chapter) → first position in chapter`, excluding learned/known words.
- **Chapter primer** view: "Before you read Chapter 4, these 23 words are new to you" + readiness %.

### 5.3 Daily quiz
- "Play" → a **round of 10** MCQ questions. Question: the word; 4 options: definitions; exactly one correct.
- The first completed round of the day is the **daily goal** (counts for the streak). After it, "Play another round"
  is offered; extra rounds are optional.
- Every question has an **"I know this"** button: marks the word `known` and replaces it with another question.
- **Close-but-wrong distractors** (the hard part):
  - Prefer definitions of words with the **same part of speech** and **similar difficulty**.
  - Optionally semantically *near* words (WordNet siblings / embedding neighbours) — **but never synonyms**, otherwise
    two answers are right. Rule: reject a distractor if it shares a synset or is a listed synonym of the target.
- When a word repeats in a session, regenerate and reshuffle options (never the same option set twice).
- Question mix per session (configurable), e.g.:
  - 6 — next words from the learning list frontier (new)
  - 3 — words in progress (0 < score < 100)
  - 1 — review of decayed "learned" words
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
- **Fast quizzes:** questions are pre-generated in the background for the next rounds and cached.
- **Privacy:** with a local model, book text never leaves the machine. A hosted model would only receive short
  snippets, and only if the user opts in.

---

## 6. Tech stack (all free & open source)

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | **Python 3.12 + FastAPI** | Best ecosystem for text/NLP; simple REST API; async; auto OpenAPI docs. |
| NLP | **spaCy** (en_core_web_sm), **wordfreq** | Lemmatization, POS, NER; word-difficulty scores. |
| File parsing | **ebooklib + BeautifulSoup** (EPUB), **pypdf / pdfminer.six** (PDF) | Mature, MIT/BSD-licensed. |
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
users            (id, name, email, created_at)
documents        (id, owner_user_id, title, author, file_path, format, uploaded_at, status)
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
- [ ] Backend skeleton: FastAPI, SQLAlchemy, Alembic, ruff, mypy, pytest + CI job (`feat/backend-skeleton`)
- [x] Frontend skeleton: Vite + React + TS, ESLint, Prettier, Vitest + CI job (`feat/frontend-skeleton`)
- [ ] Docker Compose for local run; release workflow (tag → GHCR image)

### Phase 1 — MVP (personal, local)
- [ ] EPUB + PDF + TXT upload and per-chapter extraction
- [ ] NLP pipeline: lemmatize, filter, difficulty threshold, context sentences
- [ ] WordNet dictionary import
- [ ] Current-reading chooser + current chapter
- [ ] Learning list ordering
- [ ] Quiz: 10 MCQs, safe distractors, re-randomized options
- [ ] Scoring rules + lazy decay + answer log
- [ ] Optional post-upload triage (Known / Unsure / New) + "I know this" button
- [ ] Daily goal (first round of 10) + streak, optional extra rounds
- [ ] Basic progress page
- [ ] Export / backup (JSON) and import

### Phase 2 — Better learning
- [ ] Chapter primer & readiness %
- [ ] Fill-in-the-blank questions using sentences from the book
- [ ] Reverse questions (definition → word)
- [ ] Adjustable difficulty threshold per user
- [ ] Spaced-repetition option (FSRS) alongside the point system
- [ ] Mobile-friendly layout, PWA, daily reminder
- [ ] OCR for scanned PDFs (Tesseract)

### Phase 3 — Multi-user (future plan items 1–2)
- [ ] Accounts & auth
- [ ] Personal profiles & settings
- [ ] Move to PostgreSQL; Docker deployment
- [ ] Per-user privacy of uploaded files

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
- No scraping of Vocabulary.com, Merriam-Webster, etc.
- Uploaded books: stored only for the uploader; in multi-user mode never shared across users. Only short context
  snippets shown back.
- Ready-made lists built only from public-domain or openly licensed sources.
- Project licence: MIT (suggested).

## 11. Decisions (24 Oct 2026)

| # | Question | Decision |
|---|----------|----------|
| 1 | One book or several current reads? | **Several, with priority**; quiz slots weighted by priority (§5.2) |
| 2 | Quiz length | **Rounds of 10**; first round = daily goal/streak, more rounds optional (§5.3) |
| 3 | Words already known | **Optional triage after upload** (Known / Unsure / New) **+ "I know this" button** in quizzes (§5.1, §5.3) |
| 4 | Devices | **Desktop first**; mobile-friendly layout and PWA in Phase 2 |
| 5 | Scanned PDFs | **Text PDFs only** in MVP; OCR (Tesseract) in Phase 2 (§5.1) |
| 6 | "Unsure" starting score | **50** |
| 7 | Score floor | **0** |
| 8 | Linter / database | **ESLint** (most popular); **SQLite** now, PostgreSQL in Phase 3 |
| 9 | LLM question generation | **Phase 5**; MVP keeps the `QuestionGenerator` interface and stores questions as data (§5.6) |
