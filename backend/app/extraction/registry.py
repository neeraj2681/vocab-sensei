from app.core.enums import DocumentFormat
from app.extraction.epub import EpubParser
from app.extraction.types import DocumentParser

_PARSERS: dict[DocumentFormat, DocumentParser] = {
    DocumentFormat.EPUB: EpubParser(),
}


class UnsupportedFormatError(Exception):
    pass


def get_parser(document_format: DocumentFormat) -> DocumentParser:
    try:
        return _PARSERS[document_format]
    except KeyError:
        raise UnsupportedFormatError(f"{document_format} files are not supported yet") from None
