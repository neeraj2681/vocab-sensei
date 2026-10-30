"""EPUB 2 and 3 parsing with the standard library zip reader and BeautifulSoup.

An EPUB is a zip file: META-INF/container.xml points to the package (.opf) file, whose spine lists
the content files in reading order. Chapters come from the table of contents (EPUB 3 nav document
or EPUB 2 NCX). A content file can hold several chapters (TOC links point at #anchors inside it),
and one chapter can span several files (big chapters split by converters), so chapters are cut at
TOC positions rather than at file boundaries. Without a TOC, each file is a chapter titled by its
first heading.
"""

import posixpath
import re
import warnings
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from bs4.element import NavigableString, PreformattedString, Tag

from app.extraction.chapters import merge_short
from app.extraction.types import ParsedChapter, ParsedDocument, ParseError

MAX_UNCOMPRESSED_BYTES = 300 * 1024 * 1024  # guards against zip bombs
_HTML_TYPES = {"application/xhtml+xml", "text/html"}
# A new paragraph (line) starts at these elements; inline ones (<i>, <span>, ...) stay in the line.
_BLOCK_TAGS = {
    *("p", "div", "br", "hr", "pre", "blockquote", "section", "article", "aside", "header"),
    *("h1", "h2", "h3", "h4", "h5", "h6", "li", "ul", "ol", "dl", "dt", "dd", "table", "tr"),
    *("figure", "figcaption", "footer"),
}
_WHITESPACE = re.compile(r"\s+")


class EpubParser:
    def parse(self, path: Path) -> ParsedDocument:
        try:
            with zipfile.ZipFile(path) as archive:
                return _EpubReader(archive).read()
        except zipfile.BadZipFile as exc:
            raise ParseError("not a valid EPUB (zip) file") from exc


@dataclass(frozen=True)
class _TocEntry:
    path: str  # content file inside the zip
    fragment: str | None  # anchor id inside that file, None = start of file
    title: str


@dataclass
class _Draft:
    title: str | None
    parts: list[str] = field(default_factory=list)


