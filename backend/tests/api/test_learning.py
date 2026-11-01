from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import WordStatus
from app.db.models import Document, User, UserWord, Word
from tests.api.test_documents import upload
from tests.extraction.epub_builder import Chapter, EpubSpec, build_epub

# Only common words besides the one rare word per chapter, so the word lists stay predictable.
FILLER = (
    " And the man said that the day was long and the night was cold,"
    " and he went home to sleep for a while."
)
BOOK_A = ["The tune was lugubrious.", "The talk was perfunctory.", "The servant was obsequious."]
BOOK_B = ["He was a sycophant.", "She was ebullient.", "The song was lugubrious."]


def add_book(client: TestClient, tmp_path: Path, name: str, sentences: list[str]) -> int:
    spec = EpubSpec(
        [
            Chapter(f"c{i}.xhtml", f"<p>{sentence}{FILLER}</p>", toc_title=f"Part {i}")
            for i, sentence in enumerate(sentences)
        ]
    )
    document_id = upload(client, build_epub(tmp_path / f"{name}.epub", spec).read_bytes())["id"]
    assert isinstance(document_id, int)
    assert client.post("/api/readings", json={"document_id": document_id}).status_code == 201
    return document_id


def next_lemmas(client: TestClient, count: int = 10) -> list[str]:
    response = client.get(f"/api/learning/next?count={count}")
    assert response.status_code == 200, response.text
    return [w["lemma"] for w in response.json()]


def set_status(session: Session, lemma: str, status: WordStatus) -> None:
    user = session.scalars(select(User)).one()
    word = session.scalars(select(Word).where(Word.lemma == lemma)).one()
    session.add(UserWord(user_id=user.id, word_id=word.id, status=status))
    session.commit()


def test_words_come_in_reading_order(user_client: TestClient, tmp_path: Path) -> None:
    add_book(user_client, tmp_path, "a", BOOK_A)

    assert next_lemmas(user_client) == ["lugubrious", "perfunctory", "obsequious"]


def test_each_word_says_where_it_comes_from(user_client: TestClient, tmp_path: Path) -> None:
    document_id = add_book(user_client, tmp_path, "a", BOOK_A)

    first = user_client.get("/api/learning/next?count=1").json()[0]

    assert first["document_id"] == document_id
    assert first["document_title"] == "Moby-Dick"
    assert first["chapter_index"] == 0
    assert first["chapter_title"] == "Part 0"
    assert first["context_sentence"] == "The tune was lugubrious."
    assert first["pos"] == "adjective"
    assert first["definitions"] == [{"pos": "noun", "text": "meaning of lugubrious"}]


def test_starts_at_the_current_chapter(user_client: TestClient, tmp_path: Path) -> None:
    document_id = add_book(user_client, tmp_path, "a", BOOK_A)
    user_client.patch(f"/api/readings/{document_id}", json={"current_chapter_index": 1})

    words = user_client.get("/api/learning/next?count=10").json()

    # Chapter 0's words come too, but after the chapters ahead (1 in 4 at most).
    assert [(w["lemma"], w["earlier"]) for w in words] == [
        ("perfunctory", False),
        ("obsequious", False),
        ("lugubrious", True),
    ]


def test_one_in_four_new_words_comes_from_earlier_chapters(
    user_client: TestClient, two_chapter_book: Document
) -> None:
    user_client.patch(f"/api/readings/{two_chapter_book.id}", json={"current_chapter_index": 1})

    words = user_client.get("/api/learning/next?count=8").json()

    assert [w["lemma"] for w in words] == [
        "word10", "word11", "word00", "word12", "word13", "word14", "word01", "word15",
    ]  # fmt: skip
    assert [w["earlier"] for w in words].count(True) == 2


def test_a_word_used_again_later_counts_for_the_later_chapter(
    user_client: TestClient, tmp_path: Path
) -> None:
    sentences = ["The tune was lugubrious.", "The talk was perfunctory.", "A lugubrious wind blew."]
    document_id = add_book(user_client, tmp_path, "a", sentences)
    user_client.patch(f"/api/readings/{document_id}", json={"current_chapter_index": 1})

    words = {w["lemma"]: w for w in user_client.get("/api/learning/next?count=10").json()}

    # Met again in chapter 2: an upcoming word, with chapter 2's sentence.
    assert (words["lugubrious"]["chapter_index"], words["lugubrious"]["earlier"]) == (2, False)
    assert words["lugubrious"]["context_sentence"] == "A lugubrious wind blew."


def test_skips_words_already_started_learned_or_known(
    user_client: TestClient, tmp_path: Path, session: Session
) -> None:
    add_book(user_client, tmp_path, "a", [*BOOK_A, "The boy was a sycophant."])
    set_status(session, "lugubrious", WordStatus.LEARNING)
    set_status(session, "perfunctory", WordStatus.KNOWN)
    set_status(session, "obsequious", WordStatus.LEARNED)
    set_status(session, "sycophant", WordStatus.NEW)  # a row, but not started yet

    assert next_lemmas(user_client) == ["sycophant"]


def test_books_share_the_list_by_priority(user_client: TestClient, tmp_path: Path) -> None:
    add_book(user_client, tmp_path, "a", BOOK_A)  # priority 0: 2 of every 3 words
    add_book(user_client, tmp_path, "b", BOOK_B)  # priority 1: 1 of every 3

    assert next_lemmas(user_client) == [
        "lugubrious",
        "sycophant",
        "perfunctory",
        "obsequious",
        "ebullient",  # book B's "lugubrious" is a duplicate
    ]


def test_count_limits_the_list(user_client: TestClient, tmp_path: Path) -> None:
    add_book(user_client, tmp_path, "a", BOOK_A)

    assert next_lemmas(user_client, count=2) == ["lugubrious", "perfunctory"]
    assert user_client.get("/api/learning/next?count=0").status_code == 422


def test_empty_without_current_reads(user_client: TestClient) -> None:
    assert next_lemmas(user_client) == []


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/learning/next").status_code == 401
