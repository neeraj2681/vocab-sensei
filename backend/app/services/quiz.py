"""The never-ending quiz (docs/PROJECT_PLAN.md §5.3).

There are no rounds: the screen always shows the user's newest unanswered question, and answering it
makes the next one. Each answer changes the word's score (+10 / -5, never below 0; -10 for a miss
on a word learned before, while it's above 50) and the lifetime score at the top (+5 / the same
miss penalty every time; only the total never goes below 0). Both changes are
logged; the lifetime score is the sum of the points. A word isn't asked again within
`spacing` questions (one answered wrong comes back after `retry_after`, while it's fresh); if the
user has fewer words than that, it may come back sooner, but then the answer is practice and
doesn't score.

Words in progress are only asked while one of the user's current reads uses them: stopping a book
pauses its words (progress kept) until it's read again. Learned words still come back for review
from any book, so stopping a book doesn't mean forgetting its words.
"""

from collections import Counter
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from random import Random
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import QuestionType, WordStatus
from app.db.models import GoalChange, Question, QuizAnswer, User, UserWord, Word
from app.dictionary.types import Dictionary
from app.quiz.learning_list import share_places
from app.quiz.questions import (
    Candidate,
    DefinitionQuestionGenerator,
    FillInBlankQuestionGenerator,
    NotEnoughDistractorsError,
    QuestionGenerator,
    QuestionNotPossibleError,
    ReverseQuestionGenerator,
    Target,
    WhichMeaningQuestionGenerator,
    blank_out,
)
from app.quiz.selection import (
    DailyGoal,
    Pool,
    choose_pool,
    choose_question_type,
    closest_or_oldest,
    learning_cap,
    review_weight,
    spacing_rules,
    streak,
)
from app.quiz.shop import DOUBLE_COINS_MULTIPLIER, Freeze, Item, freezes_to_use
from app.repositories.learning import LearningRepository
from app.repositories.quiz import QuizRepository
from app.repositories.readings import ReadingRepository
from app.scoring.rules import (
    WordProgress,
    answer_points,
    apply_answer,
    combo_multiplier,
    current_status,
    effective_score,
    mark_known,
    miss_penalty,
)
from app.services.learning import LearningService
from app.services.words import definitions_in_context

_STREAK_DAYS = 400  # streaks are counted over at most this many days


class QuizError(Exception):
    """Base class for problems the API reports to the user."""


class NoWordsError(QuizError):
    pass


class QuestionNotFoundError(QuizError):
    pass


class AlreadyAnsweredError(QuizError):
    pass


class InvalidChoiceError(QuizError):
    pass


class WordNotKnownError(QuizError):
    pass


@dataclass(frozen=True)
class Focus:
    """Quiz only the words of one chapter ("Study this chapter")."""

    document_id: int
    chapter_index: int


@dataclass(frozen=True)
class Day:
    date: date
    answers: int
    met: bool  # judged by the goal the user had that day, like the streak (or frozen)
    points: int  # net change in the lifetime score that day (wrong answers subtract)
    frozen: bool = False  # missed, but a streak freeze kept the streak


@dataclass(frozen=True)
class Stats:
    total: int  # lifetime points
    today: int  # answers given today, in the user's time zone
    daily_goal: int
    streak: int  # days in a row with at least `daily_goal` answers
    week: list[Day]  # the last seven days, oldest first, today last
    combo: int = 0  # right answers in a row
    combo_after: int = 5  # Ninja Mode starts after this many in a row...
    combo_multiplier: int = 2  # ...and multiplies the coins of right answers by this
    double_coins_until: datetime | None = None  # a Shop item doubling right answers' coins
    learned_today: int = 0  # words that reached "learned" today


@dataclass(frozen=True)
class AnswerOutcome:
    correct: bool
    correct_index: int
    score_delta: int  # change in the word's score
    points: int  # change in the lifetime score
    counted: bool  # False when the word was asked again too soon to score
    lemma: str  # the word, revealed after answering (reverse and fill-in questions hide it)
    meaning: str | None  # its meaning in the book's sense
    word: UserWord
    question: Question
    stats: Stats
    picked_word: str | None = None  # a wrong meaning pick: the word that meaning belongs to


RECALL_FIRST_ABOVE = 50  # words scoring above this hide their options for a moment


