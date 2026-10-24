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

### 5.2 Current reading chooser
- Dropdown (multi-select) of uploaded books → `current_readings`.
- Each current read tracks **current chapter** (user updates it, or "I finished chapter N" button).
- `learning_list` is derived (not hand-maintained): words from current reads, ordered by
  `book priority → chapter (starting at current chapter) → first position in chapter`, excluding learned/known words.
- **Chapter primer** view: "Before you read Chapter 4, these 23 words are new to you" + readiness %.

### 5.3 Daily quiz
- "Play" → 10 MCQ questions. Question: the word; 4 options: definitions; exactly one correct.
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
- Floor the score (e.g. at 0) so a few bad days don't bury a word.
- **Implement decay lazily** — compute `effective_score = score − 5 × weeks_since(learned_at or last_review)` at
  read time instead of a weekly cron job. A local app isn't always running; lazy decay is always correct.
- Every answer is stored in an append-only `quiz_answers` log. If the scoring rules change later, scores can be
  **recomputed from history** — progress is never lost (condition #2).

### 5.5 Progress dashboard
- Words learned / learning / known, per book and overall.
- Book & chapter readiness % (share of hard words in the chapter already learned).
- Daily streak, accuracy trend.

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
quiz_answers     (id, session_id, user_id, word_id, options_json, chosen, correct, score_delta, answered_at)
```

## 8. Project structure

```
vocab_sensei/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers (books, readings, quiz, progress)
│   │   ├── core/           # config (scoring constants, thresholds)
│   │   ├── db/             # models, session, alembic migrations
│   │   ├── extraction/     # pdf/epub/txt parsers, chapter splitting, NLP pipeline
│   │   ├── dictionary/     # WordNet loader, definition lookup
│   │   ├── quiz/           # question selection, distractor generation, scoring
│   │   └── main.py
│   └── tests/
├── frontend/               # React + Vite app
├── data/                   # local uploads + sqlite db (git-ignored)
└── docs/
```

## 9. Roadmap

### Phase 0 — Setup
- [ ] Repo, README, licence, `.gitignore`
- [ ] Backend skeleton (FastAPI, SQLAlchemy, Alembic, pytest)
- [ ] Frontend skeleton (Vite + React + TS)
- [ ] CI: lint + tests on GitHub Actions

### Phase 1 — MVP (personal, local)
- [ ] EPUB + PDF + TXT upload and per-chapter extraction
- [ ] NLP pipeline: lemmatize, filter, difficulty threshold, context sentences
- [ ] WordNet dictionary import
- [ ] Current-reading chooser + current chapter
- [ ] Learning list ordering
- [ ] Quiz: 10 MCQs, safe distractors, re-randomized options
- [ ] Scoring rules + lazy decay + answer log
- [ ] "I already know this" button
- [ ] Basic progress page
- [ ] Export / backup (JSON) and import

### Phase 2 — Better learning
- [ ] Chapter primer & readiness %
- [ ] Fill-in-the-blank questions using sentences from the book
- [ ] Reverse questions (definition → word)
- [ ] Adjustable difficulty threshold per user
- [ ] Spaced-repetition option (FSRS) alongside the point system
- [ ] PWA / mobile-friendly UI, daily reminder

### Phase 3 — Multi-user (future plan items 1–2)
- [ ] Accounts & auth
- [ ] Personal profiles & settings
- [ ] Move to PostgreSQL; Docker deployment
- [ ] Per-user privacy of uploaded files

### Phase 4 — Smart features (future plan items 3–5)
- [ ] Recommendations based on usage (weak words, next books)
- [ ] Usage suggestions: example sentences similar to the user's reading style
- [ ] Ready-to-use lists (e.g. from public-domain classics on Project Gutenberg, themed lists)

## 10. Policy & licensing checklist
- Dictionaries: Open English WordNet (CC BY 4.0), Wiktionary (CC BY-SA) — keep attribution in the app's About page.
- No scraping of Vocabulary.com, Merriam-Webster, etc.
- Uploaded books: stored only for the uploader; in multi-user mode never shared across users. Only short context
  snippets shown back.
- Ready-made lists built only from public-domain or openly licensed sources.
- Project licence: MIT (suggested).

## 11. Open questions
1. Multiple current reads at once, or one main book at a time?
2. Should the quiz be strictly 10 questions, or "10 by default, keep going if you want"?
3. Starting score for a newly seen word: 0? Or allow a quick "known / unsure / new" triage on upload?
4. Is a phone-friendly UI needed early (reading on Kindle/phone, quiz on phone)?
5. Should scanned (image-only) PDFs be supported via OCR (Tesseract), or text PDFs only?
