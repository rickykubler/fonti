"""Docling parser: layout analysis, reading order, table structure and OCR for scanned pages.

Optional: needs the `docling` extra. Models are loaded once per parser instance.
"""

import logging
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium

from fonti.config import ParserSettings
from fonti.domain import Block, BlockKind, ParsedDocument
from fonti.ingest.parsers import ParseError
from fonti.ingest.structure import collapse_letter_spacing, heading_level
from fonti.ingest.text import normalize

logger = logging.getLogger(__name__)

MISSING_DOCLING_MESSAGE = (
    "Per leggere scansioni, tabelle e file .docx serve l'extra docling: "
    "esegui `uv sync --extra gpu --extra docling` (oppure `--extra cpu --extra docling`)."
)


class DoclingUnavailableError(ParseError):
    pass


# A page with fewer characters than this in its text layer is treated as scanned.
MIN_TEXT_CHARS = 20


class DoclingParser:
    def __init__(self, settings: ParserSettings) -> None:
        self._settings = settings
        self._converter: Any = None

    def parse(self, path: Path) -> ParsedDocument:
        converter = self._load()
        try:
            result = converter.convert(str(path))
        except Exception as exc:  # Docling raises many exception types for unreadable files
            raise ParseError(f"Docling non è riuscito a leggere {path.name}: {exc}") from exc
        document = result.document
        blocks = list(_blocks(document))
        page_count = len(document.pages) or max((b.page for b in blocks), default=1)
        ocr_pages = tuple(scanned_pages(path)) if path.suffix.lower() == ".pdf" else ()
        title = next((b.text for b in blocks if b.kind is BlockKind.HEADING), None)
        return ParsedDocument(tuple(blocks), page_count, title, "docling", ocr_pages)

    def _load(self) -> Any:
        if self._converter is None:
            try:
                from docling.datamodel.base_models import InputFormat
                from docling.datamodel.pipeline_options import PdfPipelineOptions
                from docling.document_converter import DocumentConverter, PdfFormatOption
            except ImportError as exc:
                raise DoclingUnavailableError(MISSING_DOCLING_MESSAGE) from exc
            options = PdfPipelineOptions()
            options.do_ocr = self._settings.ocr
            options.do_table_structure = self._settings.tables
            options.ocr_options = _ocr_options(self._settings)
            if models_dir().is_dir():
                # Models fetched by `fonti models pull`: no download, no Hub request.
                options.artifacts_path = models_dir()
            self._converter = DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
            )
        return self._converter


def scanned_pages(path: Path) -> list[int]:
    """1-based numbers of the pages without a usable text layer."""
    pdf = pdfium.PdfDocument(path)
    try:
        pages = []
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                textpage = page.get_textpage()
                text = textpage.get_text_range()
                textpage.close()
            finally:
                page.close()
            if len("".join(text.split())) < MIN_TEXT_CHARS:
                pages.append(index + 1)
        return pages
    finally:
        pdf.close()


def models_dir() -> Path:
    """Where `fonti models pull` stores the Docling models (Docling's own cache)."""
    from docling.datamodel.settings import settings

    return Path(settings.cache_dir) / "models"


def download_models(settings: ParserSettings) -> Path:
    from docling.utils.model_downloader import download_models as docling_download

    return Path(
        docling_download(
            models_dir(),
            with_layout=True,
            with_tableformer=settings.tables,
            with_code_formula=False,
            with_picture_classifier=False,
            with_rapidocr=settings.ocr and settings.ocr_engine == "rapidocr",
            with_easyocr=settings.ocr and settings.ocr_engine == "easyocr",
            easyocr_languages=(settings.ocr_languages or ["it", "en"])
            if settings.ocr and settings.ocr_engine == "easyocr"
            else None,
        )
    )


def _ocr_options(settings: ParserSettings) -> Any:
    from docling.datamodel import pipeline_options as options

    # DEFAULT runs OCR only on regions without a text layer; FULL_PAGE ignores the text layer.
    mode = options.OcrMode.FULL_PAGE if settings.force_ocr else options.OcrMode.DEFAULT
    if settings.ocr_engine == "tesseract":
        return options.TesseractCliOcrOptions(
            lang=settings.ocr_languages or ["ita", "eng"], mode=mode
        )
    if settings.ocr_engine == "rapidocr":
        return options.RapidOcrOptions(mode=mode, backend="torch")
    return options.EasyOcrOptions(
        lang=settings.ocr_languages or ["it", "en"],
        mode=mode,
        confidence_threshold=settings.ocr_confidence,
    )


def _blocks(document: Any) -> list[Block]:
    from docling_core.types.doc.items.table.table import TableItem
    from docling_core.types.doc.labels import DocItemLabel

    skipped = {
        DocItemLabel.PAGE_HEADER,
        DocItemLabel.PAGE_FOOTER,
        DocItemLabel.PICTURE,
        DocItemLabel.DOCUMENT_INDEX,
    }
    blocks: list[Block] = []
    for item, _ in document.iterate_items():
        if item.label in skipped:
            continue
        page = item.prov[0].page_no if item.prov else (blocks[-1].page if blocks else 1)
        if isinstance(item, TableItem):
            table = item.export_to_markdown(doc=document).strip()
            if table:
                blocks.append(Block(BlockKind.TABLE, normalize(table), page))
            continue
        text = collapse_letter_spacing(normalize(getattr(item, "text", "") or "").strip())
        if not text:
            continue
        level = heading_level(text)
        if item.label == DocItemLabel.TITLE:
            blocks.append(Block(BlockKind.HEADING, text, page, level or 1))
        elif item.label == DocItemLabel.SECTION_HEADER or (level and len(text) <= 120):
            blocks.append(Block(BlockKind.HEADING, text, page, level or 2))
        else:
            blocks.append(Block(BlockKind.TEXT, text, page))
    return blocks