@dataclass(frozen=True)
class Preview:
    """Everything the screen shows after an answer, for both outcomes, sent with the question so
    tapping an option needs no wait. The saved answer then confirms it."""

    lemma: str
    meaning: str | None
    sentence: str | None
    counted: bool  # False when the word came back too soon to score
    points_if_right: int  # before Ninja Mode: the screen doubles it while its run is long enough
    points_if_wrong: int
    learned_if_right: bool
    recall_first: bool = False  # the word is well known: try to remember before seeing options


@dataclass(frozen=True)
class HistoryPoint:
    number: int  # 1 = the first question ever answered
    total: int  # lifetime points after this answer
    correct: bool
    answered_at: datetime


@dataclass(frozen=True)
class _InBook:
    meaning: str | None
    book: str | None
    sentence: str | None


@dataclass(frozen=True)
class PractisedWord:
    lemma: str
    book: str | None  # the book the quiz takes the word from
    meaning: str | None  # in that book's sense
    sentence: str | None  # where the book uses it
    progress: int  # 0-100: how far the word's score is towards "learned"
    learned: bool
    known: bool = False  # marked "I know this": never asked again
    later: bool = False  # in progress but waiting: beyond the words being practised now
    also_in: tuple[str, ...] = ()  # the user's other current reads that use the word


def daily_goal(user: User, tz: ZoneInfo) -> DailyGoal:
    """The user's goal and its history, with each change starting on a day in their time zone."""
    steps = tuple((c.since.astimezone(tz).date(), c.goal) for c in user.goal_changes)
    return DailyGoal(user.daily_goal, steps)


def quiz_stats(repo: QuizRepository, user: User, now: datetime, tz: ZoneInfo) -> Stats:
    """Lifetime points, today's answers and the streak, with days in the user's time zone."""
    today = now.astimezone(tz).date()
    since = datetime.combine(today - timedelta(days=_STREAK_DAYS), datetime.min.time(), tz)
    answers = repo.answers(user.id, since)
    per_day: Counter[date] = Counter(a.answered_at.astimezone(tz).date() for a in answers)
    points: Counter[date] = Counter()
    for answer in answers:
        points[answer.answered_at.astimezone(tz).date()] += answer.points
    goal = daily_goal(user, tz)
    days = [today - timedelta(days=back) for back in range(6, -1, -1)]
    points.update(repo.quest_coins_by_day(user.id, days[0]))  # quest rewards count on their day
    frozen = repo.frozen_days(user.id)
    return Stats(
        total=repo.total_points(user.id),
        today=per_day[today],
        daily_goal=goal.on(today),
        streak=streak(per_day, today, goal, frozen),
        week=[
            Day(
                day,
                per_day[day],
                per_day[day] >= goal.on(day) or day in frozen,
                points[day],
                frozen=day in frozen,
            )
            for day in days
        ],
        combo=user.combo,
        double_coins_until=user.double_coins_until,
        learned_today=repo.learned_since(user.id, datetime.combine(today, time.min, tz)),
    )


def _progress(word: UserWord) -> WordProgress:
    return WordProgress(
        score=word.score,
        status=word.status,
        learned_at=word.learned_at,
        was_learned=word.was_learned,
        interval_weeks=word.interval_weeks,
    )


