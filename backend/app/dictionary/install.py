"""Downloads the WordNet data the app needs (about 125 MB on disk, a minute or so).

uv run python -m app.dictionary.install
"""

from app.core.config import get_settings
from app.dictionary.wordnet import install


def main() -> None:
    settings = get_settings()
    print(f"Installing {settings.dictionary.lexicon} into {settings.dictionary_dir} ...")
    install(settings.dictionary_dir, settings.dictionary.lexicon)
    print("Done.")


if __name__ == "__main__":
    main()