class _EpubReader:
    def __init__(self, archive: zipfile.ZipFile) -> None:
        if sum(info.file_size for info in archive.infolist()) > MAX_UNCOMPRESSED_BYTES:
            raise ParseError("EPUB is too large once uncompressed")
        self._archive = archive

    def read(self) -> ParsedDocument:
        opf_path = self._package_path()
        opf = self._xml(opf_path)
        opf_dir = posixpath.dirname(opf_path)
        manifest: dict[str, Tag] = {
            str(item["id"]): item
            for item in opf.find_all("item")
            if item.get("id") and item.get("href")
        }

        toc = self._toc_entries(opf, manifest, opf_dir)
        drafts: list[_Draft] = []
        for path in self._spine_paths(opf, manifest, opf_dir):
            self._add_file(drafts, path, [e for e in toc if e.path == path], has_toc=bool(toc))

        chapters = merge_short(
            [ParsedChapter(title=d.title, text=text) for d in drafts if (text := _clean(d.parts))]
        )
        if not chapters:
            raise ParseError("EPUB has no readable text")
        return ParsedDocument(
            title=_text_of(opf.find("dc:title") or opf.find("title")),
            author=_text_of(opf.find("dc:creator") or opf.find("creator")),
            chapters=chapters,
        )

    def _add_file(
        self, drafts: list[_Draft], path: str, entries: list[_TocEntry], *, has_toc: bool
    ) -> None:
        doc = self._html(path)
        for tag in doc(["script", "style", "head"]):
            tag.decompose()

        file_title = next((e.title for e in entries if e.fragment is None), None)
        anchors: dict[str, str] = {}
        for e in entries:
            if e.fragment and e.fragment not in anchors:
                anchors[e.fragment] = e.title
        preamble, sections = _split_at_anchors(doc, anchors)

        if file_title is None and anchors and not sections:
            file_title = next(iter(anchors.values()))  # TOC anchors missing from the file
        if file_title is not None:
            drafts.append(_Draft(file_title, preamble))
        elif not has_toc:
            heading = doc.find(["h1", "h2", "h3"])
            drafts.append(_Draft(_text_of(heading), preamble))
        elif drafts:
            drafts[-1].parts.extend(preamble)  # continuation of the previous chapter
        else:
            drafts.append(_Draft(None, preamble))  # front matter before the first TOC entry
        drafts.extend(_Draft(title, parts) for title, parts in sections)

    def _package_path(self) -> str:
        container = self._xml("META-INF/container.xml")
        rootfile = container.find("rootfile")
        if rootfile is None or not rootfile.get("full-path"):
            raise ParseError("EPUB container does not name a package file")
        return str(rootfile["full-path"])

    def _spine_paths(self, opf: Tag, manifest: dict[str, Tag], opf_dir: str) -> list[str]:
        paths = []
        for itemref in opf.find_all("itemref"):
            item = manifest.get(str(itemref.get("idref")))
            if item is None or itemref.get("linear") == "no":
                continue
            if item.get("media-type") not in _HTML_TYPES or "nav" in _properties(item):
                continue
            paths.append(_resolve(opf_dir, str(item["href"]))[0])
        return paths

    def _toc_entries(self, opf: Tag, manifest: dict[str, Tag], opf_dir: str) -> list[_TocEntry]:
        """TOC entries in reading order, from the EPUB 3 nav doc or else the EPUB 2 NCX."""
        links: list[tuple[str, str, str]] = []  # base dir, href, label
        nav = next((i for i in manifest.values() if "nav" in _properties(i)), None)
        if nav is not None:
            nav_path = _resolve(opf_dir, str(nav["href"]))[0]
            doc = self._html(nav_path)
            toc = doc.find("nav", attrs={"epub:type": "toc"}) or doc.find("nav") or doc
            base = posixpath.dirname(nav_path)
            links = [(base, str(a["href"]), a.get_text()) for a in toc.find_all("a", href=True)]

        spine = opf.find("spine")
        ncx_id = str(spine.get("toc") or "") if isinstance(spine, Tag) else ""
        if not links and ncx_id in manifest:
            ncx_path = _resolve(opf_dir, str(manifest[ncx_id]["href"]))[0]
            base = posixpath.dirname(ncx_path)
            for point in self._xml(ncx_path).find_all("navPoint"):
                content, label = point.find("content"), point.find("navLabel")
                if isinstance(content, Tag) and label is not None and content.get("src"):
                    links.append((base, str(content["src"]), label.get_text()))

        entries, seen = [], set()
        for base, href, text in links:
            path, fragment = _resolve(base, href)
            title = " ".join(text.split())
            if title and (path, fragment) not in seen:
                seen.add((path, fragment))
                entries.append(_TocEntry(path, fragment, title))
        return entries

    def _read(self, path: str) -> bytes:
        try:
            return self._archive.read(path)
        except KeyError:
            raise ParseError(f"EPUB is missing {path}") from None

    def _xml(self, path: str) -> BeautifulSoup:
        return BeautifulSoup(self._read(path), "lxml-xml")

    def _html(self, path: str) -> BeautifulSoup:
        # Content files are XHTML, but the forgiving HTML parser copes with real-world mistakes.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
            return BeautifulSoup(self._read(path), "lxml")


def _split_at_anchors(
    doc: BeautifulSoup, anchors: dict[str, str]
) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Text before the first anchor, then (title, text) for each anchor in document order."""
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current = preamble
    remaining = dict(anchors)
    for node in doc.descendants:
        if isinstance(node, Tag):
            anchor = node.get("id") or (node.get("name") if node.name == "a" else None)
            if anchor and (title := remaining.pop(str(anchor), None)) is not None:
                current = []
                sections.append((title, current))
            if node.name in _BLOCK_TAGS:
                current.append("\n")
        elif isinstance(node, NavigableString) and not isinstance(node, PreformattedString):
            # Line breaks inside the HTML source are just spaces. (PreformattedString covers
            # comments, doctype, CDATA, ...)
            current.append(_WHITESPACE.sub(" ", str(node)))
    return preamble, sections


def _clean(parts: list[str]) -> str:
    """One paragraph per line, whitespace collapsed, blank lines dropped."""
    lines = (" ".join(line.split()) for line in "".join(parts).split("\n"))
    return "\n".join(line for line in lines if line)


def _resolve(base_dir: str, href: str) -> tuple[str, str | None]:
    """(zip path, #fragment) of an href relative to base_dir."""
    target, _, fragment = unquote(href).partition("#")
    return posixpath.normpath(posixpath.join(base_dir, target)), fragment or None


def _properties(item: Tag) -> list[str]:
    return str(item.get("properties") or "").split()


def _text_of(tag: object) -> str | None:
    if not isinstance(tag, Tag):
        return None
    return " ".join(tag.get_text().split()) or None
