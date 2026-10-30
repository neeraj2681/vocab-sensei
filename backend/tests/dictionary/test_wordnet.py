"""WordNetDictionary against a tiny hand-written lexicon, so tests need no download."""

from pathlib import Path

import pytest
import wn

from app.core.config import Settings
from app.dictionary import install as install_command
from app.dictionary.types import DictionaryUnavailableError, Sense
from app.dictionary.wordnet import WordNetDictionary, install

LEXICON = "test:1"

# WN-LMF, the XML format Open English WordNet is published in.
LMF = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE LexicalResource SYSTEM "http://globalwordnet.github.io/schemas/WN-LMF-1.0.dtd">
<LexicalResource xmlns:dc="https://globalwordnet.github.io/schemas/dc/">
  <Lexicon id="test" label="Test" language="en" email="t@example.com"
           license="https://creativecommons.org/licenses/by/4.0/" version="1">
    <LexicalEntry id="e-spleen-n"><Lemma writtenForm="spleen" partOfSpeech="n"/>
      <Sense id="s-spleen-1" synset="n-organ"/><Sense id="s-spleen-2" synset="n-anger"/>
    </LexicalEntry>
    <LexicalEntry id="e-loom-n"><Lemma writtenForm="loom" partOfSpeech="n"/>
      <Sense id="s-loom-n" synset="n-machine"/>
    </LexicalEntry>
    <LexicalEntry id="e-loom-v"><Lemma writtenForm="loom" partOfSpeech="v"/>
      <Sense id="s-loom-v1" synset="v-appear"/><Sense id="s-loom-v2" synset="v-tower"/>
      <Sense id="s-loom-v3" synset="v-threaten"/>
    </LexicalEntry>
    <LexicalEntry id="e-drizzly-s"><Lemma writtenForm="drizzly" partOfSpeech="s"/>
      <Sense id="s-drizzly" synset="s-wet"/>
    </LexicalEntry>
    <LexicalEntry id="e-damp-a"><Lemma writtenForm="damp" partOfSpeech="a"/>
      <Sense id="s-damp-a" synset="s-wet"/>
    </LexicalEntry>
    <LexicalEntry id="e-damp-s"><Lemma writtenForm="damp" partOfSpeech="s"/>
      <Sense id="s-damp-s" synset="s-wet-again"/>
    </LexicalEntry>
    <Synset id="n-organ" ili="" partOfSpeech="n">
      <Definition>an organ near the stomach</Definition>
    </Synset>
    <Synset id="n-anger" ili="" partOfSpeech="n">
      <Definition>a feeling of resentful anger</Definition>
    </Synset>
    <Synset id="n-machine" ili="" partOfSpeech="n">
      <Definition>a machine for weaving</Definition>
    </Synset>
    <Synset id="v-appear" ili="" partOfSpeech="v">
      <Definition>come into view indistinctly</Definition>
    </Synset>
    <Synset id="v-tower" ili="" partOfSpeech="v">
      <Definition>appear very large</Definition>
    </Synset>
    <Synset id="v-threaten" ili="" partOfSpeech="v">
      <Definition>seem about to happen</Definition>
    </Synset>
    <Synset id="s-wet" ili="" partOfSpeech="s">
      <Definition>wet with light rain</Definition>
    </Synset>
    <Synset id="s-wet-again" ili="" partOfSpeech="s">
      <Definition>wet with light rain</Definition>
    </Synset>
  </Lexicon>
</LexicalResource>
"""


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("wordnet")
    source = directory / "test.xml"
    source.write_text(LMF)
    wn.config.data_directory = directory
    wn.add(source, progress_handler=None)
    return directory


@pytest.fixture
def dictionary(data_dir: Path) -> WordNetDictionary:
    return WordNetDictionary(data_dir, LEXICON, senses_per_pos=2)


def test_senses_come_in_dictionary_order(dictionary: WordNetDictionary) -> None:
    assert dictionary.senses("spleen") == [
        Sense(pos="noun", definition="an organ near the stomach", rank=0),
        Sense(pos="noun", definition="a feeling of resentful anger", rank=1),
    ]


def test_each_part_of_speech_is_capped(dictionary: WordNetDictionary) -> None:
    senses = dictionary.senses("loom")

    assert [s.pos for s in senses] == ["noun", "verb", "verb"]  # the third verb sense is dropped
    assert [s.rank for s in senses] == [0, 1, 2]


def test_satellite_adjectives_count_as_adjectives(dictionary: WordNetDictionary) -> None:
    assert dictionary.senses("drizzly") == [
        Sense(pos="adjective", definition="wet with light rain", rank=0)
    ]


def test_repeated_definitions_are_kept_once(dictionary: WordNetDictionary) -> None:
    assert [s.definition for s in dictionary.senses("damp")] == ["wet with light rain"]


def test_unknown_words_have_no_senses(dictionary: WordNetDictionary) -> None:
    assert dictionary.senses("hypos") == []


def test_source_names_the_lexicon(dictionary: WordNetDictionary) -> None:
    assert dictionary.source == LEXICON


def test_missing_lexicon_raises_a_helpful_error(data_dir: Path) -> None:
    with pytest.raises(DictionaryUnavailableError, match=r"app\.dictionary\.install"):
        WordNetDictionary(data_dir, "oewn:1999")


def test_install_downloads_only_missing_lexicons(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    downloads: list[str] = []
    monkeypatch.setattr(wn, "download", downloads.append)

    install(data_dir, LEXICON)
    install(data_dir, "oewn:2025")

    assert downloads == ["oewn:2025"]


def test_install_command_uses_the_configured_lexicon(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[Path, str]] = []
    monkeypatch.setattr(install_command, "install", lambda d, lex: calls.append((d, lex)))
    monkeypatch.setattr(
        install_command, "get_settings", lambda: Settings(data_dir=tmp_path / "data")
    )

    install_command.main()

    assert calls == [(tmp_path / "data" / "wordnet", "oewn:2025")]
