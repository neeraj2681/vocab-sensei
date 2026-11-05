"""Whether what the recogniser heard is the word being practised. Pure: no audio, no web."""

import jellyfish

SIMILAR_ENOUGH = 0.88  # Jaro-Winkler, letters only: "laguubrious" for "lugubrious" passes


def said(heard: str, word: str) -> bool:
    """True when `heard` sounds like `word` (same Metaphone code) or is spelled very nearly the
    same. Recognisers split rare words ("Mel and Colley" for melancholy), so spaces are ignored."""
    letters = "".join(ch for ch in heard.lower() if ch.isalpha())
    target = "".join(ch for ch in word.lower() if ch.isalpha())
    if not letters or not target:
        return False
    if jellyfish.metaphone(letters) == jellyfish.metaphone(target):
        return True
    return jellyfish.jaro_winkler_similarity(letters, target) >= SIMILAR_ENOUGH
