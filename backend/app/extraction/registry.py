from app.core.enums import DocumentFormat
from app.extraction.epub import EpubParser
from app.extraction.pdf import PdfParser
from app.extraction.txt import TxtParser
from app.extraction.types import DocumentParser

_PARSERS: dict[DocumentFormat, DocumentParser] = {
    DocumentFormat.EPUB: EpubParser(),
    DocumentFormat.PDF: PdfParser(),
    DocumentFormat.TXT: TxtParser(),
}


def get_parser(document_format: DocumentFormat) -> DocumentParser:
    """Every format has a parser; a new format is added to DocumentFormat and here together."""
    return _PARSERS[document_format]
