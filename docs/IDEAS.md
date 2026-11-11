# Ideas, plan critique and execution plan (11 Nov 2026)

Proposals from a review of `PROJECT_PLAN.md`, `PROGRESS.md` and the code (written with the Fable model). **Nothing
here is decided**: the user picks what to build; data-model and UX choices are asked first. When an idea is built,
move it to `PROJECT_PLAN.md` / `PROGRESS.md` and mark it here. Roles and handoffs: see "Agent roles" in `CLAUDE.md`.

Note: `DocumentService.discard_upload` deletes uploaded files after extraction; only the classics keep their EPUB.

## Ideas

### (a) Learning effectiveness
1. **Sense picked from the book's sentence** (M, high). Today `senses_per_pos=3` and "book's POS first" is the only
   disambiguation, so some words are drilled with the wrong meaning (*spleen*: organ vs anger). At extraction, rank
   WordNet senses by Lesk-style overlap between the gloss (+ examples, hypernyms) and the context sentence; store
   `DocumentWord.sense_rank`. New question type `which_meaning`: the sentence plus the word's own senses as options.
2. **Confusion pairs from the answer log** (S–M, high). `quiz_answers.chosen_index` + `questions.options` record
   which other word was picked. A job builds `word_confusions(user_id, word_id, confused_with_id, count)`; contrast
   card after a repeat miss ("*elicit* vs *illicit*"); the distractor picker prefers past confusions (same synonym
   check); a "Mixed up" group on Words.
3. **Typed recall at 90+** (S, med-high). All formats are 4-option recognition. `QuestionType.TYPED`: definition or
   blanked sentence + first letter and length; accept edit distance ≤ 1 (`rapidfuzz`, MIT).

### (b) Reading and the books
4. **In-app reader for the classics** (L, high): sanitised chapter HTML for ownerless documents only; words coloured
   by progress; tap a word for its meaning and "add to my quiz".
5. **"Did you meet it?" after a chapter** (M, high): five fill-in-the-blank questions from that chapter right after
   "I finished chapter N"; log `finished_at` per chapter → reading pace → pace new-word intake.
6. **Import e-reader highlights** (S–M, med-high): Kindle `My Clippings.txt` / Kobo exports; highlighted words get a
   `priority_boost` on `user_words`.
7. **"Can I read this?" preview** (S, med): "at your level 94% known, 310 to learn, ~3 weeks; hardest chapter 12";
   `services/readiness.py` → `book_fit()`.

### (c) Motivation and friends
8. **Your own sentence** (S–M, med-high): write one sentence when a word is learned; it becomes a second fill-in
   source; friends-only sharing.
9. **Reading together** (M, med): friends on the same classic share a chapter path and nudges; derived from
   `current_readings` ∩ `friendships`.

### (d) Going public
10. **Public chapter primers for the classics** (M, high): `/classics/<slug>/chapter/<n>` with the 20 hardest words,
    definitions and sentence (WordNet attribution); sitemap; cached by Caddy.
11. **Any Gutenberg book on demand** (M, high): bundled catalogue CSV + search; one tap adds an ownerless book,
    extracted once for everyone; throttle and respect Gutenberg's robot policy.
