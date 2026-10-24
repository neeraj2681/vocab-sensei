"""Builds small EPUB files for tests."""

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

CONTAINER = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="{opf}" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""


@dataclass
class Chapter:
    file: str  # path relative to the OPF folder
    body: str  # inner HTML of <body>
    toc_title: str | None = None
    linear: bool = True


@dataclass
class EpubSpec:
    chapters: list[Chapter]
    title: str = "Moby-Dick"
    author: str = "Herman Melville"
    toc: str = "nav"  # "nav" (EPUB 3), "ncx" (EPUB 2) or "none"
    opf_dir: str = "OEBPS"
    extra_manifest: list[tuple[str, str, str]] = field(default_factory=list)  # id, href, type
    toc_links: list[tuple[str, str]] | None = None  # (href, title); default: one per chapter


def xhtml(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>x</title>'
        f"<style>p {{ color: red }}</style></head><body>{body}</body></html>"
    )


def toc_links(spec: EpubSpec) -> list[tuple[str, str]]:
    if spec.toc_links is not None:
        return spec.toc_links
    return [(c.file, c.toc_title) for c in spec.chapters if c.toc_title]


def build_epub(path: Path, spec: EpubSpec) -> Path:
    d = f"{spec.opf_dir}/" if spec.opf_dir else ""
    manifest = [
        f'<item id="c{i}" href="{c.file}" media-type="application/xhtml+xml"/>'
        for i, c in enumerate(spec.chapters)
    ]
    # Spine lists chapters in the given order; manifest order is reversed on purpose.
    manifest.reverse()
    spine = [
        f'<itemref idref="c{i}"{"" if c.linear else ' linear="no"'}/>'
        for i, c in enumerate(spec.chapters)
    ]
    files: dict[str, str] = {}

    if spec.toc == "nav":
        manifest.append(
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        )
        spine.insert(0, '<itemref idref="nav"/>')
        links = "".join(f'<li><a href="{href}">{title}</a></li>' for href, title in toc_links(spec))
        files[f"{d}nav.xhtml"] = xhtml(
            f'<nav xmlns:epub="http://www.idpf.org/2007/ops" epub:type="toc"><ol>{links}</ol></nav>'
        )
    elif spec.toc == "ncx":
        manifest.append('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')
        points = "".join(
            f'<navPoint id="p{i}"><navLabel><text>{title}</text></navLabel>'
            f'<content src="{href}"/></navPoint>'
            for i, (href, title) in enumerate(toc_links(spec))
        )
        files[f"{d}toc.ncx"] = (
            '<?xml version="1.0"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/">'
            f"<navMap>{points}</navMap></ncx>"
        )
    for item_id, href, media_type in spec.extra_manifest:
        manifest.append(f'<item id="{item_id}" href="{href}" media-type="{media_type}"/>')

    toc_attr = ' toc="ncx"' if spec.toc == "ncx" else ""
    files[f"{d}content.opf"] = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="id">test-book</dc:identifier>
    <dc:title>{spec.title}</dc:title>
    <dc:creator>{spec.author}</dc:creator>
  </metadata>
  <manifest>{"".join(manifest)}</manifest>
  <spine{toc_attr}>{"".join(spine)}</spine>
</package>"""
    for c in spec.chapters:
        files[f"{d}{c.file.replace('%20', ' ')}"] = xhtml(c.body)

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", CONTAINER.format(opf=f"{d}content.opf"))
        for name, content in files.items():
            archive.writestr(name, content)
    return path