class QuizService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        dictionary: Callable[[], Dictionary],
        rng: Random | None = None,
        generators: dict[QuestionType, QuestionGenerator] | None = None,
        speaking: bool = False,
    ) -> None:
        self._session = session
        self._speaking = speaking  # the screen can record: "say this word" questions may come
        self._settings = settings
        self._quiz = settings.quiz
        self._dictionary = dictionary
        self._rng = rng or Random()
        options = self._quiz.options_per_question
        self._generators = generators or {
            QuestionType.DEFINITION_MCQ: DefinitionQuestionGenerator(options),
            QuestionType.REVERSE: ReverseQuestionGenerator(options),
            QuestionType.FILL_IN_BLANK: FillInBlankQuestionGenerator(options),
            QuestionType.WHICH_MEANING: WhichMeaningQuestionGenerator(options),
        }
        self._repo = QuizRepository(session)
        self._learning = LearningService(session)
        self._learning_repo = LearningRepository(session)
        self._readings = ReadingRepository(session)

    # Asking

    def _check_speaking(self, user_id: int, now: datetime) -> None:
        """No "say this word" questions while the user has paused them."""
        paused = self._user(user_id).speaking_paused_until
        if paused is not None and paused > now:
            self._speaking = False

    def _pending(self, user_id: int, limit: int) -> list[Question]:
        """Unanswered questions, dropping "say this word" ones when the screen can't record."""
        if not self._speaking:
            for question in self._repo.unanswered(user_id, limit=10):
                if question.type is QuestionType.SAY_WORD:
                    self._session.delete(question)
            self._session.flush()
        return self._repo.unanswered(user_id, limit=limit)

    def skip(self, user_id: int, question_id: int, now: datetime) -> None:
        """ "Can't speak right now": drops an unanswered "say this word" question, and no more
        come for `pause_minutes`."""
        question = self._unanswered(user_id, question_id)
        if question.type is QuestionType.SAY_WORD:
            self._session.delete(question)
            minutes = self._settings.speech.pause_minutes
            self._user(user_id).speaking_paused_until = now + timedelta(minutes=minutes)
            self._session.commit()

    def unanswered_question(self, user_id: int, question_id: int) -> Question:
        return self._unanswered(user_id, question_id)

    def current_question(self, user_id: int, now: datetime, focus: Focus | None = None) -> Question:
        """The question on screen: the oldest unanswered one, or a new one (from `focus`)."""
        self._check_speaking(user_id, now)
        pending = self._pending(user_id, limit=1)
        if pending:
            return pending[0]
        question = self._ask(user_id, now, focus)
        self._session.commit()
        return question

    def upcoming(
        self, user_id: int, now: datetime, focus: Focus | None = None
    ) -> tuple[Question, Question | None]:
        """The question on screen and the one kept ready after it, so the screen can move on
        without a request. Choosing the second a step early picks the same word: the first is
        excluded either way (a word isn't asked twice within `spacing` questions)."""
        self._check_speaking(user_id, now)
        pending = self._pending(user_id, limit=2)
        if not pending:
            pending = [self._ask(user_id, now, focus)]
        if len(pending) == 1:
            with suppress(NoWordsError):  # nothing more to ask: the screen finds out there
                pending.append(self._ask(user_id, now, focus))
        self._session.commit()
        return pending[0], pending[1] if len(pending) > 1 else None

    def _ask(self, user_id: int, now: datetime, focus: Focus | None) -> Question:
        recent, retry = self._spacing(user_id)
        waiting = {q.word_id for q in self._repo.unanswered(user_id)}
        recent |= waiting  # not twice in a row
        retry = [word_id for word_id in retry if word_id not in waiting]
        unusable: set[int] = set()  # words we couldn't build a question for
        # First try words not asked recently; if there are none, allow repeats (they don't score).
        for allow_recent in (False, True):
            while True:
                excluded = unusable if allow_recent else unusable | recent
                word_id = self._pick_word(user_id, now, excluded, focus, retry)
                if word_id is None:
                    break
                question = self._build(user_id, word_id)
                if question is not None:
                    self._repo.add(question)
                    self._session.flush()
                    return question
                unusable.add(word_id)
        if focus is not None and not unusable:
            raise NoWordsError("Chapter ready! Every word in it is learned or known")
        if unusable:
            raise NoWordsError(
                "There aren't enough words yet to make four options; add another book"
            )
        raise NoWordsError("Start reading a book to get questions")

    def _spacing(self, user_id: int) -> tuple[set[int], list[int]]:
        """Words too soon to ask again, and words answered wrong that are due back now."""
        spacing = self._quiz.spacing
        recent = self._repo.recent_answers(user_id, 2 * spacing)
        return spacing_rules(recent, spacing, self._quiz.retry_after)

    def _cap(self, user_id: int) -> int:
        """Words in progress at once: about one per answer of the daily goal."""
        quiz = self._quiz
        return learning_cap(
            self._user(user_id).daily_goal, quiz.learning_cap_min, quiz.learning_cap_max
        )

    def _pick_word(
        self,
        user_id: int,
        now: datetime,
        exclude: set[int],
        focus: Focus | None,
        retry: Sequence[int] = (),
    ) -> int | None:
        pools: dict[Pool, int] = {}
        # At most `_cap` words in progress, shared equally by the current reads (see
        # `_ranked_learning`): those are practised; the rest wait with their progress.
        ranked, per_book = self._ranked_learning(user_id)
        cap = self._cap(user_id)
        if focus is None:
            # A new word comes in only when a place is free: anywhere under the cap, or in a
            # book that has fewer words in progress than its share.
            only = None
            if len(ranked) >= cap:
                books = [r.document_id for r in self._readings.list_for(user_id)]
                share = cap // max(len(books), 1)
                only = {book for book in books if per_book.get(book, 0) < share}
            new = [
                item.word.id
                for item in (
                    self._learning.next_new_words(user_id, len(exclude) + 1, only)
                    if only != set()
                    else []
                )
            ]
            allowed: set[int] | None = None
        else:
            new = [
                word.id
                for _, word, _ in self._learning_repo.new_words_in_chapter(
                    user_id, focus.document_id, focus.chapter_index, len(exclude) + 1
                )
            ]
            allowed = self._learning_repo.chapter_word_ids(focus.document_id, focus.chapter_index)

        def usable(word_id: int) -> bool:
            return word_id not in exclude and (allowed is None or word_id in allowed)

        # A word just answered wrong comes back first, while it's fresh.
        for word_id in retry:
            progress = self._repo.user_word(user_id, word_id)
            if usable(word_id) and progress is not None and progress.status is not WordStatus.KNOWN:
                return word_id

        active = {w.word_id for w in ranked[:cap]}
        new = [word_id for word_id in new if usable(word_id)]
        if new:
            pools[Pool.NEW] = new[0]
        learning = [
            w
            # Paused while none of the user's current reads uses them; progress is kept.
            for w in self._repo.words_with_status(
                user_id, WordStatus.LEARNING, exclude, in_current_reads=True
            )
            if usable(w.word_id) and (allowed is not None or w.word_id in active)
        ]
        if learning:
            pools[Pool.LEARNING] = closest_or_oldest(learning, lambda w: w.score, self._rng).word_id
        rules = self._settings.scoring
        due = [
            w
            for w in self._repo.words_with_status(user_id, WordStatus.LEARNED, exclude)
            if usable(w.word_id) and current_status(_progress(w), now, rules) is WordStatus.LEARNING
        ]
        if due:  # the most faded first, so a word at risk is saved before it slips further
            pools[Pool.REVIEW] = min(
                due, key=lambda w: effective_score(_progress(w), now, rules)
            ).word_id

        weights = {
            Pool.NEW: self._quiz.new_weight,
            Pool.LEARNING: self._quiz.learning_weight,
            # More turns while many learned words are due, so a backlog is caught up.
            Pool.REVIEW: review_weight(
                len(due),
                base=self._quiz.review_weight,
                per=self._quiz.due_per_review_weight,
                maximum=self._quiz.max_review_weight,
            ),
        }
        pool = choose_pool(list(pools), weights, self._rng)
        return pools[pool] if pool is not None else None

    def _build(self, user_id: int, word_id: int) -> Question | None:
        word = self._repo.word(word_id)
        if word is None:
            return None
        found = self._repo.occurrence(user_id, word_id)
        occurrence, document = found if found else (None, None)
        definitions = definitions_in_context(
            word,
            occurrence.pos if occurrence else None,
            occurrence.meaning_rank if occurrence else None,
        )
        if not definitions:
            return None

        correct = definitions[0]
        target = Target(
            lemma=word.lemma,
            definition=correct.text,
            synonyms=self._dictionary().synonyms(word.lemma),
            context_sentence=occurrence.context_sentence if occurrence else None,
            context_form=occurrence.context_form if occurrence else None,
            other_meanings=tuple(d.text for d in definitions[1:] if d.pos == correct.pos),
        )
        progress = self._repo.user_word(user_id, word_id)
        kind = choose_question_type(
            progress.score if progress else 0,
            blank_out(target.context_sentence, target.context_form) is not None,
            self._rng,
            reverse_from=self._quiz.reverse_from_score,
            fill_from=self._quiz.fill_from_score,
            can_ask_meaning=(
                occurrence is not None
                and occurrence.meaning_rank is not None
                and len(definitions) >= 2
            ),
            meaning_from=self._quiz.meaning_from_score,
        )
        score = progress.score if progress else 0
        speech = self._settings.speech
        if (
            self._speaking
            and score >= self._quiz.fill_from_score
            and self._rng.random() < speech.say_word_share
        ):
            return Question(  # say it aloud: right or not decided by speech recognition
                user_id=user_id,
                document_id=document.id if document else None,
                word_id=word.id,
                type=QuestionType.SAY_WORD,
                prompt=word.lemma,
                options=["said it", "not yet"],
                correct_index=0,
                generator="speech",
                source_sentence=target.context_sentence,
            )
        needed = self._quiz.options_per_question - 1
        # Closest first: same part of speech and similar difficulty, then wider, then anything.
        window = self._quiz.distractor_zipf_window
        for pos, zipf, width in (
            (correct.pos, word.zipf_frequency, window),
            (correct.pos, word.zipf_frequency, window * 4),
            (correct.pos, None, None),
            (None, None, None),
        ):
            pool = [
                Candidate(lemma, text)
                for lemma, text in self._repo.distractors(word.id, pos, zipf, width, needed * 5)
            ]
            try:
                draft = self._generators[kind].generate(target, pool, self._rng)
            except NotEnoughDistractorsError:
                continue
            except QuestionNotPossibleError:  # e.g. the sentence lost the word; ask its meaning
                kind = QuestionType.DEFINITION_MCQ
                draft = self._generators[kind].generate(target, pool, self._rng)
            return Question(
                user_id=user_id,
                document_id=document.id if document else None,
                word_id=word.id,
                type=draft.type,
                prompt=draft.prompt,
                options=draft.options,
                correct_index=draft.correct_index,
                generator=draft.generator,
                source_sentence=draft.source_sentence,
            )
        return None

    # Answering

    def answer(
        self, user_id: int, question_id: int, chosen_index: int, now: datetime, tz: ZoneInfo
    ) -> AnswerOutcome:
        question = self._unanswered(user_id, question_id)
        if not 0 <= chosen_index < len(question.options):
            raise InvalidChoiceError(f"Pick an option from 0 to {len(question.options) - 1}")

        correct = chosen_index == question.correct_index
        counted = question.word_id not in self._spacing(user_id)[0]
        word = self._user_word(user_id, question.word_id)
        delta = 0
        rules = self._settings.scoring
        miss = miss_penalty(_progress(word), now, rules)  # coins lose what the word loses
        if counted and word.status is not WordStatus.KNOWN:
            before = effective_score(_progress(word), now, rules)
            after = apply_answer(_progress(word), correct=correct, now=now, rules=rules)
            word.score, word.status, word.learned_at = after.score, after.status, after.learned_at
            word.was_learned = after.was_learned
            word.interval_weeks = after.interval_weeks
            delta = after.score - before
        word.last_reviewed_at = now
        points = answer_points(
            self._repo.total_points(user_id),
            correct=correct,
            counted=counted,
            rules=rules,
            miss=miss,
        )
        user = self._user(user_id)
        if correct:  # Ninja Mode: doubled coins once the run is long enough, then the run grows
            points *= combo_multiplier(user.combo, self._settings.scoring)
            if user.double_coins_until and now < user.double_coins_until:
                points *= DOUBLE_COINS_MULTIPLIER  # the Shop's double coins (x4 with Ninja Mode)
            user.combo += 1
        else:
            user.combo = 0

        self._repo.add(
            QuizAnswer(
                user_id=user_id,
                word_id=question.word_id,
                question_id=question.id,
                chosen_index=chosen_index,
                correct=correct,
                score_delta=delta,
                points=points,
                answered_at=now,
            )
        )
        self._session.commit()
        lemma, meaning = self._word_and_meaning(user_id, question.word_id)
        picked_word = None
        if not correct and question.type is QuestionType.DEFINITION_MCQ:
            picked_word = self._repo.word_for_definition(
                question.options[chosen_index], question.word_id
            )
        return AnswerOutcome(
            correct=correct,
            correct_index=question.correct_index,
            score_delta=delta,
            points=points,
            counted=counted,
            lemma=lemma,
            meaning=meaning,
            word=word,
            question=question,
            stats=self.stats(user_id, now, tz),
            picked_word=picked_word,
        )

    def preview(self, user_id: int, question: Question, now: datetime) -> Preview:
        """What answering `question` right or wrong would do, by the same rules as `answer`."""
        rules = self._settings.scoring
        counted = question.word_id not in self._spacing(user_id)[0]
        existing = self._repo.user_word(user_id, question.word_id)
        progress = _progress(existing) if existing else WordProgress()
        status_if_right = progress.status
        if counted and progress.status is not WordStatus.KNOWN:
            status_if_right = apply_answer(progress, correct=True, now=now, rules=rules).status
        total = self._repo.total_points(user_id)
        lemma, meaning = self._word_and_meaning(user_id, question.word_id)
        return Preview(
            lemma=lemma,
            meaning=meaning,
            sentence=question.source_sentence,
            counted=counted,
            points_if_right=answer_points(total, correct=True, counted=counted, rules=rules),
            points_if_wrong=answer_points(
                total,
                correct=False,
                counted=counted,
                rules=rules,
                miss=miss_penalty(progress, now, rules),
            ),
            learned_if_right=status_if_right is WordStatus.LEARNED,
            recall_first=question.type is not QuestionType.SAY_WORD
            and effective_score(progress, now, rules) > RECALL_FIRST_ABOVE,
        )

    def _word_and_meaning(self, user_id: int, word_id: int) -> tuple[str, str | None]:
        word = self._repo.word(word_id)
        if word is None:
            return "", None
        return word.lemma, self._in_book(user_id, word).meaning

    def _in_book(self, user_id: int, word: Word) -> _InBook:
        found = self._repo.occurrence(user_id, word.id)
        definitions = definitions_in_context(
            word,
            found[0].pos if found else None,
            found[0].meaning_rank if found else None,
        )
        return _InBook(
            meaning=definitions[0].text if definitions else None,
            book=found[1].title if found else None,
            sentence=found[0].context_sentence if found else None,
        )

    def know(self, user_id: int, question_id: int, now: datetime) -> None:
        """The "I know this" button: the word is never asked again; a new question replaces it."""
        question = self._unanswered(user_id, question_id)
        word = self._user_word(user_id, question.word_id)
        known = mark_known(_progress(word))
        word.status = known.status
        word.last_reviewed_at = now
        self._user(user_id).combo = 0  # like a wrong answer: it ends a Ninja run
        self._repo.add(
            QuizAnswer(
                user_id=user_id,
                word_id=question.word_id,
                question_id=question.id,
                chosen_index=None,
                correct=True,
                score_delta=0,
                answered_at=now,
            )
        )
        self._session.commit()

    def end_combo(self, user_id: int) -> None:
        """The player stopped after a session: Ninja Mode (and the run of right answers) ends."""
        self._user(user_id).combo = 0
        self._session.commit()

    def learn_again(self, user_id: int, lemma: str) -> None:
        """Undoes "I know this", or takes a "probably known" word into learning: it starts from 0
        and the quiz asks it (soon, while one of the user's current reads uses it)."""
        word = self._repo.word_by_lemma(lemma)
        if word is None:
            raise WordNotKnownError(f"{lemma!r} isn't one of your words")
        user_word = self._repo.user_word(user_id, word.id)
        if user_word is None:  # never started: e.g. skipped as probably known
            user_word = UserWord(user_id=user_id, word_id=word.id, score=0)
            self._repo.add(user_word)
        elif user_word.status not in (WordStatus.KNOWN, WordStatus.NEW):
            raise WordNotKnownError(f"{lemma!r} is already being learned")
        user_word.status, user_word.score, user_word.learned_at = WordStatus.LEARNING, 0, None
        user_word.interval_weeks = 1
        user_word.was_learned = False
        self._session.commit()

    def _unanswered(self, user_id: int, question_id: int) -> Question:
        question = self._repo.question(user_id, question_id)
        if question is None:
            raise QuestionNotFoundError("Question not found")
        if self._repo.answer_for(question.id) is not None:
            raise AlreadyAnsweredError("This question has already been answered")
        return question

    def _user_word(self, user_id: int, word_id: int) -> UserWord:
        word = self._repo.user_word(user_id, word_id)
        if word is None:
            word = UserWord(user_id=user_id, word_id=word_id, score=0, status=WordStatus.NEW)
            self._repo.add(word)
        return word

    # Progress

    def apply_streak_freezes(self, user_id: int, now: datetime, tz: ZoneInfo) -> None:
        """Uses streak freezes for missed days since the last check (see app/quiz/shop.py)."""
        user = self._user(user_id)
        yesterday = now.astimezone(tz).date() - timedelta(days=1)
        checked = user.freezes_checked_through
        if checked is not None and checked >= yesterday:
            return
        if checked is None:  # the first look: freezes only cover days from now on
            user.freezes_checked_through = yesterday
            self._session.commit()
            return
        unused = self._repo.unused(user.id, Item.STREAK_FREEZE)
        if unused:
            since = datetime.combine(checked - timedelta(days=_STREAK_DAYS), time.min, tz)
            per_day: Counter[date] = Counter(
                a.answered_at.astimezone(tz).date() for a in self._repo.answers(user.id, since)
            )
            freezes = {p.id: p for p in unused}
            for day, freeze_id in freezes_to_use(
                per_day,
                daily_goal(user, tz),
                self._repo.frozen_days(user.id),
                [Freeze(p.id, p.bought_at.astimezone(tz).date()) for p in unused],
                checked + timedelta(days=1),
                yesterday,
            ):
                freezes[freeze_id].used_at = now
                freezes[freeze_id].used_for_day = day
        user.freezes_checked_through = yesterday
        self._session.commit()

    def stats(self, user_id: int, now: datetime, tz: ZoneInfo) -> Stats:
        self.apply_streak_freezes(user_id, now, tz)
        rules = self._settings.scoring
        return replace(
            quiz_stats(self._repo, self._user(user_id), now, tz),
            combo_after=rules.combo_after,
            combo_multiplier=rules.combo_multiplier,
        )

    def set_daily_goal(self, user_id: int, goal: int, now: datetime, tz: ZoneInfo) -> None:
        """Changes the goal from today on; earlier days keep the goal they had (see DailyGoal)."""
        user = self._user(user_id)
        if goal == user.daily_goal:
            return
        changes = user.goal_changes
        if not changes:  # the first change: remember the goal every earlier day had
            changes.append(GoalChange(goal=user.daily_goal, since=min(user.created_at, now)))
        elif changes[-1].since.astimezone(tz).date() == now.astimezone(tz).date():
            changes[-1].goal = goal  # changed again today: only today's goal moves
            user.daily_goal = goal
            self._session.commit()
            return
        changes.append(GoalChange(goal=goal, since=now))
        user.daily_goal = goal
        self._session.commit()

    def _user(self, user_id: int) -> User:
        user = self._session.get(User, user_id)
        if user is None:
            raise LookupError(f"no user {user_id}")
        return user

    def _ranked_learning(self, user_id: int) -> tuple[list[UserWord], dict[int, int]]:
        """Words in progress in the order they get a place among the ones practised (one from
        each current read in turn, each book's closest to learned first), and how many each
        book has."""
        by_book: dict[int, list[UserWord]] = {}
        for document_id, user_word in self._repo.learning_by_book(user_id):
            by_book.setdefault(document_id, []).append(user_word)
        ranked = share_places(list(by_book.values()), key=lambda w: w.word_id)
        return ranked, {book: len(words) for book, words in by_book.items()}

    def practised_words(self, user_id: int, now: datetime) -> list[PractisedWord]:
        """Learned words first, then the rest by progress, then the ones already known."""
        rules = self._settings.scoring
        practised_now = {w.word_id for w in self._ranked_learning(user_id)[0][: self._cap(user_id)]}
        reads = self._repo.current_read_titles(user_id)
        words = []
        for user_word, word in self._repo.practised_words(user_id):
            progress = _progress(user_word)
            in_book = self._in_book(user_id, word)
            also_in = tuple(title for title in reads.get(word.id, []) if title != in_book.book)
            known = user_word.status is WordStatus.KNOWN
            score = effective_score(progress, now, rules)
            words.append(
                PractisedWord(
                    lemma=word.lemma,
                    book=in_book.book,
                    meaning=in_book.meaning,
                    sentence=in_book.sentence,
                    progress=100 if known else min(100, score * 100 // rules.learned_threshold),
                    learned=not known
                    and current_status(progress, now, rules) is WordStatus.LEARNED,
                    known=known,
                    later=user_word.status is WordStatus.LEARNING
                    and user_word.word_id not in practised_now,
                    also_in=also_in,
                )
            )
        return sorted(words, key=lambda w: (w.known, not w.learned, -w.progress, w.lemma))

    def history(self, user_id: int) -> list[HistoryPoint]:
        points: list[HistoryPoint] = []
        total = 0
        for number, answer in enumerate(self._repo.answers(user_id), start=1):
            total += answer.points
            points.append(HistoryPoint(number, total, answer.correct, answer.answered_at))
        return points
