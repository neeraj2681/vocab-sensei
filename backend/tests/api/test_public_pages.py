from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import DocumentFormat, DocumentStatus, PartOfSpeech
from app.db.models import Chapter, ChapterWord, Definition, Document, Word
from tests.conftest import make_user


def add_book(
    session: Session, slug: str | None = "dracula", owner_id: int | None = None
) -> tuple[Document, list[Chapter]]:
    chapters = [Chapter(index=0, title="Jonathan Harker's Journal"), Chapter(index=1, title="Two")]
    document = Document(
        owner_user_id=owner_id,
        title="Dracula",
        author="Bram Stoker",
        original_filename="dracula.epub",
        file_path="classics/dracula.epub",
        format=DocumentFormat.EPUB,
        status=DocumentStatus.READY,
        slug=slug,
        chapters=chapters,
    )
    session.add(document)
    session.flush()
    return document, chapters


def add_chapter_word(
    session: Session,
    document: Document,
    chapter: Chapter,
    lemma: str,
    zipf: float | None,
    sentence: str | None = None,
    form: str | None = None,
) -> None:
    word = Word(
        lemma=lemma,
        zipf_frequency=zipf,
        definitions=[Definition(pos="noun", text=f"meaning of {lemma}", source="t", sense_rank=0)],
    )
    session.add(word)
    session.flush()
    session.add(
        ChapterWord(
            chapter_id=chapter.id,
            word_id=word.id,
            document_id=document.id,
            first_position=0,
            context_sentence=sentence or f"He saw the {lemma} there.",
            context_form=form or lemma,
            pos=PartOfSpeech.NOUN,
        )
    )
    session.commit()


def test_books_lists_public_books(client: TestClient, session: Session) -> None:
    add_book(session)
    session.commit()
    response = client.get("/classics")
    assert response.status_code == 200
    assert 'href="/classics/dracula"' in response.text
    assert "Cache-Control" in response.headers
    assert response.headers["cache-control"] == "public, max-age=3600"


def test_book_page_lists_chapters_with_word_counts(client: TestClient, session: Session) -> None:
    document, chapters = add_book(session)
    add_chapter_word(session, document, chapters[0], "aaa", 2.0)
    add_chapter_word(session, document, chapters[0], "bbb", 3.0)
    add_chapter_word(session, document, chapters[1], "ccc", 3.0)
    text = client.get("/classics/dracula").text
    assert "Chapter 1: Jonathan Harker&#39;s Journal" in text
    assert "· 2 words" in text
    assert "Chapter 2: Two" in text
    assert "· 1 word<" in text
    assert 'href="/classics/dracula/chapter-2"' in text


def test_chapter_page_shows_the_twenty_hardest_words_first(
    client: TestClient, session: Session
) -> None:
    document, chapters = add_book(session)
    for i in range(25):
        add_chapter_word(session, document, chapters[0], f"w{i:02d}", 5.0 - i * 0.1)
    add_chapter_word(session, document, chapters[0], "unknown", None)
    text = client.get("/classics/dracula/chapter-1").text
    assert text.count('class="word"') == 20
    assert text.index(">w24<") < text.index(">w23<")  # rarest first
    assert ">w04<" not in text  # the 6 most common words are left out
    assert ">unknown<" not in text  # unknown frequency sorts last
    assert "meaning of w24" in text
    assert "<mark>w24</mark>" in text
    assert "Hard words in Dracula, chapter 1" in text


def test_sentences_are_escaped_and_only_the_form_is_marked(
    client: TestClient, session: Session
) -> None:
    document, chapters = add_book(session)
    add_chapter_word(
        session, document, chapters[0], "gloom", 2.0, "<script>x</script> Gloomy gloomy", "Gloomy"
    )
    text = client.get("/classics/dracula/chapter-1").text
    assert "<script>x" not in text
    assert "&lt;script&gt;x&lt;/script&gt; <mark>Gloomy</mark> gloomy" in text


def test_missing_pages_are_404(client: TestClient, session: Session) -> None:
    add_book(session)
    owner = make_user(session)
    add_book(session, slug="private", owner_id=owner.id)
    session.commit()
    for path in (
        "/classics/nope",
        "/classics/dracula/chapter-99",
        "/classics/private",
        "/classics/private/chapter-1",
    ):
        response = client.get(path)
        assert response.status_code == 404, path
        assert "Book not found" in response.text


def test_sitemap_and_robots(client: TestClient, session: Session, settings: Settings) -> None:
    add_book(session)
    session.commit()
    base = settings.email.app_base_url.rstrip("/")
    sitemap = client.get("/sitemap.xml")
    assert sitemap.headers["content-type"].startswith("application/xml")
    for path in (
        "/classics",
        "/classics/dracula",
        "/classics/dracula/chapter-1",
        "/classics/dracula/chapter-2",
    ):
        assert f"<loc>{base}{path}</loc>" in sitemap.text
    robots = client.get("/robots.txt")
    assert robots.headers["content-type"].startswith("text/plain")
    assert f"Sitemap: {base}/sitemap.xml" in robots.text
    assert "Disallow: /api/" in robots.text


def test_chapter_page_metadata(client: TestClient, session: Session, settings: Settings) -> None:
    document, chapters = add_book(session)
    add_chapter_word(session, document, chapters[0], "aaa", 2.0)
    base = settings.email.app_base_url.rstrip("/")
    response = client.get("/classics/dracula/chapter-1")
    text = response.text
    assert "<title>Hard words in Dracula, chapter 1 · Vocab Sensei</title>" in text
    assert f'<link rel="canonical" href="{base}/classics/dracula/chapter-1">' in text
    assert 'href="/register"' in text
    assert 'property="og:title"' in text
    assert response.headers["cache-control"] == "public, max-age=3600"
