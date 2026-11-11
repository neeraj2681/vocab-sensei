"""What the public book pages show: public-domain books and their hardest words per chapter."""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models import Document
from app.repositories.public_pages import PublicPagesRepository
from app.services.words import definitions_in_context

WORDS_PER_CHAPTER = 20


@dataclass(frozen=True)
class PublicChapterSummary:
    number: int  # 1-based
    title: str | None
    word_count: int


@dataclass(frozen=True)
class PublicBook:
    slug: str
    title: str
    author: str | None
    chapters: list[PublicChapterSummary] = field(default_factory=list)


@dataclass(frozen=True)
class PublicWord:
    lemma: str
    meaning: str | None
    sentence: str | None
    form: str | None


@dataclass(frozen=True)
class PublicChapter:
    book: PublicBook
    number: int
    title: str | None
    words: list[PublicWord]


class PublicPagesService:
    def __init__(self, session: Session) -> None:
        self._repo = PublicPagesRepository(session)

    def books(self) -> list[PublicBook]:
        return [_summary(d) for d in self._repo.books() if d.slug]

    def book(self, slug: str) -> PublicBook | None:
        document = self._repo.book(slug)
        if document is None or document.slug is None:
            return None
        counts = self._repo.word_counts(document.id)
        chapters = [
            PublicChapterSummary(c.index + 1, c.title, counts.get(c.id, 0))
            for c in sorted(document.chapters, key=lambda c: c.index)
        ]
        return PublicBook(document.slug, document.title, document.author, chapters)

    def chapter(self, slug: str, number: int) -> PublicChapter | None:
        """Chapter `number` (1-based) with its hardest words."""
        document = self._repo.book(slug)
        book = self.book(slug)
        if document is None or book is None:
            return None
        chapter = next((c for c in document.chapters if c.index == number - 1), None)
        if chapter is None:
            return None
        words = []
        for chapter_word, word in self._repo.hardest(chapter, WORDS_PER_CHAPTER):
            definitions = definitions_in_context(word, chapter_word.pos)
            words.append(
                PublicWord(
                    lemma=word.lemma,
                    meaning=definitions[0].text if definitions else None,
                    sentence=chapter_word.context_sentence,
                    form=chapter_word.context_form,
                )
            )
        return PublicChapter(book, number, chapter.title, words)


def _summary(document: Document) -> PublicBook:
    assert document.slug is not None
    return PublicBook(document.slug, document.title, document.author)
