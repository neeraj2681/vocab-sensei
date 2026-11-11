from app.core.slugs import MAX_LENGTH, slugify


def test_titles_become_readable_url_names() -> None:
    assert slugify("Alice's Adventures in Wonderland") == "alices-adventures-in-wonderland"
    assert slugify("Moby-Dick; or, The Whale") == "moby-dick-or-the-whale"
    assert slugify("Les Misérables") == "les-miserables"
    assert slugify("!!!") == "book"


def test_long_titles_are_cut_at_a_word() -> None:
    slug = slugify("word " * 40)

    assert len(slug) <= MAX_LENGTH
    assert not slug.endswith("-")
