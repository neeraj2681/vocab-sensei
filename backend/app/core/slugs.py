"""Readable URL names for books, e.g. "Alice's Adventures" -> "alices-adventures"."""

import re
import unicodedata

MAX_LENGTH = 80


def slugify(text: str) -> str:
    """Lower-case ASCII words joined by hyphens (apostrophes dropped, accents removed), at most
    MAX_LENGTH characters, cut at a word boundary; "book" if nothing is left."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    words = re.findall(r"[a-z0-9]+", ascii_text.lower().replace("'", ""))
    slug = ""
    for word in words:
        candidate = f"{slug}-{word}" if slug else word
        if len(candidate) > MAX_LENGTH:
            break
        slug = candidate
    return slug or "book"
