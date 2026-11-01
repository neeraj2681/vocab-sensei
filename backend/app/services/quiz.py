"""The never-ending quiz (docs/PROJECT_PLAN.md §5.3).

There are no rounds: the screen always shows the user's newest unanswered question, and answering it
makes the next one. Each answer changes the word's score (+5 / -10, never below 0) and the lifetime
score at the top (+5 / -10 every time; only the total never goes below 0). Both changes are
logged; the lifetime score is the sum of the points. A word isn't asked again within
`spacing` questions; if the user has fewer words than that, it may come back sooner, but then the
answer is practice and doesn't score.

Words in progress are only asked while one of the user's current reads uses them: stopping a book
pauses its words (progress kept) until it's read again. Learned words still come back for review
from any book, so stopping a book doesn't mean forgetting its words.
"""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from random import Random
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import QuestionType, WordStatus
from app.db.models import Question, QuizAnswer, UserWord, Word
from app.dictionary.types import Dictionary
from app.quiz.questions import (
    Candidate,
    DefinitionQuestionGenerator,
    FillInBlankQuestionGenerator,
    NotEnoughDistractorsError,
    QuestionGenerator,
    QuestionNotPossibleError,
    ReverseQuestionGenerator,
    Target,
    blank_out,
)
from app.quiz.selection import Pool, choose_pool, choose_question_type, streak
from app.repositories.learning import LearningRepository
from app.repositories.quiz import QuizRepository
from app.scoring.rules import (
    WordProgress,
    answer_points,
    apply_answer,
    current_status,
    effective_score,
    mark_known,
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


@dataclass(frozen=True)
class Focus:
    """Quiz only the words of one chapter ("Study this chapter")."""

    document_id: int
    chapter_index: int


@dataclass(frozen=True)
class Stats:
    total: int  # lifetime points
    today: int  # answers given today, in the user's time zone
    daily_goal: int
    streak: int  # days in a row with at least `daily_goal` answers


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


@dataclass(frozen=True)
class HistoryPoint:
    number: int  # 1 = the first question ever answered
    total: int  # lifetime points after this answer
    correct: bool
    answered_at: datetime


@dataclass(frozen=True)
class PractisedWord:
    lemma: str
    book: str | None  # the book the quiz takes the word from
    meaning: str | None  # in that book's sense
    progress: int  # 0-100: how far the word's score is towards "learned"
    learned: bool


def quiz_stats(repo: QuizRepository, goal: int, user_id: int, now: datetime, tz: ZoneInfo) -> Stats:
    """Lifetime points, today's answers and the streak, with days in the user's time zone."""
    today = now.astimezone(tz).date()
    since = datetime.combine(today - timedelta(days=_STREAK_DAYS), datetime.min.time(), tz)
    per_day: Counter[date] = Counter(
        a.answered_at.astimezone(tz).date() for a in repo.answers(user_id, since)
    )
    return Stats(
        total=repo.total_points(user_id),
        today=per_day[today],
        daily_goal=goal,
        streak=streak(per_day, today, goal),
    )


def _progress(word: UserWord) -> WordProgress:
    return WordProgress(score=word.score, status=word.status, learned_at=word.learned_at)


class QuizService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        dictionary: Callable[[], Dictionary],
        rng: Random | None = None,
        generators: dict[QuestionType, QuestionGenerator] | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._quiz = settings.quiz
        self._dictionary = dictionary
        self._rng = rng or Random()
        options = self._quiz.options_per_question
        self._generators = generators or {
            QuestionType.DEFINITION_MCQ: DefinitionQuestionGenerator(options),
            QuestionType.REVERSE: ReverseQuestionGenerator(options),
            QuestionType.FILL_IN_BLANK: FillInBlankQuestionGenerator(options),
        }
        self._repo = QuizRepository(session)
        self._learning = LearningService(session)
        self._learning_repo = LearningRepository(session)

    # Asking

    def current_question(self, user_id: int, now: datetime, focus: Focus | None = None) -> Question:
        """The question on screen: the unanswered one, or a new one (from `focus` if given)."""
        pending = self._repo.pending_question(user_id)
        if pending is not None:
            return pending
        question = self._ask(user_id, now, focus)
        self._session.commit()
        return question

    def _ask(self, user_id: int, now: datetime, focus: Focus | None) -> Question:
        recent = self._repo.recently_answered_word_ids(user_id, self._quiz.spacing)
        unusable: set[int] = set()  # words we couldn't build a question for
        # First try words not asked recently; if there are none, allow repeats (they don't score).
        for allow_recent in (False, True):
            while True:
                excluded = unusable if allow_recent else unusable | recent
                word_id = self._pick_word(user_id, now, excluded, focus)
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

    def _pick_word(
        self, user_id: int, now: datetime, exclude: set[int], focus: Focus | None
    ) -> int | None:
        pools: dict[Pool, int] = {}
        if focus is None:
            new = [
                item.word.id for item in self._learning.next_new_words(user_id, len(exclude) + 1)
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

        new = [word_id for word_id in new if usable(word_id)]
        if new:
            pools[Pool.NEW] = new[0]
        learning = [
            w
            # Paused while none of the user's current reads uses them; progress is kept.
            for w in self._repo.words_with_status(
                user_id, WordStatus.LEARNING, exclude, in_current_reads=True
            )
            if usable(w.word_id)
        ]
        if learning:
            pools[Pool.LEARNING] = learning[0].word_id
        due = [
            w
            for w in self._repo.words_with_status(user_id, WordStatus.LEARNED, exclude)
            if usable(w.word_id)
            and current_status(_progress(w), now, self._settings.scoring) is WordStatus.LEARNING
        ]
        if due:
            pools[Pool.REVIEW] = due[0].word_id

        weights = {
            Pool.NEW: self._quiz.new_weight,
            Pool.LEARNING: self._quiz.learning_weight,
            Pool.REVIEW: self._quiz.review_weight,
        }
        pool = choose_pool(list(pools), weights, self._rng)
        return pools[pool] if pool is not None else None

    def _build(self, user_id: int, word_id: int) -> Question | None:
        word = self._repo.word(word_id)
        if word is None:
            return None
        found = self._repo.occurrence(user_id, word_id)
        occurrence, document = found if found else (None, None)
        definitions = definitions_in_context(word, occurrence.pos if occurrence else None)
        if not definitions:
            return None

        correct = definitions[0]
        target = Target(
            lemma=word.lemma,
            definition=correct.text,
            synonyms=self._dictionary().synonyms(word.lemma),
            context_sentence=occurrence.context_sentence if occurrence else None,
            context_form=occurrence.context_form if occurrence else None,
        )
        progress = self._repo.user_word(user_id, word_id)
        kind = choose_question_type(
            progress.score if progress else 0,
            blank_out(target.context_sentence, target.context_form) is not None,
            self._rng,
            reverse_from=self._quiz.reverse_from_score,
            fill_from=self._quiz.fill_from_score,
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
        counted = question.word_id not in self._repo.recently_answered_word_ids(
            user_id, self._quiz.spacing
        )
        word = self._user_word(user_id, question.word_id)
        delta = 0
        if counted and word.status is not WordStatus.KNOWN:
            rules = self._settings.scoring
            before = effective_score(_progress(word), now, rules)
            after = apply_answer(_progress(word), correct=correct, now=now, rules=rules)
            word.score, word.status, word.learned_at = after.score, after.status, after.learned_at
            delta = after.score - before
        word.last_reviewed_at = now
        points = answer_points(
            self._repo.total_points(user_id),
            correct=correct,
            counted=counted,
            rules=self._settings.scoring,
        )

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
        )

    def _word_and_meaning(self, user_id: int, word_id: int) -> tuple[str, str | None]:
        word = self._repo.word(word_id)
        if word is None:
            return "", None
        return word.lemma, self._meaning_and_book(user_id, word)[0]

    def _meaning_and_book(self, user_id: int, word: Word) -> tuple[str | None, str | None]:
        found = self._repo.occurrence(user_id, word.id)
        definitions = definitions_in_context(word, found[0].pos if found else None)
        return (definitions[0].text if definitions else None), (found[1].title if found else None)

    def know(self, user_id: int, question_id: int, now: datetime) -> None:
        """The "I know this" button: the word is never asked again; a new question replaces it."""
        question = self._unanswered(user_id, question_id)
        word = self._user_word(user_id, question.word_id)
        known = mark_known(_progress(word))
        word.status = known.status
        word.last_reviewed_at = now
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

    def stats(self, user_id: int, now: datetime, tz: ZoneInfo) -> Stats:
        return quiz_stats(self._repo, self._quiz.daily_goal, user_id, now, tz)

    def practised_words(self, user_id: int, now: datetime) -> list[PractisedWord]:
        """Learned words first, then the rest by progress."""
        rules = self._settings.scoring
        words = []
        for user_word, word in self._repo.practised_words(user_id):
            progress = _progress(user_word)
            meaning, book = self._meaning_and_book(user_id, word)
            score = effective_score(progress, now, rules)
            words.append(
                PractisedWord(
                    lemma=word.lemma,
                    book=book,
                    meaning=meaning,
                    progress=min(100, score * 100 // rules.learned_threshold),
                    learned=current_status(progress, now, rules) is WordStatus.LEARNED,
                )
            )
        return sorted(words, key=lambda w: (not w.learned, -w.progress, w.lemma))

    def history(self, user_id: int) -> list[HistoryPoint]:
        points: list[HistoryPoint] = []
        total = 0
        for number, answer in enumerate(self._repo.answers(user_id), start=1):
            total += answer.points
            points.append(HistoryPoint(number, total, answer.correct, answer.answered_at))
        return points