12. **Try before sign-up** (M, high): guest quiz keyed by a cookie; progress merges on sign-up (backup merge, #24).

### (e) Technical
13. **A real worker process** (M, high, enabler): extraction, Whisper, recap emails and question pre-generation out
    of the API process, via `arq` (MIT, on the existing Valkey) or `procrastinate` (MIT, PostgreSQL only).
14. **Offline quiz batches** (M, med): prefetch 20 questions, queue answers in IndexedDB, `POST /quiz/answers/batch`.

**Suggested top 3**: worker process (13); sense from the sentence (1); Gutenberg on demand + public primers (11 + 10).

## Plan critique
1. **Linear, uniform decay doesn't scale**: −5/week forever means ever more reviews. Store `review_count`; double the
   decay interval after each successful review (1, 2, 4, 8 weeks).
2. **Fill-in-the-blank reuses the sentence shown in every feedback**: use another chapter's sentence, or hide it in
   feedback above 50; add the user's own sentence (idea 8).
3. **The retry after a miss is nearly free** (answer just shown, same format, full points): retry in another format or
   at half points.
4. **The leaderboard ranks volume, not learning**: rank by words learned (or net word score) this week.
5. **Readiness counts probably-known words**: leave them out; later feed the IRT difficulty back into extraction.

## Execution plan (manager = Opus 5.5, workers = Sonnet 5.5 / Haiku 5.5)

### Idea 13: worker process
| # | Task | Tier |
|---|------|------|
| 1 | Choose queue, job table, retry/timeout policy; spec + acceptance tests; ask the user (adds a container) | Opus |
| 2 | `app/jobs/`: worker entrypoint, `enqueue()`, `Job` model + migration | Sonnet |
| 3 | Move document processing and `reindex_chapters` behind `enqueue()` | Haiku |
| 4 | Move speech check, recap emails, reminders to jobs | Haiku |
| 5 | `worker` service in `deploy/compose*.yaml`, `deploy/README.md` (manager reviews: `deploy/`) | Haiku |
| 6 | Tests (job runs, failure stored, API 202 + status); import-linter contract for `jobs` | Haiku |
| 7 | Review, measure quiz latency during an upload, merge; deploy only with the user's approval | Opus |

Order: 1 → 2 → (3 ‖ 4 ‖ 5) → 6 → 7.

### Idea 1: sense from the sentence + `which_meaning`
| # | Task | Tier |
|---|------|------|
| 1 | Choose ranking, tie-breaks, storage (`sense_rank`); ask the user about the new question type | Opus |
| 2 | `dictionary/senses.py`: `rank_senses(lemma, pos, sentence) -> list[int]` (pure) | Sonnet |
| 3 | Fixture of 40 hand-checked (lemma, sentence, expected sense) cases; tests for 2 | Haiku |
| 4 | Migration adding nullable `sense_rank` (no backfill) + wiring in extraction | Haiku |
| 5 | `reindex_senses` command for existing books (copy of `reindex_chapters`, as a job) | Haiku |
| 6 | `which_meaning` generator + selection | Sonnet |
| 7 | Frontend: render the new type (reuse the multiple-choice layout), tests | Haiku |
| 8 | Check accuracy on the fixture (target ≥ 80%, better than sense 0), merge | Opus |

Order: 1 → (2 + 3) ‖ 4 → 5 → 6 → 7 → 8.

### Ideas 11 + 10: Gutenberg on demand + public primers
| # | Task | Tier |
|---|------|------|
| 1 | Catalogue source, throttling, dedupe, URL scheme, what a primer shows; confirm with the user | Opus |
| 2 | `library/catalogue.py`: load the bundled CSV, search title/author | Sonnet |
| 3 | `POST /library/gutenberg/{id}` reusing `seed_classics.download` as a job | Haiku |
| 4 | Frontend search box + "Add" on the Classics shelf | Haiku |
| 5 | Primer page template, route, attribution footer, sitemap | Sonnet |
| 6 | Caddy cache rules, `robots.txt`, tests for 2, 3, 5 | Haiku |
| 7 | Review, check legal text, merge | Opus |

Order: 1 → (2 ‖ 5) → (3, 4, 6) → 7.

### Quick wins: typed recall (3) and book-fit preview (7)
| # | Task | Tier |
|---|------|------|
| 1 | Specs: typed-answer matching (edit distance ≤ 1), unlock score; `book_fit()` formula; confirm with the user | Opus |
| 2 | `QuestionType.TYPED` generator + grading | Sonnet |
| 3 | `readiness.book_fit(user, document)` + endpoint | Sonnet |
| 4 | Tests for 2 and 3; enum/migration if needed | Haiku |
| 5 | Frontend: typed input with first-letter hint; fit card on the Classics shelf and upload result | Haiku |
| 6 | Review, merge | Opus |

Confusion pairs (2) follows the same shape: Sonnet builds the aggregate, Haiku the `word_confusions` migration and
tests. All of these can run in parallel with the big items; the one hard cross-dependency is the jobs core (13.2)
before `reindex_senses` (1.5) and the Gutenberg add endpoint (11.3).

**False economies** (keep with the manager or Sonnet): scoring/decay changes, wrong-option safety, migrations that
backfill data, debugging integration or flaky failures, database session handling, legal and attribution text.

### Cost and speed
About half the tasks suit Haiku (tests, migrations, config, wiring), a third Sonnet (new modules), the rest Opus
(specs, decisions, reviews: nearly all the judgement). Parallel worktrees are the real speed-up; the manager reviews
one PR at a time.

## UI review (11 Nov 2026, Fable)

Findings: one consistent token set and a strong quiz screen; but ~80 px of brand header on every phone page,
six tiny tabs (0.68rem), the week shown twice on Today, three bars above the quiz word, one 3,880-line CSS file
(28 font sizes, 23 radii, ~35 raw colours), no landing page for visitors, one 747 KB bundle.

**Chosen to build (11 Nov 2026), in this order:**
1. Design tokens in `:root` (space, radius, text, gold/ninja/bad-deep/cream) — manager, no visual change.
2. Wave 1: **page headings + titles** (brand header hidden on phones only; each page's heading is its `h1`;
   `document.title` per route) · **load screens on demand** (`React.lazy` per route, skip link, tab labels
   ≥ 0.75rem, no grey filter on inactive tab icons).
3. Wave 2: **one compact quiz header** (close · session progress · Ninja meter · coins; today's goal and streak
   move to the feedback card and session summary; the sparkline moves to Me) and **one week view on Today** ·
   **Settings in four headed sections** (Appearance, Learning, Reminders, Account) · **public landing page** for
   visitors at `/` (a live sample question built from the quiz components, the classics' covers linking to
   `/classics`, sign up / log in, Open Graph tags).
4. Wave 3: **cleanup checklist** (mechanical, Haiku): merge duplicate rules (`.feedback`, `.link-button`,
   `.readings`, `.app__header`, `a.primary`/`button.primary`, `a.secondary`/`button.raised`); raw colours →
   tokens (illustrations like `.market`/`.stall` keep local values); radii → `--radius-*` (6–8 → s, 10–14 → m,
   16–20 → l, 24 → xl, 999 → pill); content widths → `--measure-*`; `.panel` always a card; shared
   `PageTitle`, `EmptyState`, `Toast`, `SegmentedControl` components; split `index.css` by feature.

Not chosen yet: five tabs (Compete tab, Shop in Today), bigger quiz word / two-column options, "I know this"
in a menu with Undo, streak-at-risk nudge, Words filter chips, shared chapter word-list component.
